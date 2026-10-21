"""Gráficos del informe: ventas por producto y ventas por día.

Cada función guarda una imagen PNG y devuelve la tabla de datos usada,
para poder mostrarla también en el informe.
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
    """Barras horizontales con el importe vendido de cada producto, de mayor a menor."""
    datos = limpio.groupby("producto")["importe"].sum().sort_values()

    figura, ejes = _preparar_ejes("Ventas por producto (€)", alto=0.45 * len(datos) + 1.2)
    ejes.barh(datos.index, datos.values, color=COLOR_BARRAS, height=0.7)
    ejes.grid(axis="x", color=COLOR_REJILLA, linewidth=0.8)
    ejes.spines["bottom"].set_visible(False)
    # Etiqueta con el valor al final de cada barra.
    for posicion, valor in enumerate(datos.values):
        ejes.text(valor, posicion, f"  {valor:.2f}", va="center", fontsize=9, color=COLOR_TEXTO_SUAVE)
    ejes.set_xlim(0, datos.max() * 1.15)
    _guardar(figura, ruta)
    return datos.sort_values(ascending=False)


def grafico_ventas_por_dia(limpio, ruta):
    """Columnas con el importe vendido cada día.

    Los días sin ventas aparecen con 0, para que no parezca que las fechas son seguidas.
    """
    por_dia = limpio.groupby(pd.to_datetime(limpio["fecha"]))["importe"].sum()
    todos_los_dias = pd.date_range(por_dia.index.min(), por_dia.index.max(), freq="D")
    datos = por_dia.reindex(todos_los_dias, fill_value=0)

    figura, ejes = _preparar_ejes("Ventas por día (€)")
    etiquetas = datos.index.strftime("%d/%m")
    ejes.bar(etiquetas, datos.values, color=COLOR_BARRAS, width=0.7)
    ejes.grid(axis="y", color=COLOR_REJILLA, linewidth=0.8)
    if len(datos) > 15:
        figura.autofmt_xdate()
    _guardar(figura, ruta)
    datos.index = datos.index.strftime("%Y-%m-%d")
    return datos
