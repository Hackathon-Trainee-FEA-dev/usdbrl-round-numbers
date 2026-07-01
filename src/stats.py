"""
Teste confirmatorio: p-valor empirico (Monte Carlo) comparando o
comportamento dos niveis redondos reais contra a distribuicao nula gerada
pelos niveis de controle aleatorios de Osler (2000).

## Desenho do teste (pre-registrado -- ver README.md / memoria do projeto)

A ideia e exatamente a de Osler (2000): os N conjuntos de niveis de controle
artificiais formam uma distribuicao nula empirica de "como um nivel arbitrario
se comporta". Compara-se a estatistica observada nos niveis redondos reais
contra essa distribuicao.

- H1a (reversao/bounce): a taxa de bounce nos niveis redondos e MAIOR do que a
  taxa de bounce em niveis arbitrarios.
      estatistica = bounce_rate = n_bounce / (n_bounce + n_continuation)
      H0: nivel redondo nao difere de um nivel arbitrario.
      teste unilateral (greater), pois a hipotese de Osler e direcional.

- H1b (aceleracao): a magnitude media dos eventos de *continuacao* nos niveis
  redondos e MAIOR do que nos de controle.
      estatistica = media de |close_fim_janela - nivel| entre continuacoes.
      teste unilateral (greater).

## p-valor empirico

Para cada conjunto de controle k (k = 1..N) calcula-se a mesma estatistica,
formando a distribuicao nula {T_k}. O p-valor empirico unilateral usa a
formula (r + 1) / (N + 1) de North, Curtis & Sham (2002) -- o "+1" evita
p = 0 e corresponde a incluir a propria amostra observada na contagem:

    p_greater = (#{ T_k >= T_obs } + 1) / (N + 1)

## Grades e falsificacao

Testa-se cada grade real (R$1,00 / R$0,50 / R$0,10 / R$0,05) contra a mesma
distribuicao nula de controle. A grade R$0,01 e um PLACEBO de falsificacao:
espera-se que NAO seja significativa; se der significativa, e sinal de que o
"efeito" pode ser artefato e nao ancoragem psicologica real. Os p-valores sao
reportados por grade; correcao para multiplos testes (Bonferroni sobre as 4
grades reais) e reportada em paralelo, mas as grades sao aninhadas/correlatas,
entao Bonferroni e conservador.

## Referencias

- Osler, C. (2000). "Support for Resistance: Technical Analysis and Intraday
  Exchange Rates." FRBNY Economic Policy Review, 6(2).
- North, B. V., Curtis, D., & Sham, P. C. (2002). "A Note on the Calculation of
  Empirical P Values from Monte Carlo Procedures." American Journal of Human
  Genetics, 71(2), 439-441.
- Davison, A. C., & Hinkley, D. V. (1997). "Bootstrap Methods and Their
  Application." Cambridge University Press.
"""
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Estatisticas
# ---------------------------------------------------------------------------

def bounce_rate(events: pd.DataFrame) -> float:
    """Fracao de eventos classificados como bounce. NaN se nao ha eventos."""
    if len(events) == 0:
        return np.nan
    return float((events["outcome"] == "bounce").mean())


def mean_continuation_magnitude(events: pd.DataFrame) -> float:
    """Magnitude media entre os eventos de continuacao. NaN se nao ha continuacoes."""
    cont = events.loc[events["outcome"] == "continuation", "magnitude"]
    if len(cont) == 0:
        return np.nan
    return float(cont.mean())


# ---------------------------------------------------------------------------
# p-valor empirico
# ---------------------------------------------------------------------------

