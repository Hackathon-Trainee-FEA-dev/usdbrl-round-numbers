"""
Sanity check da fonte: preco intradiario MT5 (FBS-Demo) vs. PTAX oficial do BCB.

Objetivo: confirmar que o feed de corretora demo usado na analise nao tem erro
de escala/unidade nem deriva sistematica contra a taxa de referencia oficial do
Banco Central -- ou seja, que e um proxy legitimo do USD/BRL a vista.

Desenho (match por instante):
    - PTAX: cotacao de VENDA de FECHAMENTO (boletim de fechamento), via API
      Olinda do BCB (`CotacaoDolarPeriodo`). O carimbo `dataHoraCotacao` vem em
      horario de Brasilia (UTC-3 fixo -- o Brasil nao adota mais horario de
      verao desde 2019), convertido para UTC.
    - MT5: o `close` da barra M1 MAIS PROXIMA do instante da PTAX (merge_asof
      nearest, tolerancia de 5 min). Comparacao instante-a-instante evita o vies
      de drift intradiario que uma media diaria introduziria.
    - Metrica: diferenca relativa em basis points, diff_bps = (MT5 - PTAX)/PTAX * 1e4.

O feed demo e uma cotacao de corretora (com spread) e a PTAX e uma media oficial
de 4 janelas de consulta; portanto um offset PEQUENO e ESTAVEL de poucos bps e
esperado e aceitavel. Gap grande, com deriva, ou correlacao baixa seria red flag.

Snapshot da PTAX e versionado em data/raw/ para reprodutibilidade offline
(mesma filosofia do snapshot MT5). Se o arquivo existir, e reutilizado; senao,
e baixado da API e salvo.

Saidas:
    data/raw/ptax_bcb_fechamento.csv   snapshot da PTAX (versionado)
    results/sanity_ptax.csv            tabela dia-a-dia (PTAX, MT5, diff)
    figures/sanity_ptax.png            figura (series sobrepostas + diferenca)

Uso: python -m src.sanity_ptax   (a partir da raiz do repositorio)
"""
import os

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RAW_PATH = "data/raw/usdbrl_m1_fbs_demo.csv"
PTAX_SNAPSHOT = "data/raw/ptax_bcb_fechamento.csv"
FIG_DIR = "figures"
OUT_DIR = "results"

MATCH_TOL_MIN = 5          # tolerancia do casamento MT5<->PTAX (minutos)
BR_TZ = "America/Sao_Paulo"

OLINDA = ("https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
          "CotacaoDolarPeriodo(dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)")


# ---------------------------------------------------------------------------
# PTAX (BCB) -- fetch + cache
# ---------------------------------------------------------------------------

def fetch_ptax(date_ini, date_fim) -> pd.DataFrame:
    """Baixa a PTAX de fechamento da API Olinda para [date_ini, date_fim]."""
    import requests
    params = {
        "@dataInicial": f"'{date_ini.strftime('%m-%d-%Y')}'",
        "@dataFinalCotacao": f"'{date_fim.strftime('%m-%d-%Y')}'",
        "$format": "json",
        "$select": "cotacaoCompra,cotacaoVenda,dataHoraCotacao",
    }
    r = requests.get(OLINDA, params=params, timeout=60)
    r.raise_for_status()
    data = r.json()["value"]
    ptax = pd.DataFrame(data)
    ptax = ptax.rename(columns={"cotacaoCompra": "ptax_compra",
                                "cotacaoVenda": "ptax_venda",
                                "dataHoraCotacao": "dt_brt"})
    return ptax


def load_ptax(date_ini, date_fim) -> pd.DataFrame:
    """Usa o snapshot versionado se existir; senao baixa e salva."""
    if os.path.exists(PTAX_SNAPSHOT):
        print(f"PTAX: usando snapshot {PTAX_SNAPSHOT}")
        ptax = pd.read_csv(PTAX_SNAPSHOT)
    else:
        print("PTAX: baixando da API Olinda do BCB...")
        ptax = fetch_ptax(date_ini, date_fim)
        ptax.to_csv(PTAX_SNAPSHOT, index=False)
        print(f"PTAX: snapshot salvo em {PTAX_SNAPSHOT} ({len(ptax)} dias)")

    # carimbo em horario de Brasilia -> UTC
    ts = pd.to_datetime(ptax["dt_brt"])
    ptax["time"] = ts.dt.tz_localize(BR_TZ).dt.tz_convert("UTC")
    ptax["ptax_mid"] = (ptax["ptax_compra"] + ptax["ptax_venda"]) / 2.0
    return ptax.sort_values("time").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Match por instante
