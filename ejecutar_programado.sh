#!/bin/bash
# Procesa todos los archivos que haya en datos/entrada/, mueve los correctos
# a datos/entrada/procesados/ y envía los informes por email (configuración en .env). Lo lanza el Programador de tareas de Windows
# (ver programar_windows.ps1), aunque también serviría con cron.
#
# La tarea programada arranca en otra carpeta, así que primero vamos a la del proyecto
# (main.py usa rutas relativas como "resultados/").
cd "$(dirname "$0")" || exit 1
mkdir -p resultados

# Todo queda en resultados/registro.log; cron.log guarda además cualquier
# error inesperado de Python que no llegue a escribirse en el registro.
venv/bin/python main.py datos/entrada --mover-procesados --enviar-email >> resultados/cron.log 2>&1
