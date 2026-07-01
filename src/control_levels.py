"""
Gerador de niveis de controle (placebo) de Osler (2000).

Para cada dia de pregao, gera dois niveis artificiais -- um "acima" (R) e um
"abaixo" (S) da abertura -- a partir da propria abertura do dia e de uma
escala de range mensal:

    R = Open_dia + b * range_mes
    S = Open_dia - a * range_mes
    a, b ~ Uniforme(0, 1)

`range_mes` = maior gap absoluto entre abertura e as maximas/minimas
intradiarias observadas nos dias daquele mes, i.e.:

    range_mes = max_d( max(high_d - open_d, open_d - low_d) )  para d no mes

Osler (2000) gerou 10.000 conjuntos completos de niveis de controle pra
comparar a taxa de bounce/continuacao nos niveis redondos reais vs. nesses
niveis artificiais. Aqui o numero de conjuntos (`n_sets`) e parametrizavel
pra ajustar o custo computacional (ver README.md / memoria do projeto —
decisao ja tomada de reduzir N se necessario, sem abrir mao do desenho).
"""
import numpy as np
import pandas as pd


def build_daily_ohlc(df: pd.DataFrame, time_col: str = "time") -> pd.DataFrame:
    """Agrega o M1 em OHLC diario (open = primeira barra, high = max, low = min)."""
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
    """Calcula o range mensal (maior gap absoluto abertura->extremo) e anexa em cada linha diaria."""
    d = daily.copy()
    d["day_gap"] = np.maximum(d["high"] - d["open"], d["open"] - d["low"])
    monthly_range = d.groupby("month")["day_gap"].max().rename("month_range")
    d = d.merge(monthly_range, on="month", how="left")
    return d


def generate_control_levels(df: pd.DataFrame, n_sets: int = 200, seed: int = 42, time_col: str = "time") -> pd.DataFrame:
    """
    Gera `n_sets` conjuntos completos de niveis de controle (R e S por dia
    de pregao), seguindo o algoritmo de Osler (2000) descrito no topo deste
    arquivo.

    Retorna um DataFrame em formato longo:
        set_id, date, level_type ('R' ou 'S'), level

    `n_sets` default = 200 (nao 10.000 como Osler) por custo computacional
    do scan de eventos que vem depois (ver events.py) -- ajustavel. Rodar
    com N maior e um passo de robustez a considerar antes da versao final
    do teste confirmatorio, nao um requisito pra essa primeira implementacao.
    """
    daily = compute_monthly_range(build_daily_ohlc(df, time_col=time_col))
    rng = np.random.default_rng(seed)

    n_days = len(daily)
    opens = daily["open"].to_numpy()
    ranges = daily["month_range"].to_numpy()
    dates = daily["date"].to_numpy()

    # a, b ~ U(0,1), shape (n_sets, n_days)
    a = rng.uniform(0.0, 1.0, size=(n_sets, n_days))
    b = rng.uniform(0.0, 1.0, size=(n_sets, n_days))

    R = opens[None, :] + b * ranges[None, :]
    S = opens[None, :] - a * ranges[None, :]

    set_ids = np.repeat(np.arange(n_sets), n_days)
    date_tiled = np.tile(dates, n_sets)

    out_R = pd.DataFrame({"set_id": set_ids, "date": date_tiled, "level_type": "R", "level": R.ravel()})
    out_S = pd.DataFrame({"set_id": set_ids, "date": date_tiled, "level_type": "S", "level": S.ravel()})
    return pd.concat([out_R, out_S], ignore_index=True)
