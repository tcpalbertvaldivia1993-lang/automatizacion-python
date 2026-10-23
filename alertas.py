"""Avisos de cambios bruscos: compara cada ejecución con la anterior.

Cada ejecución guarda sus totales en un historial (un CSV con una fila por
ejecución). La siguiente vez se comparan los totales nuevos con la última fila:
si las ventas o los pedidos suben o bajan más que el umbral, es un cambio brusco.

Además se guardan las ventas de cada producto en otro historial, para avisar si
alguno de los que más venden cambia bruscamente aunque el total se mantenga.
"""

from datetime import datetime

import pandas as pd

UMBRAL_POR_DEFECTO = 20  # en %
# Indicadores que se vigilan y el nombre con el que aparecen en el aviso.
VIGILADOS = {"ventas_totales": "Ventas netas", "pedidos": "Pedidos"}

# Cada producto por separado varía mucho más que el total, así que su umbral es mayor.
UMBRAL_PRODUCTO_POR_DEFECTO = 50  # en %
# Solo se vigilan los que más vendieron la vez anterior: que un producto pase
# de vender 10 € a 3 € no merece un aviso.
MAX_PRODUCTOS_VIGILADOS = 10


def sumar_indicadores(lista_indicadores):
    """Junta los indicadores de varios archivos en unos totales de la ejecución."""
    ventas = round(sum(i["ventas_totales"] for i in lista_indicadores), 2)
    pedidos = sum(i["pedidos"] for i in lista_indicadores)
    return {
        "ventas_totales": ventas,
        "devoluciones": round(sum(i["devoluciones"] for i in lista_indicadores), 2),
        "pedidos": pedidos,
        "valor_medio_pedido": round(ventas / pedidos, 2) if pedidos else 0.0,
    }


def leer_historial(ruta):
    """Lee el historial completo (una fila por ejecución). Vacío si aún no existe."""
    if not ruta.exists():
        return pd.DataFrame()
    return pd.read_csv(ruta)


def leer_ultima_ejecucion(ruta):
    """Devuelve la última fila del historial como diccionario, o None si aún no hay."""
    historial = leer_historial(ruta)
    if historial.empty:
        return None
    return historial.iloc[-1].to_dict()


def marcar_cambios_bruscos(historial, umbral=UMBRAL_POR_DEFECTO):
    """Añade al historial el % de cambio de las ventas respecto a la fila anterior
    y si ese cambio es brusco. Sirve para colorear el gráfico de evolución."""
    historial = historial.copy()
    anterior = historial["ventas_totales"].shift()
    historial["cambio"] = (100 * (historial["ventas_totales"] - anterior) / anterior).where(anterior > 0)
    historial["brusco"] = historial["cambio"].abs() >= umbral  # NaN (sin dato) da False
    return historial


def guardar_ejecucion(ruta, totales):
    """Añade los totales de esta ejecución al final del historial."""
    fila = pd.DataFrame([{"fecha": f"{datetime.now():%Y-%m-%d %H:%M}", **totales}])
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fila.to_csv(ruta, mode="a", header=not ruta.exists(), index=False)


def comparar(actual, anterior, umbral=UMBRAL_POR_DEFECTO):
    """Compara los indicadores vigilados con la ejecución anterior.

    Devuelve una lista con un diccionario por indicador. "cambio" es el % de
    variación (None si antes era 0 o negativo y no tiene sentido calcularlo) y
    "brusco" indica si el cambio supera el umbral, hacia arriba o hacia abajo.
    """
    cambios = []
    for clave, nombre in VIGILADOS.items():
        antes, ahora = float(anterior[clave]), float(actual[clave])
        cambio = 100 * (ahora - antes) / antes if antes > 0 else None
        cambios.append({
            "clave": clave,
            "nombre": nombre,
            "anterior": antes,
            "actual": ahora,
            "cambio": cambio,
            "brusco": cambio is not None and abs(cambio) >= umbral,
        })
    return cambios


def ruta_historial_productos(ruta_historial):
    """El historial por producto va junto al de totales: historial.csv -> historial_productos.csv."""
    return ruta_historial.with_name(f"{ruta_historial.stem}_productos.csv")


def guardar_productos(ruta, ventas_por_producto):
    """Añade al historial por producto una fila por cada producto de esta ejecución."""
    filas = pd.DataFrame({
        # Con segundos, para distinguir dos ejecuciones seguidas al leer la última.
        "fecha": f"{datetime.now():%Y-%m-%d %H:%M:%S}",
        "producto": ventas_por_producto.index,
        "ventas": ventas_por_producto.round(2).values,
    })
    ruta.parent.mkdir(parents=True, exist_ok=True)
    filas.to_csv(ruta, mode="a", header=not ruta.exists(), index=False)


def leer_productos_anteriores(ruta):
    """Devuelve las ventas por producto de la última ejecución guardada, o None si no hay."""
    if not ruta.exists():
        return None
    historial = pd.read_csv(ruta, dtype={"producto": str})
    if historial.empty:
        return None
    ultima = historial[historial["fecha"] == historial["fecha"].iloc[-1]]
    return ultima.set_index("producto")["ventas"]


def comparar_productos(actual, anterior, umbral=UMBRAL_PRODUCTO_POR_DEFECTO,
                       maximo=MAX_PRODUCTOS_VIGILADOS):
    """Busca cambios bruscos en los productos que más vendieron la vez anterior.

    actual y anterior son las ventas por producto (Series con el producto como índice).
    Un producto que ya no aparece cuenta como 0 (-100 %). Devuelve solo los cambios
    bruscos, de la bajada más fuerte a la subida más fuerte.
    """
    vigilados = anterior[anterior > 0].nlargest(maximo)
    cambios = []
    for producto, antes in vigilados.items():
        ahora = float(actual.get(producto, 0.0))
        cambio = 100 * (ahora - antes) / antes
        if abs(cambio) >= umbral:
            cambios.append({"producto": producto, "anterior": float(antes),
                            "actual": ahora, "cambio": cambio})
    return sorted(cambios, key=lambda c: c["cambio"])
