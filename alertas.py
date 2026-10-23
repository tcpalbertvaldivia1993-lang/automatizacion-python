"""Avisos de cambios bruscos: compara cada ejecución con las anteriores.

Cada ejecución guarda sus totales en un historial (un CSV con una fila por
ejecución). La siguiente vez se comparan los totales nuevos con la MEDIA de las
últimas 4 ejecuciones: si las ventas o los pedidos suben o bajan más que el
umbral, es un cambio brusco. Se usa la media y no solo la semana anterior porque
las ventas varían mucho de una semana a otra: con datos reales, comparar solo con
la anterior daba aviso casi todas las semanas.

Además se guardan las ventas de cada producto en otro historial, para informar
de cuáles de los que más venden han cambiado mucho. Eso no es un aviso, solo
información: un solo pedido grande ya cambia mucho las ventas de un producto.
"""

from datetime import datetime

import pandas as pd

UMBRAL_POR_DEFECTO = 30  # en %
SEMANAS_REFERENCIA = 4   # se compara con la media de las últimas 4 ejecuciones
# Indicadores que se vigilan y el nombre con el que aparecen en el aviso.
VIGILADOS = {"ventas_totales": "Ventas netas", "pedidos": "Pedidos"}

# Cada producto por separado varía mucho más que el total, así que su umbral es mayor.
UMBRAL_PRODUCTO_POR_DEFECTO = 50  # en %
# Solo se miran los que más venden de media: que un producto pase de vender
# 10 € a 3 € no interesa.
MAX_PRODUCTOS_VIGILADOS = 10
MAX_PRODUCTOS_MOSTRADOS = 5  # en el email, los 5 que más cambiaron


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


def leer_referencia(ruta, semanas=SEMANAS_REFERENCIA):
    """Calcula la media de los indicadores vigilados en las últimas ejecuciones.

    Devuelve un diccionario con esas medias y cuántas ejecuciones se usaron
    ("semanas", menos de 4 al principio), o None si aún no hay historial.
    """
    ultimas = leer_historial(ruta).tail(semanas)
    if ultimas.empty:
        return None
    referencia = {clave: float(ultimas[clave].mean()) for clave in VIGILADOS}
    referencia["semanas"] = len(ultimas)
    return referencia


def marcar_cambios_bruscos(historial, umbral=UMBRAL_POR_DEFECTO, semanas=SEMANAS_REFERENCIA):
    """Añade al historial el % de cambio de las ventas respecto a la media de las
    ejecuciones anteriores y si ese cambio es brusco. Sirve para colorear el
    gráfico de evolución con el mismo criterio que el aviso."""
    historial = historial.copy()
    # shift: cada fila se compara con las de antes, no consigo misma.
    media = historial["ventas_totales"].shift().rolling(semanas, min_periods=1).mean()
    historial["cambio"] = (100 * (historial["ventas_totales"] - media) / media).where(media > 0)
    historial["brusco"] = historial["cambio"].abs() >= umbral  # NaN (sin dato) da False
    return historial


def guardar_ejecucion(ruta, totales):
    """Añade los totales de esta ejecución al final del historial."""
    fila = pd.DataFrame([{"fecha": f"{datetime.now():%Y-%m-%d %H:%M}", **totales}])
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fila.to_csv(ruta, mode="a", header=not ruta.exists(), index=False)


def comparar(actual, referencia, umbral=UMBRAL_POR_DEFECTO):
    """Compara los indicadores vigilados con la media de las ejecuciones anteriores.

    Devuelve una lista con un diccionario por indicador. "cambio" es el % de
    variación (None si la media era 0 o negativa y no tiene sentido calcularlo) y
    "brusco" indica si el cambio supera el umbral, hacia arriba o hacia abajo.
    """
    cambios = []
    for clave, nombre in VIGILADOS.items():
        media, ahora = float(referencia[clave]), float(actual[clave])
        cambio = 100 * (ahora - media) / media if media > 0 else None
        cambios.append({
            "clave": clave,
            "nombre": nombre,
            "referencia": media,
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
        # Con segundos, para distinguir dos ejecuciones seguidas.
        "fecha": f"{datetime.now():%Y-%m-%d %H:%M:%S}",
        "producto": ventas_por_producto.index,
        "ventas": ventas_por_producto.round(2).values,
    })
    ruta.parent.mkdir(parents=True, exist_ok=True)
    filas.to_csv(ruta, mode="a", header=not ruta.exists(), index=False)


def leer_productos_referencia(ruta, semanas=SEMANAS_REFERENCIA):
    """Devuelve la media de ventas de cada producto en las últimas ejecuciones,
    o None si aún no hay historial. Un producto que no se vendió una semana cuenta 0."""
    if not ruta.exists():
        return None
    historial = pd.read_csv(ruta, dtype={"producto": str})
    if historial.empty:
        return None
    fechas = historial["fecha"].drop_duplicates().tail(semanas)
    ultimas = historial[historial["fecha"].isin(fechas)]
    tabla = ultimas.pivot_table(index="fecha", columns="producto", values="ventas", aggfunc="sum")
    return tabla.fillna(0).mean()


def comparar_productos(actual, referencia, umbral=UMBRAL_PRODUCTO_POR_DEFECTO,
                       maximo=MAX_PRODUCTOS_VIGILADOS, mostrar=MAX_PRODUCTOS_MOSTRADOS):
    """Busca los productos que más han cambiado entre los que más venden de media.

    actual y referencia son las ventas por producto (Series con el producto como
    índice). Un producto que no se vendió esta vez cuenta como 0 (-100 %). Devuelve
    como mucho `mostrar` productos que cambiaron al menos el umbral, del cambio
    más grande al más pequeño (sea subida o bajada).
    """
    vigilados = referencia[referencia > 0].nlargest(maximo)
    cambios = []
    for producto, media in vigilados.items():
        ahora = float(actual.get(producto, 0.0))
        cambio = 100 * (ahora - media) / media
        if abs(cambio) >= umbral:
            cambios.append({"producto": producto, "referencia": float(media),
                            "actual": ahora, "cambio": cambio})
    return sorted(cambios, key=lambda c: abs(c["cambio"]), reverse=True)[:mostrar]
