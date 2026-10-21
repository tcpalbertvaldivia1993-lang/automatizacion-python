"""Gráficos del informe: ventas por producto y ventas a lo largo del tiempo.

Cada función guarda una imagen PNG y devuelve (título, datos), para poder
mostrar también la tabla en el informe. El nombre del índice de los datos
("Producto", "Día" o "Mes") sirve de cabecera de la tabla.
"""

import matplotlib

matplotlib.use("Agg")  # dibuja en archivos, sin abrir ventanas
import matplotlib.pyplot as plt
import pandas as pd

# Colores del gráfico: un solo color para los datos y grises suaves para lo demás.
COLOR_BARRAS = "#2a78d6"
COLOR_FONDO = "#fcfcfb"
COLOR_TEXTO = "#0b0b0b"
COLOR_TEXTO_SUAVE = "#52514e"
COLOR_REJILLA = "#e4e3df"

# Con datos reales puede haber miles de productos y años de fechas:
MAX_PRODUCTOS = 10      # el gráfico de productos muestra solo los que más venden
MAX_DIAS_POR_DIA = 62   # con más días que esto, las ventas se agrupan por mes


def _preparar_ejes(titulo, ancho=8, alto=4.5):
    """Crea una figura con el estilo común a todos los gráficos."""
    figura, ejes = plt.subplots(figsize=(ancho, alto), dpi=120)
    figura.patch.set_facecolor(COLOR_FONDO)
    ejes.set_facecolor(COLOR_FONDO)
    ejes.set_title(titulo, loc="left", fontsize=13, color=COLOR_TEXTO, pad=12)
    for lado in ["top", "right", "left"]:
        ejes.spines[lado].set_visible(False)
    ejes.spines["bottom"].set_color(COLOR_REJILLA)
    ejes.tick_params(colors=COLOR_TEXTO_SUAVE, length=0)
    ejes.set_axisbelow(True)
    return figura, ejes


def _guardar(figura, ruta):
    figura.tight_layout()
    figura.savefig(ruta, facecolor=COLOR_FONDO)
    plt.close(figura)


def grafico_ventas_por_producto(limpio, ruta):
    """Barras horizontales con el importe vendido de cada producto, de mayor a menor.

    Si hay más de MAX_PRODUCTOS productos, solo se muestran los que más venden.
    """
    total_productos = limpio["producto"].nunique()
    datos = limpio.groupby("producto")["importe"].sum().nlargest(MAX_PRODUCTOS).sort_values()
    datos.index.name = "Producto"
    if total_productos > MAX_PRODUCTOS:
        titulo = f"Los {MAX_PRODUCTOS} productos más vendidos (de {total_productos})"
    else:
        titulo = "Ventas por producto"

    figura, ejes = _preparar_ejes(f"{titulo} (€)", alto=0.45 * len(datos) + 1.2)
    ejes.barh(datos.index, datos.values, color=COLOR_BARRAS, height=0.7)
    ejes.grid(axis="x", color=COLOR_REJILLA, linewidth=0.8)
    ejes.spines["bottom"].set_visible(False)
    # Etiqueta con el valor al final de cada barra.
    for posicion, valor in enumerate(datos.values):
        ejes.text(valor, posicion, f"  {valor:,.2f}", va="center", fontsize=9, color=COLOR_TEXTO_SUAVE)
    ejes.set_xlim(0, datos.max() * 1.18)
    ejes.xaxis.set_major_formatter("{x:,.0f}")
    _guardar(figura, ruta)
    return titulo, datos.sort_values(ascending=False)


def grafico_ventas_en_el_tiempo(limpio, ruta):
    """Columnas con el importe vendido cada día, o cada mes si hay muchos días.

    Los días (o meses) sin ventas aparecen con 0, para que no parezca que son seguidos.
    """
    fechas = pd.to_datetime(limpio["fecha"])
    dias = (fechas.max() - fechas.min()).days + 1
    if dias > MAX_DIAS_POR_DIA:
        titulo, cabecera, frecuencia = "Ventas por mes", "Mes", "MS"
        formato_etiqueta, formato_tabla = "%m/%Y", "%Y-%m"
        periodo = fechas.dt.to_period("M").dt.to_timestamp()
    else:
        titulo, cabecera, frecuencia = "Ventas por día", "Día", "D"
        formato_etiqueta, formato_tabla = "%d/%m", "%Y-%m-%d"
        periodo = fechas

    agrupado = limpio["importe"].groupby(periodo).sum()
    todos = pd.date_range(agrupado.index.min(), agrupado.index.max(), freq=frecuencia)
    datos = agrupado.reindex(todos, fill_value=0)

    figura, ejes = _preparar_ejes(f"{titulo} (€)")
    ejes.bar(datos.index.strftime(formato_etiqueta), datos.values, color=COLOR_BARRAS, width=0.7)
    ejes.grid(axis="y", color=COLOR_REJILLA, linewidth=0.8)
    ejes.yaxis.set_major_formatter("{x:,.0f}")
    if len(datos) > 12:
        figura.autofmt_xdate()
    _guardar(figura, ruta)

    datos.index = datos.index.strftime(formato_tabla)
    datos.index.name = cabecera
    return titulo, datos
