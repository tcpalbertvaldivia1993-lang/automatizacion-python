"""Herramienta de automatización: limpia un CSV de ventas y genera un informe.

Uso:
    venv/bin/python main.py                              # usa datos/ventas_ejemplo.csv
    venv/bin/python main.py ruta/a/mis_ventas.csv

Resultados (carpeta resultados/):
    ventas_limpio.csv      -> datos ya limpios
    filas_descartadas.csv  -> filas eliminadas y el motivo
    informe.md             -> resumen con los indicadores
    registro.log           -> registro de cada ejecución
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from limpieza import calcular_indicadores, limpiar_ventas

CARPETA_RESULTADOS = Path("resultados")
ARCHIVO_POR_DEFECTO = Path("datos/ventas_ejemplo.csv")


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


def escribir_informe(archivo, filas_originales, limpio, descartadas, indicadores):
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
        f"- **Ventas totales:** {indicadores['ventas_totales']:.2f} €",
        f"- **Pedidos:** {indicadores['pedidos']}",
        f"- **Valor medio por pedido:** {indicadores['valor_medio_pedido']:.2f} €",
        "",
        "## Calidad de los datos",
        "",
        f"- Filas originales: {filas_originales}",
        f"- Filas válidas: {len(limpio)}",
        f"- Filas descartadas: {len(descartadas)}",
        "",
    ]
    if not resumen_motivos.empty:
        lineas += ["| Motivo | Filas |", "|---|---|"]
        lineas += [f"| {motivo} | {n} |" for motivo, n in resumen_motivos.items()]
        lineas.append("")

    ruta = CARPETA_RESULTADOS / "informe.md"
    ruta.write_text("\n".join(lineas), encoding="utf-8")
    return ruta


def main():
    archivo = Path(sys.argv[1]) if len(sys.argv) > 1 else ARCHIVO_POR_DEFECTO
    configurar_registro()
    logging.info("Inicio de la ejecución con el archivo %s", archivo)

    try:
        # dtype=str: leemos todo como texto para poder detectar los errores nosotros.
        df = pd.read_csv(archivo, dtype=str, keep_default_na=False)
    except FileNotFoundError:
        logging.error("No se encuentra el archivo %s", archivo)
        sys.exit(1)
    logging.info("Filas leídas: %d", len(df))

    try:
        limpio, descartadas = limpiar_ventas(df)
    except ValueError as error:
        logging.error(str(error))
        sys.exit(1)

    for motivo, n in descartadas["motivo"].value_counts().items():
        logging.warning("Descartadas %d filas por: %s", n, motivo)
    logging.info("Filas válidas: %d", len(limpio))

    indicadores = calcular_indicadores(limpio)
    logging.info("Indicadores: %s", indicadores)

    limpio.to_csv(CARPETA_RESULTADOS / "ventas_limpio.csv", index=False)
    descartadas.to_csv(CARPETA_RESULTADOS / "filas_descartadas.csv", index=False)
    ruta_informe = escribir_informe(archivo, len(df), limpio, descartadas, indicadores)
    logging.info("Informe generado en %s", ruta_informe)
    logging.info("Fin de la ejecución")


if __name__ == "__main__":
    main()
