"""Gráficos del informe: ventas por producto, ventas a lo largo del tiempo
y evolución de las ventas de una ejecución (semana) a otra.

Cada función guarda una imagen PNG (sin título: lo pone el informe). Las dos
primeras devuelven (título, datos), para poder mostrar también la tabla en el informe. El nombre del
índice de los datos ("Producto", "Día" o "Mes") sirve de cabecera de la tabla.
"""

import matplotlib

matplotlib.use("Agg")  # dibuja en archivos, sin abrir ventanas
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import FuncFormatter, MaxNLocator

from formato import numero

# Colores del gráfico: un solo color para los datos y grises suaves para lo demás.
COLOR_BARRAS = "#2a78d6"
COLOR_BARRAS_INCOMPLETAS = "#86b6ef"  # mismo azul, más claro: meses con datos incompletos
COLOR_CAMBIO_BRUSCO = "#d03b3b"  # rojo de aviso, el mismo del email
COLOR_FONDO = "#fcfcfb"
COLOR_TEXTO_SUAVE = "#52514e"
COLOR_REJILLA = "#e4e3df"

# Con datos reales puede haber miles de productos y años de fechas:
MAX_PRODUCTOS = 10      # el gráfico de productos muestra solo los que más venden
MAX_DIAS_POR_DIA = 62   # con más días que esto, las ventas se agrupan por mes
MAX_EJECUCIONES = 12    # el gráfico de evolución muestra las últimas 12 semanas

# Números de los ejes en formato español y sin decimales: 1.400.000
FORMATO_EJE = FuncFormatter(lambda valor, _: numero(valor, 0))


def _preparar_ejes(ancho=8, alto=4.5):
    """Crea una figura con el estilo común a todos los gráficos."""
    figura, ejes = plt.subplots(figsize=(ancho, alto), dpi=120)
    figura.patch.set_facecolor(COLOR_FONDO)
    ejes.set_facecolor(COLOR_FONDO)
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

    figura, ejes = _preparar_ejes(alto=0.45 * len(datos) + 0.8)
    ejes.barh(datos.index, datos.values, color=COLOR_BARRAS, height=0.7)
    ejes.grid(axis="x", color=COLOR_REJILLA, linewidth=0.8)
    ejes.spines["bottom"].set_visible(False)
    # Etiqueta con el valor al final de cada barra.
    for posicion, valor in enumerate(datos.values):
        ejes.text(valor, posicion, f"  {numero(valor)}", va="center", fontsize=9, color=COLOR_TEXTO_SUAVE)
    ejes.set_xlim(0, datos.max() * 1.25)  # espacio para la etiqueta de la barra más larga
    ejes.xaxis.set_major_locator(MaxNLocator(5))  # pocas marcas, para que no se pisen
    ejes.xaxis.set_major_formatter(FORMATO_EJE)
    _guardar(figura, ruta)
    return titulo, datos.sort_values(ascending=False)


