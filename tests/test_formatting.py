from formatting import number


def test_number_with_thousands_separators():
    assert number(1234567.891) == "1,234,567.89"
    assert number(12.5) == "12.50"
    assert number(-475870.26) == "-475,870.26"
    assert number(19773, 0) == "19,773"
    assert number(4.25, 1) == "4.2"  # Python rounding: to the nearest even number
