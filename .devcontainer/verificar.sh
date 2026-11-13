#!/usr/bin/env bash
# Teste automático (GitHub Actions): confere se o servidor subiu sozinho pelo devcontainer e responde corretamente.
set -e
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
for i in $(seq 1 90); do curl -fs http://127.0.0.1:8000/saude >/dev/null 2>&1 && break; sleep 2; done
curl -fs http://127.0.0.1:8000/saude >/dev/null || { echo "ERRO: servidor nao respondeu"; tail -n 30 /tmp/outgpt.log; exit 1; }
cd "$RAIZ/backend"
OUTGPT_SETUP_TOKEN="$(cat "$HOME/.outgpt_setup_token")" python tests/verificar_publicacao.py http://127.0.0.1:8000 --criar-master