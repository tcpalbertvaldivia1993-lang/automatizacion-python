import pandas as pd

from graficos import grafico_ventas_por_dia, grafico_ventas_por_producto


def crear_limpio():
    return pd.DataFrame({
        "fecha": ["2026-09-01", "2026-09-01", "2026-09-04"],
        "producto": ["Teclado", "Ratón", "Teclado"],
        "importe": [20.0, 5.0, 10.0],
    })


def test_ventas_por_producto(tmp_path):
    ruta = tmp_path / "producto.png"
    datos = grafico_ventas_por_producto(crear_limpio(), ruta)
    assert ruta.exists()
    assert datos.to_dict() == {"Teclado": 30.0, "Ratón": 5.0}


def test_ventas_por_dia_rellena_dias_sin_ventas(tmp_path):
    ruta = tmp_path / "dia.png"
    datos = grafico_ventas_por_dia(crear_limpio(), ruta)
    assert ruta.exists()
    assert datos.to_dict() == {
        "2026-09-01": 25.0,
        "2026-09-02": 0.0,
        "2026-09-03": 0.0,
        "2026-09-04": 10.0,
    }
