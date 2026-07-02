"""
Exporta os dados da analise para `web/data.json`, consumido pela experiencia
interativa (site em web/). Nao roda nenhum teste novo: apenas le a serie de
precos crua e os resultados ja gravados em results/ e os empacota num JSON
enxuto, apropriado pra animacao em canvas.

Saidas empacotadas:
    - series de preco (downsampled p/ ~1900 pts) + range
    - "paredes": niveis redondos nominais dentro do range, por grade
    - "toques": eventos de toque em niveis redondos, mapeados p/ o indice
      da serie downsampled (posicao das faiscas)
    - "experimento": taxa de ricochete redondo vs. sorteado (H1a), por grade
    - "ricochete": event-study medio (mean_bps +/- se) por grupo
    - "fatos": numeros de manchete (minutos, dias, contagens, premio PTAX)
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.events import filter_session, _prepare_series, detect_touch_events
from src.round_levels import all_round_levels

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "raw" / "usdbrl_m1_fbs_demo.csv"
CONFIRM_PATH = ROOT / "results" / "confirmatory_results.csv"
EVENT_PATH = ROOT / "results" / "event_study_paths.csv"
SANITY_PATH = ROOT / "results" / "sanity_ptax.csv"
OUT_PATH = ROOT / "web" / "data.json"

TOL = 0.0001                    # banda primaria do desenho (0,01%)
TARGET_POINTS = 1900            # alvo de pontos na serie downsampled
ROUND_GRIDS = ["1.00", "0.50", "0.10", "0.05"]   # grades "fortes" (nao placebo)


def build_series(s: pd.DataFrame):
    """Downsample da serie de close por stride uniforme (eixo = indice sequencial)."""
    close = s["close"].to_numpy()
    n = len(close)
    stride = max(1, n // TARGET_POINTS)
    idx = np.arange(0, n, stride)
    price_ds = close[idx]
    return idx, [round(float(p), 4) for p in price_ds]


def build_touches(s: pd.DataFrame, grids: dict, full_idx: np.ndarray):
    """Detecta toques em niveis redondos e mapeia p/ posicao na serie downsampled."""
    touches = []
    counts = {}
    for gname in ROUND_GRIDS:
        levels = grids.get(gname, [])
        c = 0
        for level in levels:
            ev = detect_touch_events(s, float(level), TOL)
            if ev.empty:
                continue
            for i in ev["idx"].to_numpy():
                di = int(np.searchsorted(full_idx, int(i)))
                di = min(di, len(full_idx) - 1)
                touches.append({"i": di, "g": gname, "p": round(float(level), 4)})
                c += 1
        counts[gname] = c
    # ordena por posicao (as faiscas acendem na ordem em que a linha avanca)
    touches.sort(key=lambda t: t["i"])
    return touches, counts


def build_walls(grids: dict):
    walls = {}
    for gname, levels in grids.items():
        walls[gname] = [round(float(x), 4) for x in levels]
    return walls


def build_experiment(confirm: pd.DataFrame):
    """H1a bounce: taxa observada (redondo) vs. media nula (sorteado), grade primaria."""
    prim = confirm[(confirm["primario"] == True) & (confirm["hipotese"] == "H1a_bounce")]
    rows = []
    for _, r in prim.iterrows():
        rows.append({
            "grade": r["grade"],
            "redondo": round(float(r["estatistica_obs"]) * 100, 2),
            "sorteado": round(float(r["nula_media"]) * 100, 2),
            "n_meses": int(r["n_meses"]),
            "placebo": bool(r["placebo"]),
            "p": round(float(r["p_montecarlo"]), 4),
        })
    return rows


def build_event_study(ev: pd.DataFrame):
    out = {}
    for grupo, g in ev.groupby("grupo"):
        g = g.sort_values("k_min")
        out[grupo] = {
            "k": [int(x) for x in g["k_min"]],
            "mean": [round(float(x), 3) for x in g["mean_bps"]],
            "se": [round(float(x), 3) for x in g["se_bps"]],
            "n": int(g["n_eventos"].iloc[0]),
        }
    return out


def main():
    df = pd.read_csv(RAW_PATH)
    n_raw = len(df)
    df = filter_session(df)
    s = _prepare_series(df)
    n_session = len(s)

    close = s["close"].to_numpy()
    price_min, price_max = float(close.min()), float(close.max())
    t = s["time"]
    date_start = str(t.iloc[0].date())
    date_end = str(t.iloc[-1].date())
    n_days = int(s["time"].dt.date.nunique())

    grids = all_round_levels(price_min, price_max)
    full_idx, price_ds = build_series(s)
    touches, touch_counts = build_touches(s, grids, full_idx)
    walls = build_walls(grids)
    confirm = pd.read_csv(CONFIRM_PATH)
    experiment = build_experiment(confirm)
    ev = pd.read_csv(EVENT_PATH)
    event_study = build_event_study(ev)

    # premio medio do feed demo vs PTAX oficial (sanity)
    premio_bps = None
    if SANITY_PATH.exists():
        san = pd.read_csv(SANITY_PATH)
        premio_bps = round(float(san["diff_bps_mid"].mean()), 1)

    # manchete: taxa de ricochete "geral" (grade 0,05, mais eventos entre as primarias)
    head = next((e for e in experiment if e["grade"] == "0.05" and not e["placebo"]), experiment[0])

    payload = {
        "meta": {
            "date_start": date_start,
            "date_end": date_end,
            "n_minutes": n_session,
            "n_minutes_raw": n_raw,
            "n_days": n_days,
            "price_min": round(price_min, 4),
            "price_max": round(price_max, 4),
            "tol_pct": TOL * 100,
            "window_min": 15,
            "premio_bps": premio_bps,
        },
        "series": price_ds,
        "walls": walls,
        "touches": touches,
        "touch_counts": touch_counts,
        "n_touches_round": int(sum(touch_counts.values())),
        "experiment": experiment,
        "headline": head,
        "event_study": event_study,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    print(f"wrote {OUT_PATH}")
    print(f"  series points : {len(price_ds)}  (session minutes {n_session})")
    print(f"  round touches : {sum(touch_counts.values())}  {touch_counts}")
    print(f"  walls         : { {k: len(v) for k, v in walls.items()} }")
    print(f"  headline      : redondo {head['redondo']}% vs sorteado {head['sorteado']}%")
    print(f"  premio demo   : {premio_bps} bps")


if __name__ == "__main__":
    main()
