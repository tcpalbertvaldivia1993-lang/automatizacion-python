"""Herramienta de automatización: limpia archivos de ventas y genera informes.

Uso:
    venv/bin/python main.py                              # usa datos/ventas_ejemplo.csv
    venv/bin/python main.py ruta/a/mis_ventas.csv        # un archivo CSV
    venv/bin/python main.py ruta/a/mis_ventas.xlsx       # un archivo Excel
    venv/bin/python main.py ruta/a/carpeta/              # todos los CSV y Excel de la carpeta
    venv/bin/python main.py datos/reales/online_retail.csv --moneda £

Opciones:
    --moneda SÍMBOLO      símbolo de la moneda en el informe (por defecto €)
    --mover-procesados    al terminar, mueve cada archivo procesado sin errores a
                          una subcarpeta "procesados/" junto a él (útil al programarlo)

Resultados (carpeta resultados/):
    <nombre del archivo>/ventas_limpio.csv      -> datos ya limpios
    <nombre del archivo>/filas_descartadas.csv  -> filas eliminadas y el motivo
    <nombre del archivo>/informe.md             -> resumen con los indicadores y gráficos
    <nombre del archivo>/graficos/              -> imágenes PNG de los gráficos
    resumen.md                                  -> comparación de archivos (solo con una carpeta)
    registro.log                                -> registro de todas las ejecuciones
"""

import argparse
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from graficos import grafico_ventas_en_el_tiempo, grafico_ventas_por_producto
from limpieza import calcular_indicadores, limpiar_ventas

CARPETA_RESULTADOS = Path("resultados")
ARCHIVO_POR_DEFECTO = Path("datos/ventas_ejemplo.csv")
EXTENSIONES = {".csv", ".xlsx", ".xls"}


