from formato import numero


def test_numero_en_formato_espanol():
    assert numero(1234567.891) == "1.234.567,89"
    assert numero(12.5) == "12,50"
    assert numero(-475870.26) == "-475.870,26"
    assert numero(19773, 0) == "19.773"
    assert numero(4.25, 1) == "4,2"  # redondeo de Python: al par más cercano
