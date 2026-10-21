# Automatización de limpieza de datos de ventas

[![Pruebas](https://github.com/tcpalbertvaldivia1993-lang/automatizacion-python/actions/workflows/pruebas.yml/badge.svg)](https://github.com/tcpalbertvaldivia1993-lang/automatizacion-python/actions/workflows/pruebas.yml)

Herramienta en Python que recibe un CSV de ventas, limpia los datos, detecta errores
y genera automáticamente un informe con los indicadores principales.

## Qué hace

1. **Limpieza**
   - Quita espacios innecesarios (al principio, al final y dobles espacios).
   - Elimina filas duplicadas.
   - Elimina fechas vacías, con formato distinto de `AAAA-MM-DD`, imposibles
     (`2026-13-45`, `2026-02-30`) o futuras.
   - Elimina cantidades vacías, no numéricas, decimales o ≤ 0.
   - Elimina precios vacíos, mal escritos (`abc`) o ≤ 0.
     Los formatos recuperables como `7,50` o `899.99 €` se corrigen en lugar de eliminarse.
2. **Indicadores**: ventas totales, número de pedidos y valor medio por pedido.
   Además, gráficos de **ventas por producto** (los 10 que más venden si hay
   muchos) y **ventas por día** (por mes si los datos abarcan más de dos meses).
   Los periodos sin ventas aparecen con 0. Cada gráfico lleva su tabla de datos.
3. **Resultados** (carpeta `resultados/`):
   - `ventas_limpio.csv`: datos limpios, con la columna `importe`.
   - `filas_descartadas.csv`: cada fila eliminada con su motivo.
   - `informe.md`: resumen con indicadores, gráficos y calidad de los datos.
   - `graficos/`: los gráficos en PNG.
   - `registro.log`: registro de cada ejecución.

## Estructura

```
datos/ventas_ejemplo.csv        CSV de ejemplo con errores a propósito
limpieza.py                     funciones de limpieza e indicadores
graficos.py                     gráficos del informe (matplotlib)
preparar_online_retail.py       descarga y adapta un conjunto de datos real
main.py                         ejecución automática
notebooks/analisis_ventas.ipynb el mismo proceso paso a paso
tests/                          pruebas con pytest
.github/workflows/pruebas.yml   ejecuta las pruebas en GitHub con cada push
```

## Cómo usarlo

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt

venv/bin/python main.py                       # usa el CSV de ejemplo
venv/bin/python main.py ruta/a/mis_ventas.csv # con tu propio archivo

venv/bin/jupyter notebook notebooks/          # abrir el notebook
venv/bin/python -m pytest                     # ejecutar las pruebas
```

El CSV debe tener las columnas:
`id_pedido, fecha, cliente, producto, cantidad, precio_unitario`.
Las fechas pueden ir con o sin hora (`2026-09-01` o `2026-09-01 08:26:00`).

## Probarlo con datos reales

`preparar_online_retail.py` descarga el conjunto de datos público
[Online Retail (UCI)](https://archive.ics.uci.edu/dataset/352/online+retail):
541.909 ventas reales de una tienda online británica (2010-2011). Después
cambia los nombres de sus columnas a los que espera la herramienta.

```bash
venv/bin/python preparar_online_retail.py              # ~2 min, solo la primera vez
venv/bin/python main.py datos/reales/online_retail.csv # ~25 s
```

Los datos reales se guardan en `datos/reales/`, que no se sube a GitHub.
