import io
import random
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from PIL import Image
from playwright.async_api import async_playwright
from pydantic import BaseModel, Field

app = FastAPI(title="Roleta Salão Maravilhas")

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
            ],
        )
        try:
            page = await browser.new_page(viewport={"width": 480, "height": 780})
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

            result_pngs: list[bytes] = []
            for _ in range(25):
                await page.wait_for_timeout(120)
                png = await page.screenshot(type="png")
                result_pngs.append(png)
        finally:
            await browser.close()

    return _png_frames_to_gif(spin_pngs, result_pngs)


@app.get("/health")
async def health():
    return {"status": "ok", "servico": "Roleta Salão Maravilhas"}


@app.post("/sortear")
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


@app.post("/gif")
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
