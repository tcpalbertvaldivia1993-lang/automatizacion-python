"""Prepara el conjunto de datos real "Online Retail" (UCI) para usarlo con main.py.

Son ventas reales de una tienda online del Reino Unido entre 2010 y 2011
(unas 540.000 filas). Fuente: https://archive.ics.uci.edu/dataset/352/online+retail

Los datos reales casi nunca vienen con las columnas que espera nuestra herramienta,
así que este script:
  1. Descarga el archivo Excel (solo la primera vez).
  2. Cambia los nombres de las columnas a los nuestros.
  3. Lo guarda como CSV en datos/reales/online_retail.csv

Uso:
    venv/bin/python preparar_online_retail.py
    venv/bin/python main.py datos/reales/online_retail.csv
"""

import io
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

URL = "https://archive.ics.uci.edu/static/public/352/online+retail.zip"
CARPETA = Path("datos/reales")
EXCEL = CARPETA / "Online Retail.xlsx"
CSV_SALIDA = CARPETA / "online_retail.csv"

# Columna del archivo original -> columna que espera nuestra herramienta.
COLUMNAS = {
    "InvoiceNo": "id_pedido",
    "InvoiceDate": "fecha",
    "CustomerID": "cliente",
    "Description": "producto",
    "Quantity": "cantidad",
    "UnitPrice": "precio_unitario",
}


def descargar():
    """Descarga y descomprime el Excel si todavía no existe."""
    if EXCEL.exists():
        print(f"Ya descargado: {EXCEL}")
        return
    CARPETA.mkdir(parents=True, exist_ok=True)
    print("Descargando (unos 23 MB)...")
    with urllib.request.urlopen(URL) as respuesta:
        contenido = respuesta.read()
    with zipfile.ZipFile(io.BytesIO(contenido)) as archivo_zip:
        archivo_zip.extract(EXCEL.name, CARPETA)
    print(f"Guardado en {EXCEL}")


def convertir():
    """Lee el Excel, renombra las columnas y guarda el CSV."""
    print("Leyendo el Excel (puede tardar un par de minutos)...")
    # dtype=str: leemos todo como texto, igual que main.py, para no ocultar errores.
    df = pd.read_excel(EXCEL, dtype=str)
    df = df[list(COLUMNAS)].rename(columns=COLUMNAS)
    df.to_csv(CSV_SALIDA, index=False)
    print(f"{len(df):,} filas guardadas en {CSV_SALIDA}")


if __name__ == "__main__":
    descargar()
    convertir()
