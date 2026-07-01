"""
Gerador de niveis de controle (placebo) de Osler (2000) -- versao LITERAL.

Para cada dia de pregao, Osler gera **20 suportes (S) + 20 resistencias (R)**
por dia, a partir da abertura do dia e de uma escala de range mensal:

    R_i = Open_dia + b_i * range_mes      b_i ~ Uniforme(0, 1)
    S_i = Open_dia - a_i * range_mes      a_i ~ Uniforme(0, 1)     i = 1..20

`range_mes` = maior gap absoluto entre a abertura e as maximas/minimas
intradiarias observadas nos dias daquele mes:

    range_mes = max_d( max(high_d - open_d, open_d - low_d) )  para d no mes

Os niveis artificiais sao **arredondados a precisao de cotacao** (Osler 2000,
endnote 3). Para o USD/BRL a cotacao tem 4 casas decimais (pip = 0,0001).

Osler gerou **10.000 conjuntos completos** desses niveis. Aqui `n_sets` e
parametrizavel; o run primario usa 5.000 (meio-termo defensavel: BA_mes e uma
media sobre conjuntos e converge muito antes de 10.000 -- ver stats.py).

## Reproducibilidade / geracao "preguicosa"

Materializar 5.000 conjuntos x 224 dias x 40 niveis = ~45M niveis num
DataFrame e pesado. O scan de eventos de controle (events.run_control_...)
gera os niveis **por dia, sob demanda**, consumindo o mesmo gerador seedado
na mesma ordem de dias -- por isso o desenho das funcoes aqui expoe tanto o
OHLC diario/range mensal quanto um helper de sorteio por dia.
"""
import numpy as np
import pandas as pd

QUOTE_DECIMALS = 4          # precisao de cotacao do USD/BRL (pip = 0,0001)
LEVELS_PER_SIDE = 20        # 20 R + 20 S por dia (literal Osler 2000)


def build_daily_ohlc(df: pd.DataFrame, time_col: str = "time") -> pd.DataFrame:
    """Agrega o M1 (ja filtrado por sessao) em OHLC diario."""
    d = df.copy()
    d[time_col] = pd.to_datetime(d[time_col], utc=True)
    d["date"] = d[time_col].dt.date
    daily = (
        d.groupby("date")
        .agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"))
        .reset_index()
    )
    daily["month"] = pd.to_datetime(daily["date"]).dt.to_period("M")
    return daily


def compute_monthly_range(daily: pd.DataFrame) -> pd.DataFrame:
    """Range mensal (maior gap absoluto abertura->extremo) anexado em cada linha diaria."""
    d = daily.copy()
    d["day_gap"] = np.maximum(d["high"] - d["open"], d["open"] - d["low"])
    monthly_range = d.groupby("month")["day_gap"].max().rename("month_range")
    d = d.merge(monthly_range, on="month", how="left")
    return d


def daily_levels_table(df: pd.DataFrame, time_col: str = "time") -> pd.DataFrame:
    """
    Tabela por dia com o que o sorteio de niveis precisa: date, month,
    open, month_range. Base tanto pra geracao materializada quanto pra
    geracao sob demanda no scan.
    """
    return compute_monthly_range(build_daily_ohlc(df, time_col=time_col))


def draw_day_levels(open_px: float, month_range: float, n_sets: int,
                    rng: np.random.Generator, levels_per_side: int = LEVELS_PER_SIDE):
    """
    Sorteia os niveis de um unico dia para todos os `n_sets` conjuntos.

    Retorna (levels, set_ids, side) todos com shape (n_sets * 2 * levels_per_side,):
        - levels: valor do nivel (ja arredondado a QUOTE_DECIMALS)
        - set_ids: indice do conjunto (0..n_sets-1) a que o nivel pertence
        - side: 'R' ou 'S'
    O consumo do `rng` e deterministico dado o seed e a ordem dos dias.
    """
    a = rng.uniform(0.0, 1.0, size=(n_sets, levels_per_side))   # S
    b = rng.uniform(0.0, 1.0, size=(n_sets, levels_per_side))   # R
    R = np.round(open_px + b * month_range, QUOTE_DECIMALS)
    S = np.round(open_px - a * month_range, QUOTE_DECIMALS)

    levels = np.concatenate([R.ravel(), S.ravel()])
    set_ids = np.concatenate([
        np.repeat(np.arange(n_sets), levels_per_side),
        np.repeat(np.arange(n_sets), levels_per_side),
    ])
    side = np.concatenate([
        np.full(n_sets * levels_per_side, "R"),
        np.full(n_sets * levels_per_side, "S"),
    ])
    return levels, set_ids, side


def generate_control_levels(df: pd.DataFrame, n_sets: int = 200, seed: int = 42,
                            levels_per_side: int = LEVELS_PER_SIDE,
                            time_col: str = "time") -> pd.DataFrame:
    """
    Versao MATERIALIZADA (formato longo) -- util para inspecao/testes com N
    pequeno. Para o run confirmatorio use o scan sob demanda em events.py,
    que nao materializa os ~45M niveis.

    Retorna DataFrame: set_id, date, month, level_type ('R'/'S'), level.
    """
    daily = daily_levels_table(df, time_col=time_col)
    rng = np.random.default_rng(seed)

    frames = []
    for row in daily.itertuples(index=False):
        levels, set_ids, side = draw_day_levels(row.open, row.month_range, n_sets, rng, levels_per_side)
        frames.append(pd.DataFrame({
            "set_id": set_ids,
            "date": row.date,
            "month": row.month,
            "level_type": side,
            "level": levels,
        }))
    return pd.concat(frames, ignore_index=True)
