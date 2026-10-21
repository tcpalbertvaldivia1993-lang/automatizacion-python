#!/bin/bash
# Procesa todos los archivos que haya en datos/entrada/ y mueve los correctos
# a datos/entrada/procesados/. Pensado para ejecutarse con cron.
#
# cron arranca en otra carpeta, así que primero vamos a la del proyecto
# (main.py usa rutas relativas como "resultados/").
cd "$(dirname "$0")" || exit 1
mkdir -p resultados

# Todo queda en resultados/registro.log; cron.log guarda además cualquier
# error inesperado de Python que no llegue a escribirse en el registro.
venv/bin/python main.py datos/entrada --mover-procesados >> resultados/cron.log 2>&1
