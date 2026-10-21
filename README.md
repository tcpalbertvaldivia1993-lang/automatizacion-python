# Automatización de limpieza de datos de ventas

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
3. **Resultados** (carpeta `resultados/`):
   - `ventas_limpio.csv`: datos limpios, con la columna `importe`.
   - `filas_descartadas.csv`: cada fila eliminada con su motivo.
   - `informe.md`: resumen con indicadores y calidad de los datos.
   - `registro.log`: registro de cada ejecución.

## Estructura

```
datos/ventas_ejemplo.csv        CSV de ejemplo con errores a propósito
limpieza.py                     funciones de limpieza e indicadores
main.py                         ejecución automática
notebooks/analisis_ventas.ipynb el mismo proceso paso a paso
tests/                          pruebas con pytest
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
