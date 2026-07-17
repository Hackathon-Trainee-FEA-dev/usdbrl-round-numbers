"""
Checagem de poder: um efeito do tamanho do que Osler (2000) mediu em pares
G10 seria detectado pelo teste confirmatorio deste projeto?

Motivacao: o resultado nulo (round numbers E extremos locais -- ver README,
secao "Diagnostico do nulo") pode, em principio, refletir tanto uma real
ausencia de efeito quanto uma falha de poder estatistico ou um bug na
deteccao/classificacao de eventos. Para descartar as duas ultimas hipoteses:

  1. Toma os eventos REAIS da grade R$0,05 (desenho primario).
  2. Injeta artificialmente um vies de reversao controlado -- converte uma
     fracao aleatoria dos eventos de "continuation" em "bounce", elevando a
     frequencia de bounce agregada em `lift_pp` pontos percentuais.
  3. Reaplica o teste confirmatorio REAL (stats.run_confirmatory_test)
     contra o controle REAL (o mesmo 20R+20S/dia usado no resto do
     projeto) -- so os outcomes da grade tratada sao alterados.

+4,6pp nao e arbitrario: e o efeito que a propria Osler mede para o marco
alemao (ela reporta +4,2pp marco, +5,6pp iene, +4,0pp libra -- Table 8,
p.61 do paper original). Se o teste confirmatorio flagar esse tamanho de
efeito como significativo, isso descarta falha de poder/bug como explicacao
do nulo observado nos dados reais.

N=500 conjuntos de controle aqui (nao 5.000) -- poder aproximado e
suficiente para este diagnostico, e mais rapido de rodar.

Uso: python -m src.power_check
"""
import os

import numpy as np
import pandas as pd

from src import round_levels, events, stats

RAW_PATH = "data/raw/usdbrl_m1_fbs_demo.csv"
OUT_PATH = "results/power_check.csv"

TOL, WINDOW = 0.0001, 15
N_SETS = 500
SEED = 42
LIFTS_PP = [0.0, 0.02, 0.04, 0.046, 0.06, 0.08, 0.10]


def inject_lift(grid_events: pd.DataFrame, lift_pp: float, rng: np.random.Generator) -> pd.DataFrame:
    """
    Converte uma fracao aleatoria de eventos 'continuation' em 'bounce' para
    elevar a frequencia de bounce agregada em ~lift_pp pontos percentuais.
    """
    d = grid_events.copy()
    cont_idx = d.index[d["outcome"] == "continuation"]
    need = int(round(lift_pp * len(d)))
    need = max(0, min(need, len(cont_idx)))
    flip = rng.choice(cont_idx, size=need, replace=False)
    d.loc[flip, "outcome"] = "bounce"
    return d


def main():
    os.makedirs("results", exist_ok=True)
    df = pd.read_csv(RAW_PATH)
    df = events.filter_session(df)
    price_min, price_max = df["low"].min(), df["high"].max()
    grids = round_levels.all_round_levels(price_min, price_max)

    round_ev = events.run_round_level_events(df, grids, tolerance_pct=TOL, window_min=WINDOW)
    grid05 = round_ev[round_ev["grid"] == "0.05"].copy()
    print(f"grade 0.05: {len(grid05)} eventos, bounce observado = {(grid05['outcome'] == 'bounce').mean():.4f}")

    ctrl = events.run_control_monthly_stats(df, n_sets=N_SETS, seed=SEED, tolerance_pct=TOL, window_min=WINDOW)

    rng = np.random.default_rng(1)
    rows = []
    for lift in LIFTS_PP:
        injected = inject_lift(grid05, lift, rng)
        injected["grid"] = "0.05"
        res = stats.run_confirmatory_test(injected, ctrl)
        row = res[(res["grade"] == "0.05") & (res["hipotese"] == "H1a_bounce")].iloc[0]
        rows.append({
            "lift_pp": lift,
            "bounce_observado": row["estatistica_obs"],
            "p_binomial": row["p_binomial"],
            "p_montecarlo": row["p_montecarlo"],
            "meses_BPmaiorBA": f"{row['sucessos_BPmaiorBA']}/{row['n_meses']}",
        })

    out = pd.DataFrame(rows)
    with pd.option_context("display.float_format", lambda v: f"{v:.4f}"):
        print(out.to_string(index=False))
    out.to_csv(OUT_PATH, index=False)
    print(f"\nResultados salvos em {OUT_PATH}")


if __name__ == "__main__":
    main()
