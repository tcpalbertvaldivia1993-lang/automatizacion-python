import shutil
from pathlib import Path

import pandas as pd
import pytest

import main

CSV_EJEMPLO = Path(__file__).resolve().parent.parent / "datos" / "ventas_ejemplo.csv"


@pytest.fixture(autouse=True)
def resultados_temporales(tmp_path, monkeypatch):
    """Los resultados de las pruebas van a una carpeta temporal, no a resultados/."""
    carpeta = tmp_path / "resultados"
    carpeta.mkdir()
    monkeypatch.setattr(main, "CARPETA_RESULTADOS", carpeta)
    return carpeta


def test_excel_da_lo_mismo_que_csv(tmp_path):
    excel = tmp_path / "ventas.xlsx"
    pd.read_csv(CSV_EJEMPLO, dtype=str, keep_default_na=False).to_excel(excel, index=False)
    assert main.procesar_archivo(excel, "€") == main.procesar_archivo(CSV_EJEMPLO, "€")


def test_resultados_en_una_carpeta_por_archivo(resultados_temporales):
    main.procesar_archivo(CSV_EJEMPLO, "£")
    carpeta = resultados_temporales / "ventas_ejemplo"
    assert (carpeta / "ventas_limpio.csv").exists()
    assert (carpeta / "graficos" / "ventas_por_producto.png").exists()
    html = (carpeta / "informe.html").read_text(encoding="utf-8")
    assert "1.375,99 £" in html                      # formato español y moneda elegida
    assert html.count("data:image/png;base64,") == 2  # los dos gráficos van dentro del HTML


def test_el_html_no_ejecuta_texto_de_los_datos(tmp_path, resultados_temporales):
    archivo = tmp_path / "raro.csv"
    archivo.write_text(
        "id_pedido,fecha,cliente,producto,cantidad,precio_unitario\n"
        "1,2026-09-01,Ana,<script>alert(1)</script>,1,10\n",
        encoding="utf-8",
    )
    main.procesar_archivo(archivo, "€")
    html = (resultados_temporales / "raro" / "informe.html").read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_resumen_html(tmp_path, resultados_temporales):
    roto = tmp_path / "roto.csv"
    roto.write_text("pedido,total\n1,10\n", encoding="utf-8")
    resultados = [(CSV_EJEMPLO, main.procesar_archivo(CSV_EJEMPLO, "€")), (roto, None)]
    html = main.escribir_resumen(resultados, "€").read_text(encoding="utf-8")
    assert 'href="ventas_ejemplo/informe.html"' in html
    assert "No se pudo procesar" in html


def test_archivo_sin_columnas_correctas_devuelve_none(tmp_path):
    roto = tmp_path / "roto.csv"
    roto.write_text("pedido,total\n1,10\n", encoding="utf-8")
    assert main.procesar_archivo(roto, "€") is None


def test_buscar_archivos_solo_csv_y_excel(tmp_path):
    for nombre in ["b.csv", "a.xlsx", "notas.txt"]:
        (tmp_path / nombre).write_text("", encoding="utf-8")
    (tmp_path / "procesados").mkdir()
    assert [a.name for a in main.buscar_archivos(tmp_path)] == ["a.xlsx", "b.csv"]


def test_mover_a_procesados(tmp_path):
    archivo = tmp_path / "ventas.csv"
    shutil.copy(CSV_EJEMPLO, archivo)
    main.mover_a_procesados(archivo)
    assert not archivo.exists()
    assert (tmp_path / "procesados" / "ventas.csv").exists()