# ---------------------------------------------------------------------------

def match_mt5(mt5: pd.DataFrame, ptax: pd.DataFrame, tol_min: int) -> pd.DataFrame:
    """Casa cada PTAX com a barra M1 mais proxima (nearest, dentro de tol_min)."""
    left = ptax[["time", "ptax_compra", "ptax_venda", "ptax_mid"]].sort_values("time")
    right = mt5[["time", "close"]].rename(columns={"close": "mt5_close"}).sort_values("time")
    merged = pd.merge_asof(left, right, on="time", direction="nearest",
                           tolerance=pd.Timedelta(minutes=tol_min))
    merged = merged.dropna(subset=["mt5_close"]).reset_index(drop=True)
    merged["date"] = merged["time"].dt.tz_convert("UTC").dt.date
    merged["diff_bps_venda"] = (merged["mt5_close"] - merged["ptax_venda"]) / merged["ptax_venda"] * 1e4
    merged["diff_bps_mid"] = (merged["mt5_close"] - merged["ptax_mid"]) / merged["ptax_mid"] * 1e4
    return merged


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(FIG_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    mt5 = pd.read_csv(RAW_PATH)
    mt5["time"] = pd.to_datetime(mt5["time"], utc=True)
    d0, d1 = mt5["time"].min(), mt5["time"].max()
    print(f"MT5: {len(mt5):,} barras M1, {d0.date()} a {d1.date()}")

    ptax = load_ptax(d0.date(), d1.date())
    merged = match_mt5(mt5, ptax, MATCH_TOL_MIN)
    print(f"Dias casados (PTAX x MT5, tol {MATCH_TOL_MIN} min): {len(merged)} de {len(ptax)} boletins")

    merged.drop(columns=["time"]).to_csv(os.path.join(OUT_DIR, "sanity_ptax.csv"), index=False)

    d = merged["diff_bps_venda"]
    dm = merged["diff_bps_mid"]
    corr = np.corrcoef(merged["mt5_close"], merged["ptax_venda"])[0, 1]
    print("\n=== Diferenca MT5 - PTAX (bps) ===")
    print(f"  vs VENDA:  media {d.mean():+.2f}  mediana {d.median():+.2f}  "
          f"desvio {d.std():.2f}  |MAE| {d.abs().mean():.2f}  [{d.min():+.1f}, {d.max():+.1f}]")
    print(f"  vs MID:    media {dm.mean():+.2f}  mediana {dm.median():+.2f}  "
          f"desvio {dm.std():.2f}  |MAE| {dm.abs().mean():.2f}")
    print(f"  correlacao dos niveis (MT5 x PTAX venda): {corr:.6f}")

    # ---- figura: series sobrepostas + diferenca ----
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True,
                                   gridspec_kw={"height_ratios": [2, 1]})
    x = pd.to_datetime(merged["date"])
    ax1.plot(x, merged["ptax_venda"], color="#1f77b4", lw=1.4, label="PTAX venda (BCB, fechamento)")
    ax1.plot(x, merged["mt5_close"], color="#d62728", lw=1.0, alpha=0.8,
             label="MT5 close (barra mais proxima)")
    ax1.set_ylabel("USD/BRL")
    ax1.set_title("Sanity check da fonte: MT5 (FBS-Demo) vs. PTAX oficial do BCB — match por instante")
    ax1.legend(fontsize=9, loc="upper right")
    ax1.grid(True, alpha=0.25)

    ax2.axhline(0, color="grey", lw=0.8)
    ax2.axhline(d.mean(), color="#d62728", lw=1.0, ls="--",
                label=f"media {d.mean():+.1f} bps")
    ax2.plot(x, d, color="#555555", lw=0.9)
    ax2.fill_between(x, d, d.mean(), color="#999999", alpha=0.20)
    ax2.set_ylabel("MT5 − PTAX (bps)")
    ax2.set_xlabel("Data")
    ax2.legend(fontsize=8, loc="upper right")
    ax2.grid(True, alpha=0.25)

    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "sanity_ptax.png"), dpi=150)
    print(f"\nFigura salva em {FIG_DIR}/sanity_ptax.png")
    print(f"Tabela salva em {OUT_DIR}/sanity_ptax.csv")


if __name__ == "__main__":
    main()
