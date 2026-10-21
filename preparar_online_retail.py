"""Prepara el conjunto de datos real "Online Retail" (UCI) para usarlo con main.py.

Son ventas reales de una tienda online del Reino Unido entre 2010 y 2011
(unas 540.000 filas). Fuente: https://archive.ics.uci.edu/dataset/352/online+retail

Los datos reales casi nunca vienen con las columnas que espera nuestra herramienta,
así que este script:
  1. Descarga el archivo Excel (solo la primera vez).
  2. Aparta las filas que no son ventas de productos (envíos, comisiones, ajustes)
     y las guarda en datos/reales/online_retail_excluidas.csv para poder revisarlas.
  3. Cambia los nombres de las columnas a los nuestros.
  4. Lo guarda como CSV en datos/reales/online_retail.csv

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
CSV_EXCLUIDAS = CARPETA / "online_retail_excluidas.csv"

# Códigos (StockCode) que en este conjunto de datos no son productos.
# Se descubrieron revisando los códigos que no siguen el formato habitual "12345" o "12345A".
NO_SON_PRODUCTOS = {
    "POST": "envío",            # POSTAGE
    "DOT": "envío",             # DOTCOM POSTAGE
    "C2": "envío",              # CARRIAGE
    "BANK CHARGES": "comisión",
    "AMAZONFEE": "comisión",
    "CRUK": "comisión",         # CRUK Commission
    "M": "ajuste",              # Manual
    "m": "ajuste",              # Manual
    "D": "ajuste",              # Discount
    "B": "ajuste",              # Adjust bad debt
    "S": "ajuste",              # SAMPLES
}

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
    """Lee el Excel, aparta lo que no son productos, renombra las columnas y guarda el CSV."""
    print("Leyendo el Excel (puede tardar un par de minutos)...")
    # dtype=str: leemos todo como texto, igual que main.py, para no ocultar errores.
    df = pd.read_excel(EXCEL, dtype=str)

    no_es_producto = df["StockCode"].isin(NO_SON_PRODUCTOS.keys())
    excluidas = df[no_es_producto].copy()
    excluidas["tipo"] = excluidas["StockCode"].map(NO_SON_PRODUCTOS)
    excluidas.to_csv(CSV_EXCLUIDAS, index=False)
    print(f"{len(excluidas):,} filas apartadas por no ser productos (en {CSV_EXCLUIDAS}):")
    for tipo, n in excluidas["tipo"].value_counts().items():
        print(f"  - {tipo}: {n:,}")

    df = df[~no_es_producto][list(COLUMNAS)].rename(columns=COLUMNAS)
    df.to_csv(CSV_SALIDA, index=False)
    print(f"{len(df):,} filas guardadas en {CSV_SALIDA}")


if __name__ == "__main__":
    descargar()
    convertir()