def empirical_pvalue(observed: float, null_samples: np.ndarray, alternative: str = "greater") -> float:
    """
    p-valor empirico via formula (r + 1) / (N + 1) de North et al. (2002).

    alternative:
        'greater' -> H1: observado > nulo   (r = #{null >= observed})
        'less'    -> H1: observado < nulo   (r = #{null <= observed})
        'two-sided' -> 2 * min(greater, less), truncado em 1.0
    """
    null = np.asarray(null_samples, dtype=float)
    null = null[~np.isnan(null)]
    n = null.size
    if n == 0 or np.isnan(observed):
        return np.nan

    if alternative == "greater":
        r = int(np.sum(null >= observed))
        return (r + 1) / (n + 1)
    if alternative == "less":
        r = int(np.sum(null <= observed))
        return (r + 1) / (n + 1)
    if alternative == "two-sided":
        p_greater = (int(np.sum(null >= observed)) + 1) / (n + 1)
        p_less = (int(np.sum(null <= observed)) + 1) / (n + 1)
        return min(1.0, 2 * min(p_greater, p_less))
    raise ValueError(f"alternative invalido: {alternative}")


def control_null_distribution(control_events: pd.DataFrame, statistic_fn) -> np.ndarray:
    """
    Calcula `statistic_fn` para cada conjunto de controle (agrupando por
    set_id), retornando o array da distribuicao nula empirica.
    """
    if len(control_events) == 0:
        return np.array([])
    return control_events.groupby("set_id").apply(statistic_fn).to_numpy(dtype=float)


# ---------------------------------------------------------------------------
# Orquestracao do teste confirmatorio
# ---------------------------------------------------------------------------

def run_confirmatory_test(round_events: pd.DataFrame, control_events: pd.DataFrame) -> pd.DataFrame:
    """
    Roda o teste confirmatorio completo: para cada grade de nivel redondo,
    compara a taxa de bounce (H1a) e a magnitude media de continuacao (H1b)
    contra a distribuicao nula dos conjuntos de controle.

    Retorna um DataFrame com uma linha por (grade x hipotese), contendo a
    estatistica observada, a media/desvio da nula, o p-valor empirico
    unilateral e o p-valor Bonferroni-corrigido (sobre as 4 grades reais).
    """
    # distribuicoes nulas (uma por conjunto de controle), calculadas uma vez
    null_bounce = control_null_distribution(control_events, bounce_rate)
    null_magnitude = control_null_distribution(control_events, mean_continuation_magnitude)

    real_grids = ["1.00", "0.50", "0.10", "0.05"]
    n_real = len(real_grids)

    rows = []
    for grid_name, grid_events in round_events.groupby("grid"):
        is_placebo = grid_name.endswith("placebo")

        # H1a -- bounce
        obs_b = bounce_rate(grid_events)
        p_b = empirical_pvalue(obs_b, null_bounce, alternative="greater")
        rows.append({
            "grade": grid_name,
            "hipotese": "H1a_bounce",
            "placebo": is_placebo,
            "n_eventos": len(grid_events),
            "estatistica_obs": obs_b,
            "nula_media": float(np.nanmean(null_bounce)),
            "nula_desvio": float(np.nanstd(null_bounce)),
            "p_empirico": p_b,
            "p_bonferroni": min(1.0, p_b * n_real) if (not is_placebo and not np.isnan(p_b)) else np.nan,
        })

        # H1b -- magnitude de continuacao
        obs_m = mean_continuation_magnitude(grid_events)
        p_m = empirical_pvalue(obs_m, null_magnitude, alternative="greater")
        n_cont = int((grid_events["outcome"] == "continuation").sum())
        rows.append({
            "grade": grid_name,
            "hipotese": "H1b_magnitude",
            "placebo": is_placebo,
            "n_eventos": n_cont,
            "estatistica_obs": obs_m,
            "nula_media": float(np.nanmean(null_magnitude)),
            "nula_desvio": float(np.nanstd(null_magnitude)),
            "p_empirico": p_m,
            "p_bonferroni": min(1.0, p_m * n_real) if (not is_placebo and not np.isnan(p_m)) else np.nan,
        })

    result = pd.DataFrame(rows)
    grid_order = {"1.00": 0, "0.50": 1, "0.10": 2, "0.05": 3, "0.01_placebo": 4}
    result["_ord"] = result["grade"].map(grid_order)
    result = result.sort_values(["_ord", "hipotese"]).drop(columns="_ord").reset_index(drop=True)
    return result
