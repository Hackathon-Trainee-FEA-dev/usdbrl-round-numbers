"""
Event-study do toque em nivel: retorno acumulado medio, redondo vs. controle.

Alinha o instante do toque em k = 0 e acompanha o caminho do `close` de
-PRE a +POST minutos. O retorno acumulado e medido em basis points relativos
ao close do toque e **assinado pela direcao de aproximacao**:

    signed_k = sign * (close[i+k] - close[i]) / close[i] * 1e4
    sign = +1 se aproximou de baixo (subindo), -1 se de cima (descendo)

Assim, no eixo y:
    > 0  => CONTINUACAO (preco seguiu na direcao do rompimento)
    < 0  => REVERSAO / bounce (preco voltou pro lado de origem)

Se niveis redondos causassem reversao (H1a), a curva redonda pos-toque
ficaria ABAIXO da curva de controle. O grafico serve de leitura visual do
resultado nulo -- nao substitui o teste confirmatorio (ver stats.py).

Saidas:
    figures/event_study.png        figura estatica (research)
    results/event_study_paths.csv  media +/- erro-padrao por passo e grupo
                                    (reaproveitavel no dashboard Streamlit)

Uso: python -m src.event_study   (a partir da raiz do repositorio)
"""
import os

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src import round_levels, control_levels, events

RAW_PATH = "data/raw/usdbrl_m1_fbs_demo.csv"
FIG_DIR = "figures"
OUT_DIR = "results"

PRE, POST = 10, 30          # minutos antes/depois do toque
TOL = 0.0001               # banda primaria (0,01%)
MAX_GAP_MIN = 5
N_CONTROL_SETS = 25        # ~meio milhao de eventos pooled: media/banda ja
                           # convergem (viz, nao o teste -- o teste usa N=5000)
SEED = 42


# ---------------------------------------------------------------------------
# Extracao de caminhos assinados
# ---------------------------------------------------------------------------

def _signed_paths(close: np.ndarray, gaps: np.ndarray, gi: np.ndarray,
                  approach_below: np.ndarray, pre: int, post: int,
                  max_gap: float) -> np.ndarray:
    """
    Dado o indice global do toque (gi) e o lado de aproximacao, devolve a
    matriz (K_valid, pre+post+1) de retornos acumulados assinados em bps.
    Descarta eventos sem janela completa ou com gap > max_gap na janela.
    """
    n = close.size
    if gi.size == 0:
        return np.empty((0, pre + post + 1))

    lo, hi = gi - pre, gi + post
    ok = (lo >= 0) & (hi < n)
    gi, approach_below, lo, hi = gi[ok], approach_below[ok], lo[ok], hi[ok]
    if gi.size == 0:
        return np.empty((0, pre + post + 1))

    # gap dentro da janela contigua [lo+1 .. hi]
    gap_off = np.arange(-pre + 1, post + 1)
    gap_idx = gi[:, None] + gap_off[None, :]
    gap_ok = ~(gaps[gap_idx] > max_gap).any(axis=1)
    gi, approach_below = gi[gap_ok], approach_below[gap_ok]
    if gi.size == 0:
        return np.empty((0, pre + post + 1))

    offs = np.arange(-pre, post + 1)
    idx = gi[:, None] + offs[None, :]
    base = close[gi][:, None]
    sign = np.where(approach_below, 1.0, -1.0)[:, None]
    return sign * (close[idx] - base) / base * 1e4


def collect_round_paths(series: pd.DataFrame, grids: dict, tol: float,
                        pre: int, post: int, max_gap: float) -> dict:
    """{grade -> matriz (n_eventos, pre+post+1)} para os niveis redondos."""
    close = series["close"].to_numpy()
    gaps = series["gap_min"].to_numpy()

    out = {}
    for grid_name, levels in grids.items():
        gi_all, side_all = [], []
        for level in levels:
            ev = events.detect_touch_events(series, level, tol)
            if ev.empty:
                continue
            gi_all.append(ev["idx"].to_numpy())
            side_all.append(ev["approach_side"].to_numpy() == "below")
        if not gi_all:
            out[grid_name] = np.empty((0, pre + post + 1))
            continue
        gi = np.concatenate(gi_all)
        approach_below = np.concatenate(side_all)
        out[grid_name] = _signed_paths(close, gaps, gi, approach_below, pre, post, max_gap)
    return out


def collect_control_paths(df: pd.DataFrame, series: pd.DataFrame, n_sets: int, seed: int,
                          tol: float, pre: int, post: int, max_gap: float) -> np.ndarray:
    """Caminhos assinados de TODOS os niveis de controle (pooled), N conjuntos."""
    close = series["close"].to_numpy()
    high = series["high"].to_numpy()
    low = series["low"].to_numpy()
    gaps = series["gap_min"].to_numpy()

    daily = control_levels.daily_levels_table(df)
    series_dates = series["time"].dt.date
    day_positions = series_dates.groupby(series_dates).groups

    rng = np.random.default_rng(seed)
    gi_all, side_all = [], []

    for row in daily.itertuples(index=False):
        levels, _set_ids, _side = control_levels.draw_day_levels(
            row.open, row.month_range, n_sets, rng)
        day_pos = np.asarray(day_positions[row.date])
        if day_pos.size == 0:
            continue

        d_low, d_high = low[day_pos], high[day_pos]
        band_lo = levels[:, None] * (1 - tol)
        band_hi = levels[:, None] * (1 + tol)
        in_band = (d_low[None, :] <= band_hi) & (d_high[None, :] >= band_lo)
        shifted = np.concatenate([np.zeros((in_band.shape[0], 1), bool), in_band[:, :-1]], axis=1)
        event_start = in_band & ~shifted

        ev_rows, ev_cols = np.nonzero(event_start)
        if ev_rows.size == 0:
            continue
        gi = day_pos[ev_cols]
        keep = gi > 0
        gi, ev_rows = gi[keep], ev_rows[keep]
        approach_below = close[gi - 1] < levels[ev_rows]
        gi_all.append(gi)
        side_all.append(approach_below)

    if not gi_all:
        return np.empty((0, pre + post + 1))
    gi = np.concatenate(gi_all)
    approach_below = np.concatenate(side_all)
    return _signed_paths(close, gaps, gi, approach_below, pre, post, max_gap)


