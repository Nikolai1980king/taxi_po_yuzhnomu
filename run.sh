#!/bin/bash
cd "$(dirname "$0")"

# Создать venv, если нет
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

. .venv/bin/activate
pip install -q -r requirements.txt
exec python main.py
