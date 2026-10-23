import pytest

import alertas
import enviar_email
import main
from tests.test_enviar_email import CONFIG, CSV_EJEMPLO, ServidorFalso

SEMANA_1 = {"ventas_totales": 1000.0, "devoluciones": 0.0, "pedidos": 10, "valor_medio_pedido": 100.0}


def test_sumar_indicadores_de_varios_archivos():
    otro = {"ventas_totales": 500.0, "devoluciones": 20.0, "pedidos": 5, "valor_medio_pedido": 100.0}
    assert alertas.sumar_indicadores([SEMANA_1, otro]) == {
        "ventas_totales": 1500.0, "devoluciones": 20.0, "pedidos": 15, "valor_medio_pedido": 100.0,
    }


def test_historial_guarda_y_lee_la_ultima_ejecucion(tmp_path):
    ruta = tmp_path / "historial.csv"
    assert alertas.leer_ultima_ejecucion(ruta) is None
    alertas.guardar_ejecucion(ruta, SEMANA_1)
    alertas.guardar_ejecucion(ruta, {**SEMANA_1, "pedidos": 7})
    ultima = alertas.leer_ultima_ejecucion(ruta)
    assert ultima["pedidos"] == 7
    assert ruta.read_text(encoding="utf-8").count("fecha") == 1  # la cabecera solo una vez


@pytest.mark.parametrize("ventas, brusco", [(1100, False), (1250, True), (650, True), (800, True)])
def test_cambio_brusco_segun_umbral(ventas, brusco):
    cambios = alertas.comparar({**SEMANA_1, "ventas_totales": ventas}, SEMANA_1, umbral=20)
    assert cambios[0]["clave"] == "ventas_totales"
    assert cambios[0]["brusco"] is brusco


def test_sin_ventas_antes_no_se_calcula_porcentaje():
    cambios = alertas.comparar(SEMANA_1, {**SEMANA_1, "ventas_totales": 0}, umbral=20)
    assert cambios[0]["cambio"] is None and not cambios[0]["brusco"]


def test_email_avisa_de_bajada_brusca(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "CARPETA_RESULTADOS", tmp_path)
    monkeypatch.setattr(enviar_email, "leer_configuracion", lambda: CONFIG)
    monkeypatch.setattr(enviar_email.smtplib, "SMTP", ServidorFalso)
    ServidorFalso.enviados.clear()

    # La semana anterior se vendieron 2.000 € en 16 pedidos; esta, 1.375,99 € en 8.
    historial = tmp_path / "historial.csv"
    alertas.guardar_ejecucion(historial, {**SEMANA_1, "ventas_totales": 2000.0, "pedidos": 16})
    resultados = [(CSV_EJEMPLO, main.procesar_archivo(CSV_EJEMPLO, "€"))]
    comparacion = main.comparar_con_anterior(resultados, historial, umbral=20)
    main.enviar_por_email(resultados, "€", comparacion)

    _, mensaje = ServidorFalso.enviados[0]
    assert "⚠ Ventas netas -31 %" in mensaje["Subject"]
    assert "⚠ Pedidos -50 %" in mensaje["Subject"]
    cuerpo = mensaje.get_body(preferencelist=("html",)).get_content()
    assert "Cambio brusco" in cuerpo and "-31,2 %" in cuerpo and "(bajada)" in cuerpo
    assert alertas.leer_ultima_ejecucion(historial)["ventas_totales"] == 1375.99


def test_primera_ejecucion_no_compara(tmp_path):
    resultados = [(CSV_EJEMPLO, SEMANA_1)]
    assert main.comparar_con_anterior(resultados, tmp_path / "historial.csv", 20) is None
    assert (tmp_path / "historial.csv").exists()