# ---------------------------------------------------------------------------
# Agregacao + plot
# ---------------------------------------------------------------------------

def _mean_se(paths: np.ndarray):
    if paths.shape[0] == 0:
        w = paths.shape[1]
        return np.full(w, np.nan), np.full(w, np.nan), 0
    mean = paths.mean(axis=0)
    se = paths.std(axis=0, ddof=1) / np.sqrt(paths.shape[0]) if paths.shape[0] > 1 else np.zeros(paths.shape[1])
    return mean, se, paths.shape[0]


def main():
    os.makedirs(FIG_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    df = events.filter_session(pd.read_csv(RAW_PATH))
    series = events._prepare_series(df)
    price_min, price_max = df["low"].min(), df["high"].max()
    grids = round_levels.all_round_levels(price_min, price_max)

    print("Coletando caminhos dos niveis redondos...")
    round_paths = collect_round_paths(series, grids, TOL, PRE, POST, MAX_GAP_MIN)
    print(f"Coletando caminhos de controle (N={N_CONTROL_SETS} conjuntos)...")
    ctrl_paths = collect_control_paths(df, series, N_CONTROL_SETS, SEED, TOL, PRE, POST, MAX_GAP_MIN)

    k = np.arange(-PRE, POST + 1)

    # tabela de saida (media +/- SE por grupo) p/ reuso no dashboard
    rows = []
    groups = {"1.00": "R$1,00", "0.50": "R$0,50", "0.10": "R$0,10",
              "0.05": "R$0,05", "0.01_placebo": "R$0,01 (placebo)"}
    for gname, label in groups.items():
        mean, se, n = _mean_se(round_paths.get(gname, np.empty((0, len(k)))))
        for i, kk in enumerate(k):
            rows.append({"grupo": label, "k_min": int(kk), "mean_bps": mean[i], "se_bps": se[i], "n_eventos": n})
    cm, cse, cn = _mean_se(ctrl_paths)
    for i, kk in enumerate(k):
        rows.append({"grupo": "Controle (Osler)", "k_min": int(kk), "mean_bps": cm[i], "se_bps": cse[i], "n_eventos": cn})
    pd.DataFrame(rows).to_csv(os.path.join(OUT_DIR, "event_study_paths.csv"), index=False)

    # ---- figura: 2 paineis (caminho completo + zoom pos-toque) ----
    colors = {"1.00": "#1f77b4", "0.50": "#2ca02c", "0.10": "#ff7f0e", "0.05": "#d62728"}

    def _draw(ax, kx, mask):
        ax.plot(kx, cm[mask], color="black", lw=2.2, label=f"Controle (Osler), n={cn:,}", zorder=5)
        ax.fill_between(kx, (cm - 1.96 * cse)[mask], (cm + 1.96 * cse)[mask],
                        color="black", alpha=0.12, zorder=1)
        for gname, color in colors.items():
            mean, se, n = _mean_se(round_paths.get(gname, np.empty((0, len(k)))))
            if n == 0:
                continue
            ax.plot(kx, mean[mask], color=color, lw=1.6, label=f"{groups[gname]}, n={n:,}")
        mean, se, n = _mean_se(round_paths.get("0.01_placebo", np.empty((0, len(k)))))
        if n > 0:
            ax.plot(kx, mean[mask], color="grey", lw=1.3, ls="--",
                    label=f"{groups['0.01_placebo']}, n={n:,}")
        ax.axvline(0, color="grey", lw=1, ls=":")
        ax.axhline(0, color="grey", lw=0.8)
        ax.grid(True, alpha=0.25)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5))

    _draw(ax1, k, np.ones_like(k, dtype=bool))
    ax1.set_xlabel("Minutos desde o toque (k = 0)")
    ax1.set_ylabel("Retorno acumulado assinado (bps)\n(+ = continuação  /  − = reversão)")
    ax1.set_title("Caminho completo (com a aproximação)")
    ax1.legend(fontsize=8, loc="upper left", framealpha=0.9)

    post = k >= 0
    _draw(ax2, k[post], post)
    ax2.set_xlabel("Minutos desde o toque (k = 0)")
    ax2.set_ylabel("Retorno acumulado assinado (bps)")
    ax2.set_title("Zoom pós-toque (k ≥ 0) — onde H1a/H1b agiriam")

    fig.suptitle("Event-study do toque em nível: USD/BRL M1 (FBS-Demo, sessão 15:30–23:00) — "
                 "níveis redondos vs. controle de Osler (banda 0,01%)", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(os.path.join(FIG_DIR, "event_study.png"), dpi=150)
    print(f"Figura salva em {FIG_DIR}/event_study.png")
    print(f"Tabela salva em {OUT_DIR}/event_study_paths.csv")

    # resumo pos-toque (k = +15, horizonte primario)
    j = np.where(k == 15)[0][0]
    print(f"\nRetorno assinado medio em k=+15 min (bps):")
    print(f"  Controle: {cm[j]:+.2f}")
    for gname, label in groups.items():
        m, _s, n = _mean_se(round_paths.get(gname, np.empty((0, len(k)))))
        if n:
            print(f"  {label}: {m[j]:+.2f}")


if __name__ == "__main__":
    main()
