#!/bin/sh
# Ponto de partida para instalar (ou atualizar) o OutGPT em um servidor Ubuntu/Debian novo.
# Uso:   sudo sh instalar.sh        (o passo a passo completo está em SERVIDOR.md)
set -e

if [ "$(id -u)" != "0" ]; then
  echo "Rode como administrador:  sudo sh instalar.sh"
  exit 1
fi
if ! command -v apt-get >/dev/null 2>&1; then
  echo "Este instalador é para Ubuntu ou Debian (usa o apt-get). Veja SERVIDOR.md para outros sistemas."
  exit 1
fi

DIR="${OUTGPT_DIR:-/opt/outgpt}"
REPO="${OUTGPT_REPO:-https://github.com/Marcelo-HC-Ramos/outgptenterprise.git}"

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y git curl python3 ca-certificates

if [ -d "$DIR/.git" ]; then
  echo "Atualizando o projeto em $DIR ..."
  git -C "$DIR" pull --ff-only
else
  echo "Baixando o projeto para $DIR ..."
  git clone --depth 1 "$REPO" "$DIR"
fi

exec python3 "$DIR/servidor/instalar.py" "$@"
