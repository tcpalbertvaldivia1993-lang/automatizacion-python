"""Envío de los informes por email (SMTP).

La configuración (servidor, usuario, contraseña y destinatario) se lee del archivo
.env del proyecto, que NO se sube a GitHub. Ver .env.ejemplo.
También se puede dar con variables de entorno, que tienen prioridad sobre .env.
"""

import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

ARCHIVO_CONFIGURACION = Path(__file__).resolve().parent / ".env"
CLAVES = ["SMTP_SERVIDOR", "SMTP_PUERTO", "EMAIL_USUARIO", "EMAIL_CONTRASENA", "EMAIL_DESTINO"]


def leer_configuracion(ruta=ARCHIVO_CONFIGURACION):
    """Lee las líneas CLAVE=valor de .env y comprueba que no falte ninguna."""
    config = {}
    if ruta.exists():
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            config[clave.strip()] = valor.strip().strip('"').strip("'")
    for clave in CLAVES:
        if os.environ.get(clave):
            config[clave] = os.environ[clave]

    faltan = [clave for clave in CLAVES if not config.get(clave)]
    if faltan:
        raise ValueError(f"Falta configuración de email en {ruta.name}: {', '.join(faltan)}. "
                         "Copia .env.ejemplo como .env y rellénalo.")
    return config


def construir_mensaje(config, asunto, html, adjuntos, imagenes=()):
    """Crea el email: cuerpo en HTML y los informes como archivos adjuntos.

    adjuntos es una lista de (nombre que verá el destinatario, ruta del archivo).
    imagenes es una lista de (identificador, ruta de un PNG) que se muestran dentro
    del cuerpo: en el HTML se ponen con <img src="cid:identificador">. Gmail bloquea
    las imágenes en base64, pero sí muestra estas, que van como partes del mensaje.
    """
    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = config["EMAIL_USUARIO"]
    mensaje["To"] = config["EMAIL_DESTINO"]  # varios destinatarios: separados por comas
    # Texto simple para programas de correo que no muestran HTML.
    mensaje.set_content("Resumen de ventas generado automáticamente. "
                        "Los informes completos van adjuntos: ábrelos con el navegador.")
    mensaje.add_alternative(html, subtype="html")
    parte_html = mensaje.get_body(preferencelist=("html",))
    for identificador, ruta in imagenes:
        parte_html.add_related(ruta.read_bytes(), maintype="image", subtype="png",
                               cid=f"<{identificador}>")
    for nombre, ruta in adjuntos:
        mensaje.add_attachment(ruta.read_bytes(), maintype="text", subtype="html", filename=nombre)
    return mensaje


def enviar(config, mensaje):
    """Envía el mensaje con conexión cifrada (STARTTLS), como piden Gmail y Outlook."""
    contexto = ssl.create_default_context()
    with smtplib.SMTP(config["SMTP_SERVIDOR"], int(config["SMTP_PUERTO"]), timeout=30) as servidor:
        servidor.starttls(context=contexto)
        servidor.login(config["EMAIL_USUARIO"], config["EMAIL_CONTRASENA"])
        servidor.send_message(mensaje)
