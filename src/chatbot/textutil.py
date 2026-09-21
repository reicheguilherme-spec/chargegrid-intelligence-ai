"""Funcoes de texto compartilhadas."""
import re
import unicodedata


def norm(texto: str) -> str:
    """minusculas e sem acentos (para comparar textos)."""
    t = unicodedata.normalize("NFD", str(texto).lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def fmt_br(x, casas=1) -> str:
    """Numero no padrao brasileiro: 1.234,5"""
    s = f"{float(x):,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def decimais_ponto(texto: str) -> str:
    """Troca virgula decimal por ponto (36,2 -> 36.2) para facilitar comparacoes."""
    return re.sub(r"(?<=\d),(?=\d)", ".", texto)
