import pandas as pd

from graficos import MAX_PRODUCTOS, grafico_ventas_en_el_tiempo, grafico_ventas_por_producto


def crear_limpio():
    return pd.DataFrame({
        "fecha": ["2026-09-01", "2026-09-01", "2026-09-04"],
        "producto": ["Teclado", "Ratón", "Teclado"],
        "importe": [20.0, 5.0, 10.0],
    })


def test_ventas_por_producto(tmp_path):
    ruta = tmp_path / "producto.png"
    titulo, datos = grafico_ventas_por_producto(crear_limpio(), ruta)
    assert ruta.exists()
    assert titulo == "Ventas por producto"
    assert datos.to_dict() == {"Teclado": 30.0, "Ratón": 5.0}


def test_con_muchos_productos_solo_se_muestran_los_que_mas_venden(tmp_path):
    limpio = pd.DataFrame({
        "fecha": ["2026-09-01"] * 15,
        "producto": [f"Producto {i}" for i in range(15)],
        "importe": [float(i) for i in range(15)],
    })
    titulo, datos = grafico_ventas_por_producto(limpio, tmp_path / "producto.png")
    assert len(datos) == MAX_PRODUCTOS
    assert datos.index[0] == "Producto 14"
    assert titulo == f"Los {MAX_PRODUCTOS} productos más vendidos (de 15)"


def test_ventas_por_dia_rellena_dias_sin_ventas(tmp_path):
    ruta = tmp_path / "dia.png"
    titulo, datos = grafico_ventas_en_el_tiempo(crear_limpio(), ruta)
    assert ruta.exists()
    assert titulo == "Ventas por día"
    assert datos.to_dict() == {
        "2026-09-01": 25.0,
        "2026-09-02": 0.0,
        "2026-09-03": 0.0,
        "2026-09-04": 10.0,
    }


def test_con_muchos_dias_se_agrupa_por_mes(tmp_path):
    limpio = pd.DataFrame({
        "fecha": ["2026-01-10", "2026-01-20", "2026-04-05"],
        "producto": ["Teclado"] * 3,
        "importe": [10.0, 5.0, 7.0],
    })
    titulo, datos = grafico_ventas_en_el_tiempo(limpio, tmp_path / "mes.png")
    assert titulo == "Ventas por mes"
    assert datos.to_dict() == {"2026-01": 15.0, "2026-02": 0.0, "2026-03": 0.0, "2026-04": 7.0}
