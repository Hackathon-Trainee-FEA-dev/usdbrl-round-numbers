"""
Driver do teste confirmatorio ponta a ponta -- desenho LITERAL de Osler (2000).

Pipeline:
  1. Carrega o snapshot M1 e FILTRA pela sessao liquida (equivalente BR ao
     recorte 9h-16h NY de Osler -- ver events.filter_session).
  2. Gera as grades de niveis redondos.
  3. Para cada variante de parametro (banda/janela): detecta+classifica os
     eventos redondos e roda o scan mensal de controle (20R+20S/dia, N
     conjuntos), e aplica o teste confirmatorio:
       - PRIMARIO: sinal binomial mensal (BP_mes > BA_mes) -- literal Osler.
       - COMPLEMENTAR: p-valor empirico Monte Carlo (r+1)/(N+1).

Parametros (pre-registrado -- ver README.md):
  - primario:  banda 0,01% (0.0001), janela 15 min
  - robustez:  banda 0,00% e 0,02%; janela 30 min

N_SETS = 5000 (meio-termo entre 2.000 e os 10.000 de Osler; BA_mes e uma media
sobre conjuntos e converge bem antes de 10.000). Parametrizavel.

Saida: results/confirmatory_results.csv + resumo no stdout.
Uso: python -m src.run_analysis   (a partir da raiz do repositorio)
"""
import os
import time
import pandas as pd

from src import round_levels, events, stats

RAW_PATH = "data/raw/usdbrl_m1_fbs_demo.csv"
OUT_DIR = "results"
OUT_PATH = os.path.join(OUT_DIR, "confirmatory_results.csv")

N_SETS = 5000
SEED = 42

# (nome, tolerance_pct, window_min, is_primary)
PARAM_SETS = [
    ("primario_0.01pct_15min", 0.0001, 15, True),
    ("robustez_0.00pct_15min", 0.0000, 15, False),
    ("robustez_0.02pct_15min", 0.0002, 15, False),
    ("robustez_0.01pct_30min", 0.0001, 30, False),
]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    df = pd.read_csv(RAW_PATH)

    # (1) filtro de sessao -- aplicado UMA vez, upstream de tudo.
    df = events.filter_session(df)
    print(f"Barras apos filtro de sessao [{events.SESSION_START},{events.SESSION_END}): {len(df)}")

    # (2) grades de niveis redondos (sobre o range da sessao).
    price_min, price_max = df["low"].min(), df["high"].max()
    grids = round_levels.all_round_levels(price_min, price_max)

    all_results = []
    for name, tol, window, is_primary in PARAM_SETS:
        t0 = time.time()
        round_ev = events.run_round_level_events(df, grids, tolerance_pct=tol, window_min=window)
        ctrl = events.run_control_monthly_stats(df, n_sets=N_SETS, seed=SEED,
                                                tolerance_pct=tol, window_min=window)
        res = stats.run_confirmatory_test(round_ev, ctrl)
        res.insert(0, "parametro", name)
        res.insert(1, "primario", is_primary)
        all_results.append(res)
        print(f"[{name}] round={len(round_ev)} eventos, {len(ctrl['months'])} meses, "
              f"N={N_SETS} conjuntos, {time.time()-t0:.1f}s")

    results = pd.concat(all_results, ignore_index=True)
    results.to_csv(OUT_PATH, index=False)
    print(f"\nResultados salvos em {OUT_PATH}\n")

    primary = results[results["primario"]].copy()
    with pd.option_context("display.max_columns", None, "display.width", 200,
                           "display.float_format", lambda v: f"{v:.4f}"):
        print("=== Desenho primario (banda 0,01%, janela 15 min) ===")
        cols = ["grade", "hipotese", "placebo", "n_meses", "sucessos_BPmaiorBA",
                "p_binomial", "estatistica_obs", "nula_media", "p_montecarlo"]
        print(primary[cols].to_string(index=False))


if __name__ == "__main__":
    main()
