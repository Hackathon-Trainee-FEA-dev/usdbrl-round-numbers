"""
Niveis de suporte/resistencia por extremo local ("swing point") -- a
operacionalizacao deste projeto do segundo ingrediente que Osler cita como
fonte dos niveis publicados pelas firmas (o outro e numero redondo, ja
testado em round_levels.py). Ver endnote 8 de Osler (2000):

    "I examine whether round numbers or local minima/maxima (both of which
    are known to be sources of published support and resistance levels)
    have predictive power for exchange rate bounces. I find that they do."

## Nota de integridade

O algoritmo EXATO que Osler usou nesse teste especifico esta num paper irmao
NAO publicado ("Are Currency Markets Efficient? Predictable Trend Reversals
in Intraday Exchange Rates", FRBNY, fev/2000) e nao foi localizado (nem a
propria FRBNY o disponibiliza online). Este modulo e, portanto, uma
operacionalizacao PROPRIA e documentada do conceito de "minimo/maximo
local" -- ao contrario do controle 20R+20S (control_levels.py), que E uma
replica literal do algoritmo publicado no paper principal.

## Definicao (fractal classico de swing point)

Um dia `i` da serie diaria (ja filtrada por sessao) e um MAXIMO LOCAL
("resistencia") confirmado se seu high for estritamente maior que o high de
TODOS os `k` dias anteriores e de TODOS os `k` dias seguintes. Simetrico
para MINIMO LOCAL ("suporte") via low. `k=5` dias e o default (fractal
padrao de 5 barras, popularizado por Bill Williams -- escolha documentada,
nao arbitraria, mas tambem nao testada por robustez ainda).

A confirmacao so e possivel `k` dias DEPOIS do dia candidato (e preciso ver
os k dias seguintes para saber que ele foi o extremo). O nivel so entra na
lista de "ativos" a partir do dia seguinte ao da confirmacao -- sem
look-ahead: nenhum dia usa informacao que ainda nao existia naquele ponto do
tempo.

## Roster diario

Para manter comparabilidade estatistica com o controle de Osler (20
resistencias + 20 suportes por dia), o roster de cada dia e formado pelos
20 swings de alta e os 20 de baixa CONFIRMADOS MAIS RECENTES ate aquele dia
(pode ser menos no inicio da amostra, antes de haver 20 confirmados).
Niveis arredondados a precisao de cotacao (4 casas, igual ao controle).
"""
import pandas as pd

from src.control_levels import build_daily_ohlc, QUOTE_DECIMALS

FRACTAL_WINDOW = 5      # k dias de cada lado p/ confirmar um swing point
LEVELS_PER_SIDE = 20    # roster diario: 20 R + 20 S mais recentes (paridade com Osler)


def find_swing_points(daily: pd.DataFrame, k: int = FRACTAL_WINDOW) -> pd.DataFrame:
    """
    Detecta maximos/minimos locais confirmados na serie diaria (colunas
    date, high, low -- ja ordenada por data, uma linha por dia de pregao).

    Retorna uma linha por swing point:
        date            dia do extremo
        confirmed_date  dia a partir do qual o nivel pode ser usado sem
                        look-ahead (= date + k dias de pregao)
        level_type      'R' (maximo/resistencia) ou 'S' (minimo/suporte)
        level           high ou low do dia, arredondado a QUOTE_DECIMALS
    """
    d = daily.sort_values("date").reset_index(drop=True)
    highs = d["high"].to_numpy()
    lows = d["low"].to_numpy()
    dates = d["date"].to_numpy()
    n = len(d)

    rows = []
    for i in range(k, n - k):
        if highs[i] > highs[i - k:i].max() and highs[i] > highs[i + 1:i + k + 1].max():
            rows.append({
                "date": dates[i], "confirmed_date": dates[i + k],
                "level_type": "R", "level": round(float(highs[i]), QUOTE_DECIMALS),
            })
        if lows[i] < lows[i - k:i].min() and lows[i] < lows[i + 1:i + k + 1].min():
            rows.append({
                "date": dates[i], "confirmed_date": dates[i + k],
                "level_type": "S", "level": round(float(lows[i]), QUOTE_DECIMALS),
            })
    return pd.DataFrame(rows, columns=["date", "confirmed_date", "level_type", "level"])


def daily_active_levels(df: pd.DataFrame, k: int = FRACTAL_WINDOW,
                        levels_per_side: int = LEVELS_PER_SIDE,
                        time_col: str = "time") -> dict:
    """
    Para cada dia de pregao da amostra, retorna a lista de niveis ativos:
    os `levels_per_side` swings de resistencia + `levels_per_side` de
    suporte mais recentemente CONFIRMADOS antes daquele dia (confirmed_date
    < date do dia -- sem look-ahead).

    Retorna dict {date: [niveis...]} (lista simples, R e S juntos -- o scan
    de eventos nao precisa da distincao de lado, so o valor do nivel).
    """
    daily = build_daily_ohlc(df, time_col=time_col)
    swings = find_swing_points(daily, k=k)
    all_dates = sorted(daily["date"].unique())

    swings_r = swings[swings["level_type"] == "R"].sort_values("confirmed_date")
    swings_s = swings[swings["level_type"] == "S"].sort_values("confirmed_date")

    roster = {}
    for d in all_dates:
        avail_r = swings_r.loc[swings_r["confirmed_date"] < d, "level"].tail(levels_per_side).tolist()
        avail_s = swings_s.loc[swings_s["confirmed_date"] < d, "level"].tail(levels_per_side).tolist()
        roster[d] = avail_r + avail_s
    return roster
