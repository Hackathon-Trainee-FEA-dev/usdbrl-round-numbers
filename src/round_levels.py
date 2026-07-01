"""
Geracao da grade de niveis redondos nominais de USD/BRL.

Hierarquia (forca decrescente), conforme desenho pre-registrado (ver
README.md / memoria do projeto):

    R$1,00 / R$0,50 / R$0,10 / R$0,05  -> niveis testados como hipotese central
    R$0,01                              -> placebo de falsificacao (nivel
                                            "redondo" fraco demais pra ter
                                            efeito psicologico esperado;
                                            serve de checagem negativa)

Niveis sao nominais e fixos (ex.: 5.00, 5.10, 5.20, ...) -- nao dependem da
serie de precos em si, apenas do range observado, que define quais niveis
"existem" dentro da janela de dados disponivel.
"""
import numpy as np

# Grade oficial do desenho pre-registrado.
GRIDS = {
    "1.00": 1.00,
    "0.50": 0.50,
    "0.10": 0.10,
    "0.05": 0.05,
    "0.01_placebo": 0.01,
}


def generate_round_levels(price_min: float, price_max: float, step: float, pad: float = 0.0) -> np.ndarray:
    """
    Gera os niveis redondos nominais (multiplos exatos de `step`) que caem
    dentro de [price_min - pad, price_max + pad].

    `pad` permite incluir niveis logo fora do range observado (default 0 =
    so niveis dentro do range realmente observado nos dados).
    """
    lo = price_min - pad
    hi = price_max + pad
    if hi < lo:
        return np.array([])

    first = np.ceil(lo / step) * step
    n = int(np.floor((hi - first) / step)) + 1
    if n <= 0:
        return np.array([])

    levels = first + np.arange(n) * step
    # arredonda pra evitar sujeira de ponto flutuante (ex. 5.099999999999)
    decimals = max(0, -int(np.floor(np.log10(step))) + 2)
    return np.round(levels, decimals)


def all_round_levels(price_min: float, price_max: float) -> dict:
    """Retorna {nome_da_grade: array_de_niveis} pra todas as grades oficiais (GRIDS)."""
    return {name: generate_round_levels(price_min, price_max, step) for name, step in GRIDS.items()}
