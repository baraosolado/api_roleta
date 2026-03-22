#!/bin/bash
apt update -y && apt install -y python3 python3-pip python3-venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 -m playwright install chromium
python3 -m playwright install-deps chromium
echo "Instalação concluída!"
echo "Para iniciar: source venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000"
