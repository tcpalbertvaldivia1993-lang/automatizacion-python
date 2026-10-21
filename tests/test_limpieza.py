import pandas as pd

from limpieza import calcular_indicadores, convertir_cantidad, convertir_precio, limpiar_ventas


def crear_df(filas):
    columnas = ["id_pedido", "fecha", "cliente", "producto", "cantidad", "precio_unitario"]
    return pd.DataFrame(filas, columns=columnas)


def test_convertir_precio():
    assert convertir_precio("7,50") == 7.5
    assert convertir_precio("899.99 €") == 899.99
    assert convertir_precio("abc") is None
    assert convertir_precio("") is None


def test_convertir_cantidad():
    assert convertir_cantidad("3") == 3
    assert convertir_cantidad("2.5") is None
    assert convertir_cantidad("dos") is None
    assert convertir_cantidad("") is None


def test_duplicados_con_espacios_se_eliminan():
    df = crear_df([
        ["1", "2026-09-01", " Ana ", "Teclado", "1", "10"],
        ["1", "2026-09-01", "Ana", "Teclado", "1", "10"],
    ])
    limpio, descartadas = limpiar_ventas(df)
    assert len(limpio) == 1
    assert limpio.loc[0, "cliente"] == "Ana"
    assert descartadas.loc[0, "motivo"] == "fila duplicada"


def test_cantidades_y_precios_invalidos_se_descartan():
    df = crear_df([
        ["1", "2026-09-01", "Ana", "Teclado", "", "10"],
        ["2", "2026-09-01", "Ana", "Teclado", "-1", "10"],
        ["3", "2026-09-01", "Ana", "Teclado", "1", "abc"],
        ["4", "2026-09-01", "Ana", "Teclado", "1", "-5"],
        ["5", "2026-09-01", "Ana", "Teclado", "2", "10"],
    ])
    limpio, descartadas = limpiar_ventas(df)
    assert list(limpio["id_pedido"]) == ["5"]
    assert len(descartadas) == 4


def test_indicadores():
    df = crear_df([
        ["1", "2026-09-01", "Ana", "Teclado", "2", "10"],
        ["1", "2026-09-01", "Ana", "Ratón", "1", "5"],
        ["2", "2026-09-02", "Luis", "Monitor", "1", "100"],
    ])
    limpio, _ = limpiar_ventas(df)
    indicadores = calcular_indicadores(limpio)
    assert indicadores == {"ventas_totales": 125.0, "pedidos": 2, "valor_medio_pedido": 62.5}
