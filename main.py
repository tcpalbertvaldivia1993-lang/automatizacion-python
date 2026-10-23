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
    --enviar-email        envía los informes por email (configuración en .env,
                          ver .env.ejemplo)
    --historial RUTA      guarda los totales de cada ejecución en ese CSV y avisa
                          si las ventas o los pedidos cambian bruscamente
                          respecto a la media de las 4 ejecuciones anteriores
    --umbral PORCENTAJE   cuánto tiene que cambiar para avisar (por defecto 30 %)
    --umbral-producto PORCENTAJE
                          cuánto tiene que cambiar uno de los 10 productos que más
                          venden para mencionarlo en el email (por defecto 50 %)

Resultados (carpeta resultados/):
    <nombre del archivo>/ventas_limpio.csv      -> datos ya limpios
    <nombre del archivo>/filas_descartadas.csv  -> filas eliminadas y el motivo
    <nombre del archivo>/informe.html           -> informe con indicadores y gráficos
    <nombre del archivo>/graficos/              -> imágenes PNG de los gráficos
    resumen.html                                -> comparación de archivos (solo con una carpeta)
    evolucion.png                               -> ventas de cada ejecución (solo con --historial)
    registro.log                                -> registro de todas las ejecuciones
"""

import argparse
import base64
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

import alertas
import enviar_email
from formato import numero
from graficos import grafico_evolucion, grafico_ventas_en_el_tiempo, grafico_ventas_por_producto
from limpieza import calcular_indicadores, limpiar_ventas

CARPETA_RESULTADOS = Path("resultados")
ARCHIVO_POR_DEFECTO = Path("datos/ventas_ejemplo.csv")
EXTENSIONES = {".csv", ".xlsx", ".xls"}

# Plantillas HTML de los informes. autoescape evita que un texto de los datos
# (por ejemplo un producto llamado "<b>Oferta</b>") se interprete como HTML.
PLANTILLAS = Environment(
    loader=FileSystemLoader(Path(__file__).resolve().parent / "plantillas"),
    autoescape=select_autoescape(),
)
PLANTILLAS.filters["numero"] = numero  # en las plantillas: {{ valor | numero }}


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


def crear_graficos(limpio, carpeta_salida):
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
        titulo, datos = funcion(limpio, carpeta / nombre)
        graficos.append((titulo, f"graficos/{nombre}", datos))
    return graficos


def imagen_incrustada(ruta):
    """Convierte un PNG en texto (base64) para meterlo dentro del HTML.

    Así el informe es un solo archivo: se puede enviar por email y se ve completo.
    """
    contenido = base64.b64encode(ruta.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{contenido}"


def escribir_informe(carpeta_salida, archivo, filas_originales, limpio, descartadas,
                     indicadores, graficos, moneda):
    """Crea el informe en HTML a partir de la plantilla plantillas/informe.html."""
    motivos = descartadas["motivo"].value_counts()
    html = PLANTILLAS.get_template("informe.html").render(
        archivo=archivo,
        nombre_archivo=archivo.name,
        fecha_ejecucion=f"{datetime.now():%d/%m/%Y %H:%M}",
        moneda=moneda,
        indicadores=indicadores,
        graficos=[
            {
                "titulo": titulo,
                "imagen": imagen_incrustada(carpeta_salida / imagen),
                "cabecera": datos.index.name,
                "filas": list(datos.items()),
            }
            for titulo, imagen, datos in graficos
        ],
        calidad={
            "originales": filas_originales,
            "validas": len(limpio),
            "descartadas": len(descartadas),
            "porcentaje_descartadas": 100 * len(descartadas) / filas_originales,
            "motivos": list(motivos.items()),
        },
    )
    ruta = carpeta_salida / "informe.html"
    ruta.write_text(html, encoding="utf-8")
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
    graficos = crear_graficos(limpio, carpeta_salida)
    ruta_informe = escribir_informe(carpeta_salida, archivo, len(df), limpio, descartadas,
                                    indicadores, graficos, moneda)
    logging.info("Informe generado en %s", ruta_informe)
    return indicadores


def escribir_resumen(resultados, moneda, evolucion=None):
    """Crea resultados/resumen.html con una fila por archivo, para compararlos.

    evolucion es la ruta del gráfico de evolución semanal, si lo hay.
    """
    errores = sum(1 for _, indicadores in resultados if indicadores is None)
    html = PLANTILLAS.get_template("resumen.html").render(
        fecha_ejecucion=f"{datetime.now():%d/%m/%Y %H:%M}",
        moneda=moneda,
        evolucion=imagen_incrustada(evolucion) if evolucion else None,
        correctos=len(resultados) - errores,
        errores=errores,
        filas=[
            {"nombre": archivo.name, "indicadores": indicadores,
             "enlace": f"{archivo.stem}/informe.html"}
            for archivo, indicadores in resultados
        ],
    )
    ruta = CARPETA_RESULTADOS / "resumen.html"
    ruta.write_text(html, encoding="utf-8")
    return ruta


def ventas_por_producto(archivos):
    """Suma el importe de cada producto en los datos limpios de todos los archivos."""
    limpios = [pd.read_csv(CARPETA_RESULTADOS / archivo.stem / "ventas_limpio.csv",
                           usecols=["producto", "importe"], dtype={"producto": str})
               for archivo in archivos]
    return pd.concat(limpios).groupby("producto")["importe"].sum()


def comparar_productos_con_anteriores(archivos, ruta_historial, umbral):
    """Guarda las ventas por producto en su historial y busca los que más han cambiado.

    Devuelve la lista de esos productos, o None si no hay con qué comparar.
    """
    ruta = alertas.ruta_historial_productos(ruta_historial)
    actual = ventas_por_producto(archivos)
    referencia = alertas.leer_productos_referencia(ruta)
    alertas.guardar_productos(ruta, actual)
    if referencia is None:
        return None
    cambios = alertas.comparar_productos(actual, referencia, umbral)
    for c in cambios:  # solo informativo: no es un aviso
        logging.info("Producto que más cambió: %s %+.1f %%", c["producto"], c["cambio"])
    return cambios


def comparar_con_anteriores(resultados, ruta_historial, umbral,
                            umbral_producto=alertas.UMBRAL_PRODUCTO_POR_DEFECTO):
    """Guarda los totales y las ventas por producto de esta ejecución en los historiales
    y los compara con la media de las últimas ejecuciones.

    Devuelve {"semanas": ..., "cambios": [...], "productos": [...]}, donde "semanas" es
    cuántas ejecuciones entran en la media, o None si no hay con qué comparar.
    """
    archivos = [archivo for archivo, indicadores in resultados if indicadores is not None]
    if not archivos:
        return None
    totales = alertas.sumar_indicadores([indicadores for _, indicadores in resultados
                                         if indicadores is not None])
    # La referencia se lee antes de guardar: esta ejecución no entra en su propia media.
    referencia = alertas.leer_referencia(ruta_historial)
    alertas.guardar_ejecucion(ruta_historial, totales)
    productos = comparar_productos_con_anteriores(archivos, ruta_historial, umbral_producto)
    if referencia is None:
        logging.info("Primera ejecución con historial: la próxima vez habrá con qué comparar")
        return None

    cambios = alertas.comparar(totales, referencia, umbral)
    for c in cambios:
        if c["brusco"]:
            logging.warning("Cambio brusco en %s: %+.1f %% respecto a la media de las %d "
                            "ejecuciones anteriores", c["nombre"].lower(), c["cambio"],
                            referencia["semanas"])
    return {"semanas": referencia["semanas"], "cambios": cambios, "productos": productos or []}


def crear_grafico_evolucion(ruta_historial, umbral):
    """Dibuja resultados/evolucion.png con las ventas de las últimas ejecuciones.

    Devuelve la ruta del gráfico, o None si aún hay menos de dos ejecuciones.
    """
    historial = alertas.leer_historial(ruta_historial)
    if len(historial) < 2:
        return None
    ruta = CARPETA_RESULTADOS / "evolucion.png"
    grafico_evolucion(alertas.marcar_cambios_bruscos(historial, umbral), ruta)
    logging.info("Gráfico de evolución generado en %s", ruta)
    return ruta


def enviar_por_email(resultados, moneda, comparacion=None, evolucion=None):
    """Envía un email con los indicadores de cada archivo y sus informes HTML adjuntos.

    Si hay comparación con las ejecuciones anteriores, el email la muestra y el asunto
    avisa de los cambios bruscos. Si hay gráfico de evolución, va dentro del cuerpo.
    """
    config = enviar_email.leer_configuracion()
    correctos = [archivo for archivo, indicadores in resultados if indicadores is not None]
    errores = len(resultados) - len(correctos)
    fecha = f"{datetime.now():%d/%m/%Y}"

    html = PLANTILLAS.get_template("email.html").render(
        fecha_ejecucion=fecha,
        moneda=moneda,
        correctos=len(correctos),
        errores=errores,
        filas=[{"nombre": archivo.name, "indicadores": indicadores}
               for archivo, indicadores in resultados],
        comparacion=comparacion,
        evolucion=evolucion is not None,
    )
    asunto = f"Informe de ventas · {fecha}"
    if errores:
        asunto += f" · ⚠ {errores} con errores"
    for c in (comparacion or {}).get("cambios", []):
        if c["brusco"]:
            asunto += f" · ⚠ {c['nombre']} {c['cambio']:+.0f} %"
    adjuntos = [(f"informe_{archivo.stem}.html", CARPETA_RESULTADOS / archivo.stem / "informe.html")
                for archivo in correctos]

    imagenes = [("evolucion", evolucion)] if evolucion else []  # en la plantilla: cid:evolucion
    mensaje = enviar_email.construir_mensaje(config, asunto, html, adjuntos, imagenes)
    enviar_email.enviar(config, mensaje)
    logging.info("Email enviado a %s con %d %s", config["EMAIL_DESTINO"], len(adjuntos),
                 "informe adjunto" if len(adjuntos) == 1 else "informes adjuntos")


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
    parser.add_argument("--enviar-email", action="store_true",
                        help="enviar los informes por email (configuración en .env)")
    parser.add_argument("--historial", type=Path,
                        help="CSV donde se guardan los totales de cada ejecución para "
                             "compararlos con la media de las 4 anteriores y avisar "
                             "de cambios bruscos")
    parser.add_argument("--umbral", type=float, default=alertas.UMBRAL_POR_DEFECTO,
                        help="%% de subida o bajada que se considera brusco (por defecto 30)")
    parser.add_argument("--umbral-producto", type=float,
                        default=alertas.UMBRAL_PRODUCTO_POR_DEFECTO,
                        help="%% de cambio de un producto para mencionarlo (por defecto 50)")
    return parser.parse_args()


def main():
    argumentos = leer_argumentos()
    configurar_registro()
    logging.info("Inicio de la ejecución con %s", argumentos.ruta)

    archivos = buscar_archivos(argumentos.ruta)
    if argumentos.historial:  # por si los historiales están en la misma carpeta: no son ventas
        historiales = {argumentos.historial.resolve(),
                       alertas.ruta_historial_productos(argumentos.historial).resolve()}
        archivos = [a for a in archivos if a.resolve() not in historiales]
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

    comparacion = evolucion = None
    if argumentos.historial:
        comparacion = comparar_con_anteriores(resultados, argumentos.historial, argumentos.umbral,
                                              argumentos.umbral_producto)
        evolucion = crear_grafico_evolucion(argumentos.historial, argumentos.umbral)

    if argumentos.ruta.is_dir():
        logging.info("Resumen generado en %s",
                     escribir_resumen(resultados, argumentos.moneda, evolucion))

    errores = sum(1 for _, indicadores in resultados if indicadores is None)
    email_fallido = False
    if argumentos.enviar_email:
        try:
            enviar_por_email(resultados, argumentos.moneda, comparacion, evolucion)
        except Exception as error:  # configuración incompleta, sin internet, contraseña mal...
            logging.error("No se pudo enviar el email: %s", error)
            email_fallido = True

    logging.info("Fin de la ejecución: %d archivos correctos, %d con errores",
                 len(resultados) - errores, errores)
    if errores or email_fallido:
        sys.exit(1)  # así la tarea programada o GitHub Actions saben que algo falló


if __name__ == "__main__":
    main()
