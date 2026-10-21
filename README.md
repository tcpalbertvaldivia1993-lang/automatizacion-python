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
541.909 ventas reales de una tienda online británica (2010-2011). Después:

- Aparta las 2.912 filas que no son productos (envíos, comisiones y ajustes,
  identificados por su código) en `datos/reales/online_retail_excluidas.csv`.
- Cambia los nombres de las columnas a los que espera la herramienta.

Las cancelaciones de este conjunto (pedidos que empiezan por `C`) tienen cantidad
negativa, así que la herramienta las resta de las ventas automáticamente.
Los importes están en libras (£), aunque el informe muestra el símbolo €.

```bash
venv/bin/python preparar_online_retail.py              # ~2 min, solo la primera vez
venv/bin/python main.py datos/reales/online_retail.csv # ~25 s
```

Los datos reales se guardan en `datos/reales/`, que no se sube a GitHub.
