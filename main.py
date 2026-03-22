import asyncio
import io
import os
import random
import uuid
from pathlib import Path

import aiofiles

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Security, status
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import APIKeyHeader
from PIL import Image
from playwright.async_api import async_playwright
from pydantic import BaseModel, Field

load_dotenv()
API_KEY = os.getenv("API_KEY")

_BASE_DIR = Path(__file__).resolve().parent
_ASSETS_ROLETA_MP3 = _BASE_DIR / "assets" / "roleta.mp3"
_ASSETS_CELEBRACAO_MP3 = _BASE_DIR / "assets" / "celebracao.mp3"

app = FastAPI(title="Roleta Salão Maravilhas")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def validar_api_key(key: str | None = Security(api_key_header)):
    if not key or key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key inválida ou ausente",
        )
    return key


_HTML_CACHE: str | None = None


def _load_roleta_html() -> str:
    global _HTML_CACHE
    if _HTML_CACHE is None:
        _HTML_CACHE = Path("roleta.html").read_text(encoding="utf-8")
    return _HTML_CACHE


class SortearBody(BaseModel):
    nomes: list[str] = Field(..., min_length=1)
    retornar_gif: bool = True


class GifBody(BaseModel):
    nomes: list[str] = Field(..., min_length=1)
    ganhadora: str = Field(..., min_length=1)


def _normalize_nomes(nomes: list[str]) -> list[str]:
    return [n.strip() for n in nomes if n and str(n).strip()]


def _png_frames_to_gif(spin_pngs: list[bytes], result_pngs: list[bytes]) -> bytes:
    durations = [80] * len(spin_pngs) + [120] * len(result_pngs)
    all_pngs = spin_pngs + result_pngs
    images_rgb = [Image.open(io.BytesIO(b)).convert("RGB") for b in all_pngs]
    palette_ref = images_rgb[0].quantize(colors=200, method=Image.Quantize.MEDIANCUT)
    quantized = [im.quantize(palette=palette_ref) for im in images_rgb]
    buf = io.BytesIO()
    n = len(quantized)
    quantized[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=quantized[1:],
        duration=durations,
        loop=0,
        disposal=[2] * n,
    )
    return buf.getvalue()


async def _capture_roleta_gif(nomes: list[str], ganhadora: str) -> bytes:
    html = _load_roleta_html()
    spin_pngs: list[bytes] = []
    max_spin_frames = 600

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--autoplay-policy=no-user-gesture-required",
            ],
        )
        try:
            # Altura >780px: com muitos participantes + roleta + cartão do resultado o layout passa de 780px e o GIF cortava o nome (viewport antigo do PRD).
            page = await browser.new_page(viewport={"width": 480, "height": 1200})
            await page.set_content(html, wait_until="domcontentloaded")
            await page.wait_for_timeout(1000)

            await page.evaluate(
                """([nomes, ganhadora]) => {
                    window._sorteioFinalizado = false;
                    window.iniciarSorteio(nomes, ganhadora);
                }""",
                [nomes, ganhadora],
            )

            for _ in range(max_spin_frames):
                png = await page.screenshot(type="png")
                spin_pngs.append(png)
                done = await page.evaluate("() => window._sorteioFinalizado === true")
                if done:
                    break
                await page.wait_for_timeout(80)
            else:
                raise RuntimeError(
                    "Timeout: animação da roleta não finalizou (_sorteioFinalizado)."
                )

            await page.evaluate(
                """() => {
                    const el = document.getElementById('result');
                    if (el) el.scrollIntoView({ block: 'center', behavior: 'instant' });
                }""",
            )

            result_pngs: list[bytes] = []
            for _ in range(25):
                await page.wait_for_timeout(120)
                png = await page.screenshot(type="png")
                result_pngs.append(png)
        finally:
            await browser.close()

    return _png_frames_to_gif(spin_pngs, result_pngs)


async def gerar_gif_bytes(nomes: list[str], ganhadora: str) -> bytes:
    return await _capture_roleta_gif(nomes, ganhadora)