def grafico_ventas_en_el_tiempo(limpio, ruta):
    """Columnas con el importe vendido cada día, o cada mes si hay muchos días.

    Los días (o meses) sin ventas aparecen con 0, para que no parezca que son seguidos.
    Si el primer o el último mes no tienen datos de todos sus días, se marcan como
    incompletos (color más claro y un *), para que no parezca una caída de ventas.
    """
    fechas = pd.to_datetime(limpio["fecha"])
    primera, ultima = fechas.min(), fechas.max()
    incompletos = set()
    if (ultima - primera).days + 1 > MAX_DIAS_POR_DIA:
        titulo, cabecera, frecuencia = "Ventas por mes", "Mes", "MS"
        formato_etiqueta, formato_tabla = "%m/%Y", "%Y-%m"
        periodo = fechas.dt.to_period("M").dt.to_timestamp()
        if primera.day != 1:
            incompletos.add(primera.to_period("M").to_timestamp())
        if not ultima.is_month_end:
            incompletos.add(ultima.to_period("M").to_timestamp())
    else:
        titulo, cabecera, frecuencia = "Ventas por día", "Día", "D"
        formato_etiqueta, formato_tabla = "%d/%m", "%Y-%m-%d"
        periodo = fechas

    agrupado = limpio["importe"].groupby(periodo).sum()
    todos = pd.date_range(agrupado.index.min(), agrupado.index.max(), freq=frecuencia)
    datos = agrupado.reindex(todos, fill_value=0)
    es_incompleto = [momento in incompletos for momento in datos.index]

    figura, ejes = _preparar_ejes()
    etiquetas = [
        momento.strftime(formato_etiqueta) + ("*" if incompleto else "")
        for momento, incompleto in zip(datos.index, es_incompleto)
    ]
    colores = [COLOR_BARRAS_INCOMPLETAS if incompleto else COLOR_BARRAS for incompleto in es_incompleto]
    ejes.bar(etiquetas, datos.values, color=colores, width=0.7)
    ejes.grid(axis="y", color=COLOR_REJILLA, linewidth=0.8)
    ejes.yaxis.set_major_formatter(FORMATO_EJE)
    if len(datos) > 12:
        figura.autofmt_xdate()
    if incompletos:
        nota = f"* Mes incompleto: los datos van del {primera:%d/%m/%Y} al {ultima:%d/%m/%Y}."
        figura.text(0.01, 0.01, nota, fontsize=9, color=COLOR_TEXTO_SUAVE)
    _guardar(figura, ruta)

    datos.index = [
        momento.strftime(formato_tabla) + (" (incompleto)" if incompleto else "")
        for momento, incompleto in zip(datos.index, es_incompleto)
    ]
    datos.index.name = cabecera
    return titulo, datos


def grafico_evolucion(historial, ruta):
    """Columnas con las ventas netas de cada ejecución (cada semana), de la más antigua
    a la más reciente. Las que cambiaron bruscamente respecto a la anterior van en rojo
    y con el % encima.

    historial debe venir de alertas.marcar_cambios_bruscos (columnas cambio y brusco).
    """
    datos = historial.tail(MAX_EJECUCIONES)
    etiquetas = [f"{fecha:%d/%m}" for fecha in pd.to_datetime(datos["fecha"])]
    # Dos ejecuciones el mismo día tendrían la misma etiqueta y se pisarían: se numeran.
    etiquetas = [e if etiquetas.count(e) == 1 else f"{e} ({i + 1})" for i, e in enumerate(etiquetas)]
    colores = [COLOR_CAMBIO_BRUSCO if brusco else COLOR_BARRAS for brusco in datos["brusco"]]

    figura, ejes = _preparar_ejes(alto=3.6)
    ejes.bar(etiquetas, datos["ventas_totales"], color=colores, width=0.6)
    ejes.grid(axis="y", color=COLOR_REJILLA, linewidth=0.8)
    ejes.yaxis.set_major_formatter(FORMATO_EJE)
    ejes.set_ylim(min(0, datos["ventas_totales"].min()), datos["ventas_totales"].max() * 1.18)
    # Con pocas semanas las barras saldrían enormes: se reserva sitio para al menos 6,
    # y el gráfico se va llenando de izquierda a derecha.
    ejes.set_xlim(-0.6, max(len(datos), 6) - 0.4)
    # Solo se etiquetan los cambios bruscos, para no llenar el gráfico de números.
    for posicion, (valor, cambio, brusco) in enumerate(
            zip(datos["ventas_totales"], datos["cambio"], datos["brusco"])):
        if brusco:
            ejes.text(posicion, valor, f"{'+' if cambio > 0 else ''}{numero(cambio, 0)} %",
                      ha="center", va="bottom", fontsize=9, fontweight="bold",
                      color=COLOR_CAMBIO_BRUSCO)
    _guardar(figura, ruta)
