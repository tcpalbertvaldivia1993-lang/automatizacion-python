from pathlib import Path

import pytest

import enviar_email
import main

CSV_EJEMPLO = Path(__file__).resolve().parent.parent / "datos" / "ventas_ejemplo.csv"

CONFIG = {
    "SMTP_SERVIDOR": "smtp.ejemplo.com",
    "SMTP_PUERTO": "587",
    "EMAIL_USUARIO": "yo@ejemplo.com",
    "EMAIL_CONTRASENA": "secreta",
    "EMAIL_DESTINO": "jefa@ejemplo.com",
}


class ServidorFalso:
    """Imita a smtplib.SMTP sin conectarse a internet; guarda lo que se le pide."""

    enviados = []

    def __init__(self, servidor, puerto, timeout):
        self.datos = {"servidor": servidor, "puerto": puerto}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def starttls(self, context):
        self.datos["cifrado"] = True

    def login(self, usuario, contrasena):
        self.datos["login"] = (usuario, contrasena)

    def send_message(self, mensaje):
        ServidorFalso.enviados.append((self.datos, mensaje))


@pytest.fixture(autouse=True)
def sin_variables_de_entorno(monkeypatch):
    for clave in enviar_email.CLAVES:
        monkeypatch.delenv(clave, raising=False)


def test_leer_configuracion(tmp_path):
    archivo = tmp_path / ".env"
    archivo.write_text(
        "# comentario\n" + "\n".join(f"{k}={v}" for k, v in CONFIG.items()) + "\n",
        encoding="utf-8",
    )
    assert enviar_email.leer_configuracion(archivo) == CONFIG


def test_configuracion_incompleta_da_error_claro(tmp_path):
    archivo = tmp_path / ".env"
    archivo.write_text("SMTP_SERVIDOR=smtp.gmail.com\n", encoding="utf-8")
    with pytest.raises(ValueError, match="EMAIL_CONTRASENA"):
        enviar_email.leer_configuracion(archivo)


def test_construir_mensaje_con_adjunto(tmp_path):
    informe = tmp_path / "informe.html"
    informe.write_text("<h1>Hola</h1>", encoding="utf-8")
    mensaje = enviar_email.construir_mensaje(CONFIG, "Asunto", "<p>cuerpo</p>",
                                             [("informe_x.html", informe)])
    assert mensaje["To"] == "jefa@ejemplo.com"
    adjuntos = list(mensaje.iter_attachments())
    assert [a.get_filename() for a in adjuntos] == ["informe_x.html"]


def test_enviar_por_email_completo(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "CARPETA_RESULTADOS", tmp_path)
    monkeypatch.setattr(enviar_email, "leer_configuracion", lambda: CONFIG)
    monkeypatch.setattr(enviar_email.smtplib, "SMTP", ServidorFalso)
    ServidorFalso.enviados.clear()

    roto = tmp_path / "roto.csv"
    resultados = [(CSV_EJEMPLO, main.procesar_archivo(CSV_EJEMPLO, "€")), (roto, None)]
    main.enviar_por_email(resultados, "€")

    datos, mensaje = ServidorFalso.enviados[0]
    assert datos == {"servidor": "smtp.ejemplo.com", "puerto": 587, "cifrado": True,
                     "login": ("yo@ejemplo.com", "secreta")}
    assert "1 con errores" in mensaje["Subject"]
    cuerpo = mensaje.get_body(preferencelist=("html",)).get_content()
    assert "1.375,99 €" in cuerpo
    assert "roto.csv" in cuerpo and "No se pudo procesar" in cuerpo
    assert [a.get_filename() for a in mensaje.iter_attachments()] == ["informe_ventas_ejemplo.html"]
