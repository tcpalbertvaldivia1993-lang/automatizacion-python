"""Funciones para limpiar los datos de ventas, detectar errores y calcular indicadores.

Este módulo lo usan tanto main.py (ejecución automática) como el notebook.
"""

import pandas as pd

COLUMNAS_OBLIGATORIAS = ["id_pedido", "fecha", "cliente", "producto", "cantidad", "precio_unitario"]


def comprobar_columnas(df):
    """Lanza un error si al CSV le falta alguna columna necesaria."""
    faltan = [c for c in COLUMNAS_OBLIGATORIAS if c not in df.columns]
    if faltan:
        raise ValueError(f"Faltan columnas en el CSV: {', '.join(faltan)}")


def quitar_espacios(df):
    """Quita espacios al principio y al final, y deja un solo espacio entre palabras."""
    df = df.copy()
    for columna in df.columns:
        df[columna] = df[columna].str.strip().str.replace(r"\s+", " ", regex=True)
    return df


def convertir_precio(texto):
    """Convierte un precio escrito como texto a número.

    Acepta formatos recuperables como "7,50" o "899.99 €".
    Devuelve None si el precio no se puede entender (por ejemplo "abc").
    """
    if pd.isna(texto) or texto == "":
        return None
    limpio = texto.replace("€", "").replace(" ", "").replace(",", ".")
    try:
        return float(limpio)
    except ValueError:
        return None


def convertir_cantidad(texto):
    """Convierte una cantidad a número entero. Devuelve None si no es válida."""
    if pd.isna(texto) or texto == "":
        return None
    try:
        numero = float(texto)
    except ValueError:
        return None
    if not numero.is_integer():
        return None
    return int(numero)


def limpiar_ventas(df):
    """Limpia el DataFrame de ventas.

    Devuelve dos DataFrames:
      - limpio: las filas correctas, con cantidad y precio ya como números.
      - descartadas: las filas eliminadas, con una columna "motivo".
    """
    comprobar_columnas(df)
    df = quitar_espacios(df)

    descartes = []

    # 1. Filas duplicadas (se buscan después de quitar espacios,
    #    así " Ana López " y "Ana López" cuentan como iguales).
    es_duplicada = df.duplicated(keep="first")
    duplicadas = df[es_duplicada].copy()
    duplicadas["motivo"] = "fila duplicada"
    descartes.append(duplicadas)
    df = df[~es_duplicada].copy()

    # 2. Cantidades vacías o inválidas.
    df["cantidad_num"] = df["cantidad"].apply(convertir_cantidad)
    cantidad_mala = df["cantidad_num"].isna() | (df["cantidad_num"] <= 0)
    malas = df[cantidad_mala].copy()
    malas["motivo"] = "cantidad vacía o inválida"
    descartes.append(malas)
    df = df[~cantidad_mala].copy()

    # 3. Precios mal escritos, vacíos o no positivos.
    df["precio_num"] = df["precio_unitario"].apply(convertir_precio)
    precio_malo = df["precio_num"].isna() | (df["precio_num"] <= 0)
    malos = df[precio_malo].copy()
    malos["motivo"] = "precio vacío o mal escrito"
    descartes.append(malos)
    df = df[~precio_malo].copy()

    # Dejamos las columnas finales con los valores ya convertidos.
    df["cantidad"] = df["cantidad_num"].astype(int)
    df["precio_unitario"] = df["precio_num"]
    df["importe"] = (df["cantidad"] * df["precio_unitario"]).round(2)
    limpio = df.drop(columns=["cantidad_num", "precio_num"]).reset_index(drop=True)

    descartadas = pd.concat(descartes)[COLUMNAS_OBLIGATORIAS + ["motivo"]]
    return limpio, descartadas.reset_index(drop=True)


def calcular_indicadores(limpio):
    """Calcula ventas totales, número de pedidos y valor medio por pedido."""
    ventas_totales = round(float(limpio["importe"].sum()), 2)
    pedidos = int(limpio["id_pedido"].nunique())
    valor_medio = round(ventas_totales / pedidos, 2) if pedidos else 0.0
    return {
        "ventas_totales": ventas_totales,
        "pedidos": pedidos,
        "valor_medio_pedido": valor_medio,
    }
