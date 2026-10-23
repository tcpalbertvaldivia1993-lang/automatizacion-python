# Automatización de limpieza de datos de ventas

[![Pruebas](https://github.com/tcpalbertvaldivia1993-lang/automatizacion-python/actions/workflows/pruebas.yml/badge.svg)](https://github.com/tcpalbertvaldivia1993-lang/automatizacion-python/actions/workflows/pruebas.yml)

Herramienta en Python que recibe archivos de ventas (CSV o Excel), limpia los datos,
detecta errores y genera automáticamente un informe con los indicadores principales.
Puede procesar una carpeta entera, ejecutarse sola cada semana y enviar los informes por email.

## Qué hace

1. **Limpieza**
   - Quita espacios innecesarios (al principio, al final y dobles espacios).
   - Elimina filas duplicadas.
   - Elimina fechas vacías, con formato distinto de `AAAA-MM-DD`, imposibles
     (`2026-13-45`, `2026-02-30`) o futuras.
   - Elimina cantidades vacías, no numéricas, decimales o 0.
     Una cantidad **negativa** es una devolución o cancelación: no se elimina,
     se resta de las ventas y no cuenta como pedido.
   - Elimina precios vacíos, mal escritos (`abc`) o ≤ 0.
     Los formatos recuperables como `7,50` o `899.99 €` se corrigen en lugar de eliminarse.
2. **Indicadores**: ventas totales netas, devoluciones y cancelaciones,
   número de pedidos y valor medio por pedido.
   Además, gráficos de **ventas por producto** (los 10 que más venden si hay
   muchos) y **ventas por día** (por mes si los datos abarcan más de dos meses).
   Los periodos sin ventas aparecen con 0, y el primer o último mes con datos
   incompletos se marca con `*` y un color más claro. Cada gráfico lleva su tabla de datos.
3. **Resultados** (carpeta `resultados/`, con una subcarpeta por archivo):
   - `<archivo>/ventas_limpio.csv`: datos limpios, con la columna `importe`.
   - `<archivo>/filas_descartadas.csv`: cada fila eliminada con su motivo.
   - `<archivo>/informe.html`: informe con indicadores, gráficos y calidad de los datos.
     Es un solo archivo (los gráficos van dentro): se abre con doble clic en cualquier
     navegador, se puede enviar por email y se adapta al móvil. Números en formato español.
   - `<archivo>/graficos/`: los gráficos en PNG.
   - `resumen.html`: al procesar una carpeta, una tabla que compara todos los archivos.
   - `registro.log`: registro de todas las ejecuciones.
   - `historial.csv`: totales de cada ejecución programada, para detectar cambios bruscos.

## Estructura

```
datos/ventas_ejemplo.csv        CSV de ejemplo con errores a propósito
limpieza.py                     funciones de limpieza e indicadores
graficos.py                     gráficos del informe (matplotlib)
plantillas/                     diseño HTML de los informes (Jinja2)
formato.py                      números en formato español: 1.234,56
enviar_email.py                 envío de los informes por email (SMTP)
alertas.py                      historial de ejecuciones y aviso de cambios bruscos
.env.ejemplo                    plantilla de la configuración del email
preparar_online_retail.py       descarga y adapta un conjunto de datos real
main.py                         ejecución automática (un archivo o una carpeta)
ejecutar_programado.sh          lo que ejecuta la tarea programada: procesa datos/entrada/
programar_windows.ps1           crea la tarea en el Programador de tareas de Windows
datos/entrada/                  carpeta de entrada para la ejecución programada
notebooks/analisis_ventas.ipynb el mismo proceso paso a paso
tests/                          pruebas con pytest
.github/workflows/pruebas.yml   ejecuta las pruebas en GitHub con cada push
```

## Cómo usarlo

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt

venv/bin/python main.py                        # usa el CSV de ejemplo
venv/bin/python main.py ruta/a/mis_ventas.csv  # un CSV
venv/bin/python main.py ruta/a/mis_ventas.xlsx # un Excel
venv/bin/python main.py ruta/a/carpeta/        # todos los CSV y Excel de una carpeta
venv/bin/python main.py ventas.csv --moneda £   # otra moneda en el informe
venv/bin/python main.py --enviar-email          # enviar los informes por email

venv/bin/jupyter notebook notebooks/          # abrir el notebook
venv/bin/python -m pytest                     # ejecutar las pruebas
```

El archivo debe tener las columnas:
`id_pedido, fecha, cliente, producto, cantidad, precio_unitario`.
Las fechas pueden ir con o sin hora (`2026-09-01` o `2026-09-01 08:26:00`).

## Probarlo con datos reales

`preparar_online_retail.py` descarga el conjunto de datos público
[Online Retail (UCI)](https://archive.ics.uci.edu/dataset/352/online+retail):
541.909 ventas reales de una tienda online británica (2010-2011). Después:

- Aparta las 2.912 filas que no son productos (envíos, comisiones y ajustes,
  identificados por su código) en `datos/reales/online_retail_excluidas.csv`.
- Cambia los nombres de las columnas a los que espera la herramienta.

Las cancelaciones de este conjunto (pedidos que empiezan por `C`) tienen cantidad
negativa, así que la herramienta las resta de las ventas automáticamente.
Los importes están en libras, así que conviene usar `--moneda £`.

```bash
venv/bin/python preparar_online_retail.py              # ~2 min, solo la primera vez
venv/bin/python main.py datos/reales/online_retail.csv --moneda £ # ~25 s
```

Los datos reales se guardan en `datos/reales/`, que no se sube a GitHub.

## Ejecución programada

Deja los archivos de ventas en `datos/entrada/`. Cada lunes a las 08:00, el
**Programador de tareas de Windows** abre WSL y ejecuta `ejecutar_programado.sh`, que:

1. procesa todos los CSV y Excel de `datos/entrada/`,
2. genera sus informes y `resultados/resumen.html`,
3. mueve los que salieron bien a `datos/entrada/procesados/` (los que fallan se quedan,
   para revisarlos con `resultados/registro.log`),
4. compara los totales con los del lunes anterior (`resultados/historial.csv`),
5. envía un email con los indicadores de cada archivo, sus informes HTML adjuntos y
   un aviso si las ventas o los pedidos cambiaron bruscamente.

Si el PC estaba apagado el lunes a las 08:00, la tarea se ejecuta en cuanto se enciende.
Se usa el Programador de tareas y no `cron` porque `cron` solo funciona con WSL abierto.

Para crear la tarea (una sola vez, desde WSL):

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w programar_windows.ps1)"
```

Para verla o cambiarla: menú Inicio → "Programador de tareas" →
"automatizacion-python - informe semanal".

## Envío por email

1. Copia la plantilla de configuración: `cp .env.ejemplo .env`
2. Rellena `.env` con el servidor, tu cuenta, la contraseña y el destinatario.
   Con Gmail hace falta una **contraseña de aplicación**
   ([cómo crearla](https://myaccount.google.com/apppasswords)), no tu contraseña normal.
3. Pruébalo: `venv/bin/python main.py --enviar-email`

El email lleva en el cuerpo los indicadores de cada archivo (y avisa si alguno falló), y
los informes completos como adjuntos HTML. Los gráficos van en los adjuntos y no en el
cuerpo, porque Gmail y otros programas de correo bloquean las imágenes incrustadas.

`.env` contiene tu contraseña: está en `.gitignore` y **nunca** se sube a GitHub.

## Aviso de cambios bruscos

Con `--historial`, cada ejecución guarda sus totales (ventas netas, devoluciones,
pedidos y valor medio) en una fila de un CSV. La siguiente ejecución los compara con
la anterior: si las **ventas netas** o los **pedidos** suben o bajan un 20 % o más,
es un cambio brusco.

```bash
venv/bin/python main.py datos/entrada --historial resultados/historial.csv
venv/bin/python main.py datos/entrada --historial resultados/historial.csv --umbral 30
```

- El registro muestra un aviso: `Cambio brusco en ventas netas: -31.2 %`.
- Con `--enviar-email`, el email incluye un recuadro con la comparación (en rojo si
  hay un cambio brusco) y el asunto lo avisa: `Informe de ventas · 23/10/2026 · ⚠ Ventas netas -31 %`.

La ejecución programada ya usa `resultados/historial.csv`, así que cada lunes se compara
con el lunes anterior. Las ejecuciones a mano sin `--historial` no se guardan, para que
las pruebas no estropeen la comparación. La primera vez no hay nada con qué comparar.