def configurar_registro():
    """Guarda los mensajes en resultados/registro.log y también los muestra en pantalla."""
    CARPETA_RESULTADOS.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(CARPETA_RESULTADOS / "registro.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    # matplotlib escribe avisos internos que no interesan en nuestro registro.
    logging.getLogger("matplotlib").setLevel(logging.WARNING)


def leer_archivo(archivo):
    """Lee un CSV o un Excel. Todo se lee como texto para poder detectar los errores nosotros."""
    if archivo.suffix.lower() == ".csv":
        return pd.read_csv(archivo, dtype=str, keep_default_na=False)
    return pd.read_excel(archivo, dtype=str, keep_default_na=False)


def buscar_archivos(ruta):
    """Devuelve la lista de archivos a procesar: el propio archivo, o los de la carpeta."""
    if ruta.is_dir():
        return sorted(a for a in ruta.iterdir() if a.is_file() and a.suffix.lower() in EXTENSIONES)
    return [ruta]


def crear_graficos(limpio, carpeta_salida, moneda):
    """Genera los gráficos en <carpeta_salida>/graficos/.

    Devuelve una lista con (título, imagen, datos) de cada gráfico.
    """
    carpeta = carpeta_salida / "graficos"
    carpeta.mkdir(exist_ok=True)
    graficos = []
    for nombre, funcion in [
        ("ventas_por_producto.png", grafico_ventas_por_producto),
        ("ventas_en_el_tiempo.png", grafico_ventas_en_el_tiempo),
    ]:
        titulo, datos = funcion(limpio, carpeta / nombre, moneda)
        graficos.append((titulo, f"graficos/{nombre}", datos))
    return graficos


def tabla_markdown(datos, moneda):
    """Convierte una serie de pandas en una tabla Markdown de dos columnas."""
    lineas = [f"| {datos.index.name} | Ventas ({moneda}) |", "|---|---:|"]
    lineas += [f"| {indice} | {valor:,.2f} |" for indice, valor in datos.items()]
    return lineas


def escribir_informe(carpeta_salida, archivo, filas_originales, limpio, descartadas,
                     indicadores, graficos, moneda):
    """Crea el informe en formato Markdown."""
    resumen_motivos = descartadas["motivo"].value_counts()
    lineas = [
        "# Informe de ventas",
        "",
        f"- Archivo analizado: `{archivo}`",
        f"- Fecha de ejecución: {datetime.now():%Y-%m-%d %H:%M}",
        "",
        "## Indicadores",
        "",
        f"- **Ventas totales (netas):** {indicadores['ventas_totales']:,.2f} {moneda}",
        f"- **Devoluciones y cancelaciones (ya restadas):** {indicadores['devoluciones']:,.2f} {moneda}",
        f"- **Pedidos:** {indicadores['pedidos']:,}",
        f"- **Valor medio por pedido:** {indicadores['valor_medio_pedido']:,.2f} {moneda}",
        "",
    ]
    for titulo, imagen, datos in graficos:
        lineas += [f"## {titulo}", "", f"![{titulo}]({imagen})", ""]
        lineas += tabla_markdown(datos, moneda) + [""]
    lineas += [
        "## Calidad de los datos",
        "",
        f"- Filas originales: {filas_originales:,}",
        f"- Filas válidas: {len(limpio):,}",
        f"- Filas descartadas: {len(descartadas):,}",
        "",
    ]
    if not resumen_motivos.empty:
        lineas += ["| Motivo | Filas |", "|---|---|"]
        lineas += [f"| {motivo} | {n:,} |" for motivo, n in resumen_motivos.items()]
        lineas.append("")

    ruta = carpeta_salida / "informe.md"
    ruta.write_text("\n".join(lineas), encoding="utf-8")
    return ruta


def procesar_archivo(archivo, moneda):
    """Limpia un archivo y genera sus resultados en resultados/<nombre del archivo>/.

    Devuelve los indicadores, o None si el archivo no se pudo procesar.
    """
    logging.info("Procesando %s", archivo)
    try:
        df = leer_archivo(archivo)
    except FileNotFoundError:
        logging.error("No se encuentra el archivo %s", archivo)
        return None
    except Exception as error:  # archivo dañado, formato no reconocido...
        logging.error("No se pudo leer %s: %s", archivo, error)
        return None
    logging.info("Filas leídas: %d", len(df))

    try:
        limpio, descartadas = limpiar_ventas(df)
    except ValueError as error:
        logging.error("%s: %s", archivo.name, error)
        return None

    for motivo, n in descartadas["motivo"].value_counts().items():
        logging.warning("Descartadas %d filas por: %s", n, motivo)
    logging.info("Filas válidas: %d", len(limpio))
    if limpio.empty:
        logging.error("%s: no queda ninguna fila válida", archivo.name)
        return None

    indicadores = calcular_indicadores(limpio)
    logging.info("Indicadores: %s", indicadores)

    carpeta_salida = CARPETA_RESULTADOS / archivo.stem
    carpeta_salida.mkdir(exist_ok=True)
    limpio.to_csv(carpeta_salida / "ventas_limpio.csv", index=False)
    descartadas.to_csv(carpeta_salida / "filas_descartadas.csv", index=False)
    graficos = crear_graficos(limpio, carpeta_salida, moneda)
    ruta_informe = escribir_informe(carpeta_salida, archivo, len(df), limpio, descartadas,
                                    indicadores, graficos, moneda)
    logging.info("Informe generado en %s", ruta_informe)
    return indicadores


def escribir_resumen(resultados, moneda):
    """Crea resultados/resumen.md con una fila por archivo, para compararlos."""
    lineas = [
        "# Resumen de archivos procesados",
        "",
        f"Fecha de ejecución: {datetime.now():%Y-%m-%d %H:%M}",
        "",
        f"| Archivo | Ventas netas ({moneda}) | Devoluciones ({moneda}) | Pedidos "
        f"| Valor medio ({moneda}) | Informe |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for archivo, ind in resultados:
        if ind is None:
            lineas.append(f"| {archivo.name} | ❌ error, ver registro.log | | | | |")
        else:
            lineas.append(
                f"| {archivo.name} | {ind['ventas_totales']:,.2f} | {ind['devoluciones']:,.2f} "
                f"| {ind['pedidos']:,} | {ind['valor_medio_pedido']:,.2f} "
                f"| [informe]({archivo.stem}/informe.md) |"
            )
    ruta = CARPETA_RESULTADOS / "resumen.md"
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return ruta


def mover_a_procesados(archivo):
    """Mueve el archivo a una subcarpeta "procesados/" para no volver a procesarlo."""
    destino = archivo.parent / "procesados"
    destino.mkdir(exist_ok=True)
    shutil.move(archivo, destino / archivo.name)
    logging.info("Movido a %s", destino / archivo.name)


def leer_argumentos():
    parser = argparse.ArgumentParser(description="Limpia archivos de ventas y genera informes.")
    parser.add_argument("ruta", nargs="?", type=Path, default=ARCHIVO_POR_DEFECTO,
                        help="archivo CSV/Excel, o carpeta con varios")
    parser.add_argument("--moneda", default="€", help="símbolo de la moneda (por defecto €)")
    parser.add_argument("--mover-procesados", action="store_true",
                        help="mover cada archivo procesado sin errores a procesados/")
    return parser.parse_args()


def main():
    argumentos = leer_argumentos()
    configurar_registro()
    logging.info("Inicio de la ejecución con %s", argumentos.ruta)

    archivos = buscar_archivos(argumentos.ruta)
    if not archivos:
        logging.info("No hay archivos CSV ni Excel en %s. Nada que hacer.", argumentos.ruta)
        logging.info("Fin de la ejecución")
        return

    resultados = []
    for archivo in archivos:
        indicadores = procesar_archivo(archivo, argumentos.moneda)
        resultados.append((archivo, indicadores))
        if indicadores is not None and argumentos.mover_procesados:
            mover_a_procesados(archivo)

    if argumentos.ruta.is_dir():
        logging.info("Resumen generado en %s", escribir_resumen(resultados, argumentos.moneda))

    errores = sum(1 for _, indicadores in resultados if indicadores is None)
    logging.info("Fin de la ejecución: %d archivos correctos, %d con errores",
                 len(resultados) - errores, errores)
    if errores:
        sys.exit(1)  # así cron o GitHub Actions saben que algo falló


if __name__ == "__main__":
    main()
