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
    assert "£" in (carpeta / "informe.md").read_text(encoding="utf-8")


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
