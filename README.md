# API Roleta — Salão Maravilhas

API REST (FastAPI) que sorteia participantes e gera GIF da roleta com Playwright.

## Autenticação

Os endpoints `POST /sortear` e `POST /gif` exigem o header:

```http
X-API-Key: sua-chave-aqui
```

O valor deve ser o mesmo definido em `API_KEY` no arquivo `.env`. O endpoint `GET /health` é **público** (monitoramento).

### Gerar uma chave forte

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

No Windows (PowerShell), com Python instalado:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Cole o resultado em `.env`:

```env
API_KEY=o-valor-gerado-aqui
```

**Não commite o `.env`** (ele está no `.gitignore`).

## Configuração local

1. Copie o exemplo de ambiente: `cp .env.example .env` (ou crie `.env` manualmente).
2. Defina `API_KEY` em `.env`.
3. Crie o venv e instale dependências:

```bash
python -m venv venv
source venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
python -m playwright install chromium
```

4. Suba a API:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Docker

Na pasta do projeto (onde estão `Dockerfile` e `docker-compose.yml`):

1. Crie o `.env` com `API_KEY=...` (veja acima).
2. Execute:

```bash
docker compose up -d --build
```

O `docker-compose.yml` usa `env_file: .env` para injetar `API_KEY` no container.

## n8n

### Fluxos prontos (importar)

Na pasta [`n8n/`](n8n/) há workflows em JSON para importar no n8n:

| Arquivo | Uso |
|---------|-----|
| `00-health.json` | `GET /health` — sem API Key (monitoramento) |
| `01-sortear-json.json` | `POST /sortear` com `retornar_gif: false` — resposta JSON com `ganhadora` e `total` |
| `02-sortear-gif.json` | `POST /sortear` com GIF binário (resposta como arquivo) |
| `03-post-gif-fixo.json` | `POST /gif` — lista + `ganhadora` fixa |
| `04-sortear-video.json` | `POST /sortear/video` — MP4 (GIF + ffmpeg no servidor) |

**Como importar:** no n8n, **Workflows** → menu **⋯** → **Import from File** → escolha o `.json`.

### Variável de ambiente no n8n

Os fluxos usam **`{{ $env.ROLETTA_API_KEY }}`** no header **X-API-Key**. Defina no processo do n8n o mesmo valor da `API_KEY` da API:

- **Docker (n8n):** no `docker-compose` ou `-e ROLETTA_API_KEY=...`
- **systemd / PM2 / host:** exporte `ROLETTA_API_KEY` antes de subir o n8n

**Alternativa sem env:** no nó **HTTP Request**, em **Specify Headers**, troque o valor por texto fixo (apenas testes) ou use credencial **Header Auth** (`X-API-Key`).

### Configurar URL da API

Em cada fluxo, edite o nó **Config** (ou **Code**) e altere `base_url` de `http://localhost:8000` para `http://SEU_IP_OU_DOMINIO:8000`.

### Resposta GIF / MP4

Nos fluxos **02** e **04**, o HTTP Request usa **Response → File** e **Full Response** para binário e headers (**X-Ganhadora**, **X-Total**). O **04** retorna **`video/mp4`** (demora mais: Playwright + ffmpeg). Depois encadeie **Telegram**, **Google Drive**, **Move Binary Data**, etc.

### Montagem manual (HTTP Request)

| Campo | Valor |
|-------|--------|
| Method | `POST` |
| URL | `http://SEU_SERVIDOR:8000/sortear` |
| Header | `X-API-Key`: mesma chave do `.env` da API |
| Body (JSON) | `{"nomes": ["Ana", "Bia"], "retornar_gif": true}` |

Para só JSON: `"retornar_gif": false`.

**Vídeo (MP4):** `POST /sortear/video` com o mesmo body; use `retornar_gif: true` para gerar o vídeo (com `false` a API responde só JSON).

## Endpoints

| Método | Rota       | Auth   | Descrição        |
|--------|------------|--------|------------------|
| GET    | `/health`  | Não    | Status do serviço |
| POST   | `/sortear` | Sim    | Sorteio (+ GIF opcional) |
| POST   | `/sortear/video` | Sim | Sorteio → MP4 (ffmpeg) |
| POST   | `/gif`     | Sim    | GIF com ganhadora fixa |

Documentação interativa: `http://localhost:8000/docs` (use **Authorize** com a mesma API Key).
