#!/bin/sh
# Ajusta a permissão do volume /data (discos persistentes costumam vir como root) e inicia o servidor sem privilégios.
set -e
mkdir -p /data
chown -R app:app /data 2>/dev/null || true
exec setpriv --reuid=app --regid=app --init-groups sh -c "python init_db.py && exec python server.py"