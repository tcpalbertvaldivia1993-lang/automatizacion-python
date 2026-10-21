"""Formato de números en español, compartido por el informe y los gráficos."""


def numero(valor, decimales=2):
    """Formatea un número al estilo español: 1234567.891 -> "1.234.567,89"."""
    texto = f"{valor:,.{decimales}f}"  # formato inglés: 1,234,567.89
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")
