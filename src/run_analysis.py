"""
Driver do teste confirmatorio ponta a ponta.

Carrega o snapshot M1, gera niveis redondos e de controle, detecta e
classifica os eventos (bounce/continuacao) e roda o teste de p-valor
empirico (redondo vs. distribuicao nula dos controles), para o desenho
primario e para as variantes de robustez de Osler.

Parametros (desenho pre-registrado -- ver README.md):
    - primario:   banda 0,01% (0.0001), janela 15 min
    - robustez:   banda 0,00% e 0,02% (0.0 e 0.0002); janela 30 min

Saida: results/confirmatory_results.csv (uma linha por grade x hipotese x
variante de parametro) + resumo impresso no stdout.

Uso: python -m src.run_analysis   (a partir da raiz do repositorio)
"""
import os
import time
import pandas as pd

from src import round_levels, control_levels, events, stats

RAW_PATH = "data/raw/usdbrl_m1_fbs_demo.csv"
OUT_DIR = "results"
OUT_PATH = os.path.join(OUT_DIR, "confirmatory_results.csv")

N_SETS = 2000
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
    price_min, price_max = df["low"].min(), df["high"].max()
    grids = round_levels.all_round_levels(price_min, price_max)

    # niveis de controle nao dependem de tolerancia/janela -> gera uma vez.
    print(f"Gerando {N_SETS} conjuntos de niveis de controle (seed={SEED})...")
    ctrl_levels = control_levels.generate_control_levels(df, n_sets=N_SETS, seed=SEED)

    all_results = []
    for name, tol, window, is_primary in PARAM_SETS:
        t0 = time.time()
        round_ev = events.run_round_level_events(df, grids, tolerance_pct=tol, window_min=window)
        ctrl_ev = events.run_control_level_events(df, ctrl_levels, tolerance_pct=tol, window_min=window)
        res = stats.run_confirmatory_test(round_ev, ctrl_ev)
        res.insert(0, "parametro", name)
        res.insert(1, "primario", is_primary)
        all_results.append(res)
        print(f"[{name}] round={len(round_ev)} eventos, control={len(ctrl_ev)} eventos, {time.time()-t0:.1f}s")

    results = pd.concat(all_results, ignore_index=True)
    results.to_csv(OUT_PATH, index=False)
    print(f"\nResultados salvos em {OUT_PATH}\n")

    # resumo do desenho primario
    primary = results[results["primario"]].copy()
    with pd.option_context("display.max_columns", None, "display.width", 160, "display.float_format", lambda v: f"{v:.4f}"):
        print("=== Desenho primario (banda 0,01%, janela 15 min) ===")
        print(primary[["grade", "hipotese", "placebo", "n_eventos", "estatistica_obs", "nula_media", "p_empirico", "p_bonferroni"]].to_string(index=False))


if __name__ == "__main__":
    main()
