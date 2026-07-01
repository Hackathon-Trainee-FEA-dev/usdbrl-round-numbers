"""
Teste confirmatorio: niveis redondos reais vs. niveis de controle aleatorios
de Osler (2000).

## Teste PRIMARIO -- sinal binomial mensal (LITERAL Osler 2000)

Osler nao usa percentil Monte Carlo. O procedimento dela (p.61-62 do paper):

  1. Para cada mes, calcula a bounce frequency dos niveis reais -> BP_mes.
  2. Para cada mes, calcula a bounce frequency de cada um dos N conjuntos de
     controle e tira a MEDIA sobre os conjuntos -> BA_mes.
  3. Conta em quantos dos N_meses vale BP_mes > BA_mes.
  4. Teste de sinal binomial: essa contagem vs. Binomial(N_meses, 0,5). A
     "marginal significance" e a cauda da binomial.

  bounce frequency = bounces / total de hits.

Aplicado tambem a H1b (magnitude media de continuacao), com a mesma logica de
sinal mensal -- mas H1b NAO e de Osler (2000) (ela nao testa aceleracao; ver
memoria/README), entra como EXTENSAO ancorada em Curcio et al. (1997) e Brock,
Lakonishok & LeBaron (1992).

## Teste COMPLEMENTAR -- p-valor empirico Monte Carlo (r+1)/(N+1)

Como o sinal binomial e pouco potente com poucos meses (~12 na nossa amostra
-> precisa 10/12 p/ p<0,05), reportamos em paralelo o p-valor empirico de
Monte Carlo (North, Curtis & Sham 2002): a estatistica agregada (pooled sobre
todos os meses) dos niveis redondos vs. a distribuicao dessa mesma estatistica
sobre os N conjuntos de controle. Mais potente, complementa o teste literal.

## Grades e falsificacao

Cada grade real (R$1,00 / 0,50 / 0,10 / 0,05) e testada; R$0,01 e PLACEBO (nao
deve dar significativo). Bonferroni sobre as 4 grades reais reportado em
paralelo (conservador -- grades aninhadas/correlatas).

## Referencias
- Osler, C. (2000). FRBNY Economic Policy Review, 6(2).
- Curcio, R., Goodhart, C., Guillaume, D., Payne, R. (1997). "Do technical
  trading rules generate profits?" LSE Financial Markets Group.
- Brock, W., Lakonishok, J., LeBaron, B. (1992). J. Finance 47(5).
- North, B. V., Curtis, D., Sham, P. C. (2002). Am. J. Human Genetics 71(2).
"""
from math import comb

import numpy as np
import pandas as pd

REAL_GRIDS = ["1.00", "0.50", "0.10", "0.05"]
GRID_ORDER = {"1.00": 0, "0.50": 1, "0.10": 2, "0.05": 3, "0.01_placebo": 4}


# ---------------------------------------------------------------------------
# Testes de base
# ---------------------------------------------------------------------------

def binomial_sign_pvalue(successes: int, n: int) -> float:
    """
    Cauda superior de Binomial(n, 0,5): P(X >= successes). Teste de sinal
    unilateral (a hipotese de Osler e direcional: BP > BA mais vezes que o
    acaso). NaN se n == 0.
    """
    if n == 0:
        return np.nan
    tail = sum(comb(n, k) for k in range(successes, n + 1))
    return tail / (2 ** n)


def empirical_pvalue(observed: float, null_samples: np.ndarray) -> float:
    """p-valor empirico unilateral (greater) (r+1)/(N+1), North et al. (2002)."""
    null = np.asarray(null_samples, dtype=float)
    null = null[~np.isnan(null)]
    nn = null.size
    if nn == 0 or np.isnan(observed):
        return np.nan
    r = int(np.sum(null >= observed))
    return (r + 1) / (nn + 1)


# ---------------------------------------------------------------------------
# Estatisticas mensais dos niveis redondos
# ---------------------------------------------------------------------------

def _round_monthly_bounce(grid_events: pd.DataFrame, months: list) -> np.ndarray:
    """BP_mes (bounce freq) por mes para uma grade. NaN em meses sem hits."""
    out = np.full(len(months), np.nan)
    idx = {m: i for i, m in enumerate(months)}
    for m, g in grid_events.groupby("month"):
        if m in idx and len(g) > 0:
            out[idx[m]] = float((g["outcome"] == "bounce").mean())
    return out


def _round_monthly_magnitude(grid_events: pd.DataFrame, months: list) -> np.ndarray:
    """MP_mes (magnitude media de continuacao) por mes. NaN em meses sem continuacoes."""
    out = np.full(len(months), np.nan)
    idx = {m: i for i, m in enumerate(months)}
    cont = grid_events[grid_events["outcome"] == "continuation"]
    for m, g in cont.groupby("month"):
        if m in idx and len(g) > 0:
            out[idx[m]] = float(g["magnitude"].mean())
    return out


# ---------------------------------------------------------------------------
# Estatisticas mensais/pooled dos controles
# ---------------------------------------------------------------------------

