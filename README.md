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

No nó **HTTP Request**, em **Headers**, adicione:

| Name      | Value        |
|-----------|--------------|
| X-API-Key | sua-chave-aqui |

O valor deve coincidir com `API_KEY` no `.env` do servidor.

## Endpoints

| Método | Rota       | Auth   | Descrição        |
|--------|------------|--------|------------------|
| GET    | `/health`  | Não    | Status do serviço |
| POST   | `/sortear` | Sim    | Sorteio (+ GIF opcional) |
| POST   | `/gif`     | Sim    | GIF com ganhadora fixa |

Documentação interativa: `http://localhost:8000/docs` (use **Authorize** com a mesma API Key para testar `/sortear` e `/gif`).
