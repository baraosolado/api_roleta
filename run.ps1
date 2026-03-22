Set-Location $PSScriptRoot
if (-not (Test-Path ".\venv\Scripts\python.exe")) {
    Write-Error "Crie o venv: python -m venv venv && .\venv\Scripts\pip install -r requirements.txt"
    exit 1
}
& ".\venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8000
