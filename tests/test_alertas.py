import pandas as pd
import pytest

import alertas
import enviar_email
import main
from tests.test_enviar_email import CONFIG, CSV_EJEMPLO, ServidorFalso

SEMANA_1 = {"ventas_totales": 1000.0, "devoluciones": 0.0, "pedidos": 10, "valor_medio_pedido": 100.0}


@pytest.fixture
def email_falso(tmp_path, monkeypatch):
    """Resultados en una carpeta temporal y emails a un servidor falso."""
    monkeypatch.setattr(main, "CARPETA_RESULTADOS", tmp_path)
    monkeypatch.setattr(enviar_email, "leer_configuracion", lambda: CONFIG)
    monkeypatch.setattr(enviar_email.smtplib, "SMTP", ServidorFalso)
    ServidorFalso.enviados.clear()
    return ServidorFalso.enviados


def test_sumar_indicadores_de_varios_archivos():
    otro = {"ventas_totales": 500.0, "devoluciones": 20.0, "pedidos": 5, "valor_medio_pedido": 100.0}
    assert alertas.sumar_indicadores([SEMANA_1, otro]) == {
        "ventas_totales": 1500.0, "devoluciones": 20.0, "pedidos": 15, "valor_medio_pedido": 100.0,
    }


def test_referencia_es_la_media_de_las_ultimas_4_ejecuciones(tmp_path):
    ruta = tmp_path / "historial.csv"
    assert alertas.leer_referencia(ruta) is None
    alertas.guardar_ejecucion(ruta, SEMANA_1)
    alertas.guardar_ejecucion(ruta, {**SEMANA_1, "ventas_totales": 2000.0})
    # Al principio hay menos de 4: se usa la media de las que haya.
    assert alertas.leer_referencia(ruta) == {"ventas_totales": 1500.0, "pedidos": 10.0, "semanas": 2}
    for ventas in [3000.0, 4000.0, 5000.0]:
        alertas.guardar_ejecucion(ruta, {**SEMANA_1, "ventas_totales": ventas})
    # Con 5 ejecuciones, la primera (1.000) ya no entra: (2000+3000+4000+5000) / 4
    assert alertas.leer_referencia(ruta)["ventas_totales"] == 3500.0
    assert ruta.read_text(encoding="utf-8").count("fecha") == 1  # la cabecera solo una vez


@pytest.mark.parametrize("ventas, brusco", [(1100, False), (1300, True), (750, False), (700, True)])
def test_cambio_brusco_segun_umbral(ventas, brusco):
    cambios = alertas.comparar({**SEMANA_1, "ventas_totales": ventas}, SEMANA_1, umbral=30)
    assert cambios[0]["clave"] == "ventas_totales"
    assert cambios[0]["brusco"] is brusco


def test_sin_ventas_antes_no_se_calcula_porcentaje():
    cambios = alertas.comparar(SEMANA_1, {**SEMANA_1, "ventas_totales": 0}, umbral=30)
    assert cambios[0]["cambio"] is None and not cambios[0]["brusco"]


def test_email_avisa_de_bajada_brusca(tmp_path, email_falso):
    # Las 4 semanas anteriores se vendieron 2.000 € en 16 pedidos; esta, 1.375,99 € en 8.
    historial = tmp_path / "historial.csv"
    for _ in range(4):
        alertas.guardar_ejecucion(historial, {**SEMANA_1, "ventas_totales": 2000.0, "pedidos": 16})
    resultados = [(CSV_EJEMPLO, main.procesar_archivo(CSV_EJEMPLO, "€"))]
    comparacion = main.comparar_con_anteriores(resultados, historial, umbral=30)
    main.enviar_por_email(resultados, "€", comparacion)

    mensaje = email_falso[0][1]
    assert "⚠ Ventas netas -31 %" in mensaje["Subject"]
    assert "⚠ Pedidos -50 %" in mensaje["Subject"]
    cuerpo = mensaje.get_body(preferencelist=("html",)).get_content()
    assert "Cambio brusco" in cuerpo and "-31,2 %" in cuerpo and "(bajada)" in cuerpo
    assert "la media de las 4 semanas anteriores" in cuerpo
    assert alertas.leer_historial(historial)["ventas_totales"].iloc[-1] == 1375.99


def test_marcar_cambios_bruscos_con_la_media():
    historial = pd.DataFrame({"ventas_totales": [1000.0, 1100.0, 700.0, 1000.0, 1000.0, 600.0]})
    marcado = alertas.marcar_cambios_bruscos(historial, umbral=30)
    # 1ª: sin anteriores · +10 % · 700 vs 1.050 (-33 %) · +7 % · +5 % · 600 vs 950 (-37 %)
    assert marcado["brusco"].tolist() == [False, False, True, False, False, True]
    assert round(marcado["cambio"][5], 1) == -36.8


