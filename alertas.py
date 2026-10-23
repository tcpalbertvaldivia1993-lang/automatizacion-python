"""Avisos de cambios bruscos: compara cada ejecución con la anterior.

Cada ejecución guarda sus totales en un historial (un CSV con una fila por
ejecución). La siguiente vez se comparan los totales nuevos con la última fila:
si las ventas o los pedidos suben o bajan más que el umbral, es un cambio brusco.
"""

from datetime import datetime

import pandas as pd

UMBRAL_POR_DEFECTO = 20  # en %
# Indicadores que se vigilan y el nombre con el que aparecen en el aviso.
VIGILADOS = {"ventas_totales": "Ventas netas", "pedidos": "Pedidos"}


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


def leer_ultima_ejecucion(ruta):
    """Devuelve la última fila del historial como diccionario, o None si aún no hay."""
    if not ruta.exists():
        return None
    historial = pd.read_csv(ruta)
    if historial.empty:
        return None
    return historial.iloc[-1].to_dict()


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