def _control_monthly_bounce_mean(ctrl: dict) -> np.ndarray:
    """BA_mes: media, sobre conjuntos, da bounce freq de cada conjunto no mes."""
    hits, bounces = ctrl["hits"], ctrl["bounces"]
    with np.errstate(invalid="ignore", divide="ignore"):
        per_set = np.where(hits > 0, bounces / hits, np.nan)
    return np.nanmean(per_set, axis=0)   # (n_months,)


def _control_monthly_magnitude_mean(ctrl: dict) -> np.ndarray:
    """MA_mes: media, sobre conjuntos, da magnitude media de continuacao no mes."""
    cc, ms = ctrl["cont_count"], ctrl["mag_sum"]
    with np.errstate(invalid="ignore", divide="ignore"):
        per_set = np.where(cc > 0, ms / cc, np.nan)
    return np.nanmean(per_set, axis=0)


def _control_pooled_bounce(ctrl: dict) -> np.ndarray:
    """Distribuicao nula (pooled): bounce freq de cada conjunto sobre todos os meses."""
    tot_h = ctrl["hits"].sum(axis=1)
    tot_b = ctrl["bounces"].sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(tot_h > 0, tot_b / tot_h, np.nan)


def _control_pooled_magnitude(ctrl: dict) -> np.ndarray:
    """Distribuicao nula (pooled): magnitude media de continuacao por conjunto."""
    tot_c = ctrl["cont_count"].sum(axis=1)
    tot_m = ctrl["mag_sum"].sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(tot_c > 0, tot_m / tot_c, np.nan)


# ---------------------------------------------------------------------------
# Orquestracao
# ---------------------------------------------------------------------------

def _sign_test(bp: np.ndarray, ba: np.ndarray):
    """Conta meses com BP>BA (ambos definidos) e roda o teste de sinal."""
    comparable = ~np.isnan(bp) & ~np.isnan(ba)
    n = int(comparable.sum())
    successes = int(np.sum(bp[comparable] > ba[comparable]))
    return successes, n, binomial_sign_pvalue(successes, n)


def run_confirmatory_test(round_events: pd.DataFrame, ctrl: dict) -> pd.DataFrame:
    """
    Teste confirmatorio completo por grade x hipotese.

    round_events: eventos dos niveis redondos (colunas grid, month, outcome,
                  magnitude).
    ctrl:         saida de events.run_control_monthly_stats (matrizes por
                  conjunto x mes).

    Colunas de saida: grade, hipotese, placebo, n_meses, sucessos_BP>BA,
    p_binomial (LITERAL), estatistica_obs (pooled), nula_media,
    p_montecarlo (complementar), p_binom_bonferroni.
    """
    months = ctrl["months"]

    ba_bounce = _control_monthly_bounce_mean(ctrl)
    ba_mag = _control_monthly_magnitude_mean(ctrl)
    null_bounce_pooled = _control_pooled_bounce(ctrl)
    null_mag_pooled = _control_pooled_magnitude(ctrl)
    n_real = len(REAL_GRIDS)

    rows = []
    for grid_name, grid_events in round_events.groupby("grid"):
        is_placebo = grid_name.endswith("placebo")

        # ---- H1a: bounce (LITERAL Osler) ----
        bp = _round_monthly_bounce(grid_events, months)
        s, nmo, p_bin = _sign_test(bp, ba_bounce)
        obs_pooled = float((grid_events["outcome"] == "bounce").mean()) if len(grid_events) else np.nan
        p_mc = empirical_pvalue(obs_pooled, null_bounce_pooled)
        rows.append({
            "grade": grid_name, "hipotese": "H1a_bounce", "placebo": is_placebo,
            "n_meses": nmo, "sucessos_BPmaiorBA": s, "p_binomial": p_bin,
            "estatistica_obs": obs_pooled, "nula_media": float(np.nanmean(null_bounce_pooled)),
            "p_montecarlo": p_mc,
            "p_binom_bonferroni": min(1.0, p_bin * n_real) if (not is_placebo and not np.isnan(p_bin)) else np.nan,
        })

        # ---- H1b: magnitude de continuacao (EXTENSAO, nao-Osler) ----
        mp = _round_monthly_magnitude(grid_events, months)
        s2, nmo2, p_bin2 = _sign_test(mp, ba_mag)
        cont = grid_events[grid_events["outcome"] == "continuation"]
        obs_mag = float(cont["magnitude"].mean()) if len(cont) else np.nan
        p_mc2 = empirical_pvalue(obs_mag, null_mag_pooled)
        rows.append({
            "grade": grid_name, "hipotese": "H1b_magnitude", "placebo": is_placebo,
            "n_meses": nmo2, "sucessos_BPmaiorBA": s2, "p_binomial": p_bin2,
            "estatistica_obs": obs_mag, "nula_media": float(np.nanmean(null_mag_pooled)),
            "p_montecarlo": p_mc2,
            "p_binom_bonferroni": min(1.0, p_bin2 * n_real) if (not is_placebo and not np.isnan(p_bin2)) else np.nan,
        })

    result = pd.DataFrame(rows)
    result["_ord"] = result["grade"].map(GRID_ORDER)
    result = result.sort_values(["_ord", "hipotese"]).drop(columns="_ord").reset_index(drop=True)
    return result