def test_grafico_de_evolucion_en_el_email(tmp_path, email_falso):
    historial = tmp_path / "historial.csv"
    alertas.guardar_ejecucion(historial, SEMANA_1)
    assert main.crear_grafico_evolucion(historial, 30) is None  # con una sola semana no hay gráfico
    alertas.guardar_ejecucion(historial, {**SEMANA_1, "ventas_totales": 500.0})
    evolucion = main.crear_grafico_evolucion(historial, 30)
    assert evolucion == tmp_path / "evolucion.png" and evolucion.exists()

    main.enviar_por_email([(CSV_EJEMPLO, None)], "€", evolucion=evolucion)
    mensaje = email_falso[0][1]
    assert 'src="cid:evolucion"' in mensaje.get_body(preferencelist=("html",)).get_content()
    imagenes = [p for p in mensaje.walk() if p.get_content_type() == "image/png"]
    assert [p["Content-ID"] for p in imagenes] == ["<evolucion>"]

    html = main.escribir_resumen([(CSV_EJEMPLO, None)], "€", evolucion).read_text(encoding="utf-8")
    assert "semana a semana" in html and "data:image/png;base64," in html


def test_primera_ejecucion_no_compara(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "CARPETA_RESULTADOS", tmp_path)
    resultados = [(CSV_EJEMPLO, main.procesar_archivo(CSV_EJEMPLO, "€"))]
    assert main.comparar_con_anteriores(resultados, tmp_path / "historial.csv", 30) is None
    assert (tmp_path / "historial.csv").exists()
    assert (tmp_path / "historial_productos.csv").exists()


def test_productos_que_mas_cambiaron():
    referencia = pd.Series({"Portátil": 1000.0, "Monitor": 400.0, "Funda": 200.0,
                            "Ratón": 100.0, "Cable": 5.0})
    actual = pd.Series({"Portátil": 950.0, "Monitor": 100.0, "Funda": 500.0, "Cable": 1.0,
                        "Nuevo": 900.0})
    cambios = alertas.comparar_productos(actual, referencia, umbral=50, maximo=4, mostrar=2)
    # Funda +150 %, Ratón -100 % (sin ventas), Monitor -75 %, Portátil -5 % (no llega al umbral).
    # Cable no está entre los 4 que más venden y Nuevo no vendía antes: no se miran.
    # Se muestran los 2 cambios más grandes, sea subida o bajada.
    assert [(c["producto"], c["cambio"]) for c in cambios] == [("Funda", 150.0), ("Ratón", -100.0)]


def test_referencia_de_productos_con_la_media(tmp_path):
    ruta = tmp_path / "historial_productos.csv"
    assert alertas.leer_productos_referencia(ruta) is None
    for numero, ventas in enumerate([{"A": 10.0, "B": 20.0}, {"A": 30.0}]):
        alertas.guardar_productos(ruta, pd.Series(ventas))
        # La fecha lleva segundos: se fija a mano para que las ejecuciones no coincidan.
        historial = pd.read_csv(ruta)
        historial.loc[historial.index[-len(ventas):], "fecha"] = f"2026-10-1{numero} 08:00:00"
        historial.to_csv(ruta, index=False)
    # B no se vendió la segunda semana: cuenta como 0 en la media.
    assert alertas.leer_productos_referencia(ruta).to_dict() == {"A": 20.0, "B": 10.0}


def test_productos_en_el_email_solo_informan(tmp_path, email_falso):
    # Mismo total que antes, pero el Teclado vendía 500 € de media y ahora 51 €.
    historial = tmp_path / "historial.csv"
    alertas.guardar_ejecucion(historial, {**SEMANA_1, "ventas_totales": 1375.99, "pedidos": 8})
    alertas.guardar_productos(alertas.ruta_historial_productos(historial),
                              pd.Series({"Portátil": 899.99, "Teclado": 500.0}))
    resultados = [(CSV_EJEMPLO, main.procesar_archivo(CSV_EJEMPLO, "€"))]
    comparacion = main.comparar_con_anteriores(resultados, historial, umbral=30, umbral_producto=50)
    assert [p["producto"] for p in comparacion["productos"]] == ["Teclado"]
    main.enviar_por_email(resultados, "€", comparacion)

    mensaje = email_falso[0][1]
    assert "⚠" not in mensaje["Subject"]  # un producto no es motivo de aviso
    cuerpo = mensaje.get_body(preferencelist=("html",)).get_content()
    assert "Productos que más cambiaron" in cuerpo and "Teclado" in cuerpo
    assert "Sin cambios bruscos respecto a la semana anterior" in cuerpo