async def gif_bytes_para_mp4(gif_bytes: bytes) -> bytes:
    if not _ASSETS_ROLETA_MP3.is_file() or not _ASSETS_CELEBRACAO_MP3.is_file():
        raise RuntimeError(
            "Arquivos de áudio ausentes: coloque roleta.mp3 e celebracao.mp3 em api_roleta/assets/."
        )
    base = f"/tmp/roleta_{uuid.uuid4().hex}"
    gif_path = f"{base}.gif"
    mp4_path = f"{base}.mp4"
    try:
        async with aiofiles.open(gif_path, "wb") as f:
            await f.write(gif_bytes)
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-y",
            "-i",
            gif_path,
            "-i",
            str(_ASSETS_ROLETA_MP3),
            "-i",
            str(_ASSETS_CELEBRACAO_MP3),
            "-filter_complex",
            "[1:a][2:a]concat=n=2:v=0:a=1[aout]",
            "-map",
            "0:v",
            "-map",
            "[aout]",
            "-movflags",
            "faststart",
            "-pix_fmt",
            "yuv420p",
            "-vf",
            "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-shortest",
            mp4_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg GIF+áudio→MP4 código {proc.returncode}")

        async with aiofiles.open(mp4_path, "rb") as f:
            return await f.read()
    finally:
        for p in (gif_path, mp4_path):
            try:
                os.unlink(p)
            except OSError:
                pass


@app.get("/health")
async def health():
    return {"status": "ok", "servico": "Roleta Salão Maravilhas"}


@app.post("/sortear", dependencies=[Depends(validar_api_key)])
async def sortear(body: SortearBody):
    nomes = _normalize_nomes(body.nomes)
    if not nomes:
        raise HTTPException(status_code=422, detail="Lista de nomes vazia após normalização.")

    ganhadora = random.choice(nomes)
    total = len(nomes)

    if not body.retornar_gif:
        return JSONResponse(content={"ganhadora": ganhadora, "total": total})

    gif_bytes = await _capture_roleta_gif(nomes, ganhadora)
    return StreamingResponse(
        io.BytesIO(gif_bytes),
        media_type="image/gif",
        headers={
            "X-Ganhadora": ganhadora,
            "X-Total": str(total),
        },
    )


@app.post("/sortear/video", dependencies=[Depends(validar_api_key)])
async def sortear_video(body: SortearBody):
    nomes = _normalize_nomes(body.nomes)
    if not nomes:
        raise HTTPException(status_code=422, detail="Lista de nomes vazia após normalização.")

    ganhadora = random.choice(nomes)
    total = len(nomes)

    if not body.retornar_gif:
        return JSONResponse(content={"ganhadora": ganhadora, "total": total})

    gif_bytes = await gerar_gif_bytes(nomes, ganhadora)
    try:
        mp4_bytes = await gif_bytes_para_mp4(gif_bytes)
    except RuntimeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao converter GIF em MP4: {e}",
        ) from e

    return StreamingResponse(
        io.BytesIO(mp4_bytes),
        media_type="video/mp4",
        headers={
            "X-Ganhadora": ganhadora,
            "X-Total": str(total),
            "Content-Disposition": 'attachment; filename="sorteio_maravilhas.mp4"',
        },
    )


@app.post("/gif", dependencies=[Depends(validar_api_key)])
async def gif_only(body: GifBody):
    nomes = _normalize_nomes(body.nomes)
    if not nomes:
        raise HTTPException(status_code=422, detail="Lista de nomes vazia após normalização.")
    g = body.ganhadora.strip()
    if g not in nomes:
        raise HTTPException(
            status_code=422,
            detail="ganhadora deve estar presente em nomes.",
        )

    gif_bytes = await _capture_roleta_gif(nomes, g)
    return StreamingResponse(
        io.BytesIO(gif_bytes),
        media_type="image/gif",
        headers={"X-Ganhadora": g},
    )


_OPENAPI_HTTP_METHODS = frozenset(
    {"get", "post", "put", "delete", "patch", "head", "options", "trace"},
)

_OPENAPI_PROTECTED_PATHS = frozenset({"/sortear", "/sortear/video", "/gif"})


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version="1.0.0",
        openapi_version=app.openapi_version,
        description=getattr(app, "description", None),
        routes=app.routes,
    )
    if API_KEY:
        components = openapi_schema.setdefault("components", {})
        schemes = components.setdefault("securitySchemes", {})
        schemes["ApiKeyAuth"] = {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "Mesmo valor da variável API_KEY no arquivo .env do servidor.",
        }
        for path, path_item in openapi_schema.get("paths", {}).items():
            if path not in _OPENAPI_PROTECTED_PATHS:
                continue
            for method in _OPENAPI_HTTP_METHODS:
                op = path_item.get(method)
                if isinstance(op, dict):
                    op["security"] = [{"ApiKeyAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi
