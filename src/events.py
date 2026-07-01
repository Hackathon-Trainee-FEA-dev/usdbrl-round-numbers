"""
Motor de deteccao de eventos e classificacao bounce/continuacao.

Replica do desenho unificado de Osler (2000) (ver README.md / memoria do
projeto): um "evento" ocorre quando o preco toca um nivel (redondo ou de
controle) dentro de uma banda de tolerancia percentual; classifica-se o
resultado observando o lado do nivel em que o preco esta ao final de uma
janela fixa apos o toque.

    - bounce / reversao      (evidencia H1a): preco volta pro lado de onde veio.
    - continuacao / aceleracao (evidencia H1b): preco permanece/segue pro
      outro lado; magnitude = distancia percorrida alem do nivel.

Parametros primarios do desenho pre-registrado: banda = 0,01% de distancia
do nivel, janela = 15 min (robustez: banda 0,00%/0,02%, janela 30 min).

Reaproveitado tanto pros niveis redondos reais (fixos, validos no dataset
inteiro -- ver round_levels.py) quanto pros niveis de controle de Osler
(validos so no dia em que foram gerados -- ver control_levels.py).

## Decisoes de implementacao (nao estao no paper, documentadas aqui pra
## transparencia -- nenhuma delas altera os parametros ja travados):

- "Toque" = a faixa [low, high] da barra intersecta a banda [nivel*(1-tol),
  nivel*(1+tol)] -- checagem via high/low, nao so pelo close, pra nao perder
  toques intrabarra.
- Um evento e a *primeira* barra de cada sequencia continua dentro da banda
  (evita contar a mesma permanencia no nivel varias vezes).
- Lado de aproximacao = lado do close da barra imediatamente anterior ao
  toque (acima/abaixo do nivel).
- Eventos sem `window_min` barras completas ate o fim da serie sao
  descartados (nao da pra observar o resultado).
- Eventos cuja janela de classificacao atravessa um gap de negociacao >
  `max_gap_min` (ex. fechamento de fim de semana) sao descartados -- mesma
  logica do bug de gap de fim de semana encontrado na fase piloto.
"""
import numpy as np
import pandas as pd


def _prepare_series(df: pd.DataFrame, time_col: str = "time") -> pd.DataFrame:
    d = df[[time_col, "open", "high", "low", "close"]].copy()
    d[time_col] = pd.to_datetime(d[time_col], utc=True)
    d = d.sort_values(time_col).reset_index(drop=True)
    d["gap_min"] = d[time_col].diff().dt.total_seconds().div(60)
    return d


# ---------------------------------------------------------------------------
# Niveis redondos: um nivel fixo, valido no dataset inteiro.
# ---------------------------------------------------------------------------

def detect_touch_events(series: pd.DataFrame, level: float, tolerance_pct: float) -> pd.DataFrame:
    """
    Detecta eventos discretos de "toque" num unico nivel, na serie inteira.

    Retorna um DataFrame com uma linha por evento: indice global do bar de
    toque (`idx`), horario (`time`) e lado de aproximacao (`approach_side`,
    'above'/'below', baseado no close da barra imediatamente anterior).
    """
    band_lo = level * (1 - tolerance_pct)
    band_hi = level * (1 + tolerance_pct)

    low = series["low"].to_numpy()
    high = series["high"].to_numpy()
    close = series["close"].to_numpy()

    in_band = (low <= band_hi) & (high >= band_lo)
    if not in_band.any():
        return pd.DataFrame(columns=["idx", "time", "approach_side"])

    shifted = np.concatenate([[False], in_band[:-1]])
    event_start = in_band & (~shifted)
    event_idx = np.where(event_start)[0]
    event_idx = event_idx[event_idx > 0]  # descarta toque na 1a barra (sem "antes")
    if event_idx.size == 0:
        return pd.DataFrame(columns=["idx", "time", "approach_side"])

    prev_close = close[event_idx - 1]
    approach_side = np.where(prev_close < level, "below", "above")

    return pd.DataFrame({
        "idx": event_idx,
        "time": series["time"].to_numpy()[event_idx],
        "approach_side": approach_side,
    })


def classify_events(series: pd.DataFrame, events: pd.DataFrame, level: float, window_min: int, max_gap_min: int) -> pd.DataFrame:
    """
    Pra cada evento de toque, olha `window_min` barras a frente e classifica
    como bounce (voltou pro lado original) ou continuacao (seguiu/passou pro
    outro lado). Descarta eventos sem barras suficientes ate o fim da serie
    ou com gap de negociacao > max_gap_min dentro da janela.
    """
    if events.empty:
        return pd.DataFrame(columns=["time", "level", "approach_side", "outcome", "magnitude"])

    n = len(series)
    close = series["close"].to_numpy()
    gaps = series["gap_min"].to_numpy()

    rows = []
    for idx, time, approach_side in events[["idx", "time", "approach_side"]].itertuples(index=False):
        i = int(idx)
        j = i + window_min
        if j >= n:
            continue
        window_gaps = gaps[i + 1: j + 1]
        if (window_gaps > max_gap_min).any():
            continue

        end_close = close[j]
        side_end = "below" if end_close < level else "above"
        outcome = "bounce" if side_end == approach_side else "continuation"
        magnitude = abs(end_close - level)

        rows.append({
            "time": time,
            "level": level,
            "approach_side": approach_side,
            "outcome": outcome,
            "magnitude": magnitude,
        })

    return pd.DataFrame(rows)


def run_round_level_events(
    df: pd.DataFrame,
    grids: dict,
    tolerance_pct: float = 0.0001,
    window_min: int = 15,
    max_gap_min: int = 5,
    time_col: str = "time",
) -> pd.DataFrame:
    """
    Roda deteccao + classificacao de eventos pra todas as grades de niveis
    redondos (ver round_levels.GRIDS / round_levels.all_round_levels), usando
    o dataset inteiro (niveis sao fixos/nominais, validos em qualquer data).
    """
    series = _prepare_series(df, time_col=time_col)

    all_results = []
    for grid_name, levels in grids.items():
        for level in levels:
            events = detect_touch_events(series, level, tolerance_pct)
            if events.empty:
                continue
            classified = classify_events(series, events, level, window_min, max_gap_min)
            if classified.empty:
                continue
            classified["grid"] = grid_name
            classified["level_type"] = "round"
            all_results.append(classified)

    if not all_results:
        return pd.DataFrame()
    return pd.concat(all_results, ignore_index=True)


# ---------------------------------------------------------------------------
# Niveis de controle: um nivel por dia, valido so naquele dia (o toque tem
# que acontecer no dia em que o nivel "nasceu" -- a janela de classificacao
# depois do toque pode seguir pra frente na serie normalmente).
# ---------------------------------------------------------------------------

def run_control_level_events(
    df: pd.DataFrame,
    control_levels: pd.DataFrame,
    tolerance_pct: float = 0.0001,
    window_min: int = 15,
    max_gap_min: int = 5,
    time_col: str = "time",
) -> pd.DataFrame:
    """
    Roda deteccao + classificacao de eventos pros niveis de controle de
    Osler (ver control_levels.generate_control_levels). Vetorizado por dia:
    pra cada dia, testa todos os niveis (de todos os conjuntos) que nascem
    naquele dia de uma vez via broadcasting numpy, em vez de escanear a
    serie inteira nivel a nivel (inviavel com milhares de conjuntos).
    """
    series = _prepare_series(df, time_col=time_col)
    series["date"] = series[time_col].dt.date

    low = series["low"].to_numpy()
    high = series["high"].to_numpy()
    close = series["close"].to_numpy()
    gaps = series["gap_min"].to_numpy()
    times = series["time"].to_numpy()
    n = len(series)

    results = []
    day_groups = series.groupby("date").indices  # date -> array de posicoes globais

    for date, day_idx in day_groups.items():
        day_idx = np.asarray(day_idx)
        day_levels = control_levels[control_levels["date"] == date]
        if day_levels.empty or day_idx.size == 0:
            continue

        levels_arr = day_levels["level"].to_numpy()
        set_ids = day_levels["set_id"].to_numpy()
        level_types = day_levels["level_type"].to_numpy()

        d_low = low[day_idx]
        d_high = high[day_idx]

        band_lo = levels_arr[:, None] * (1 - tolerance_pct)
        band_hi = levels_arr[:, None] * (1 + tolerance_pct)

        in_band = (d_low[None, :] <= band_hi) & (d_high[None, :] >= band_lo)  # (L, D)
        prev_col = np.zeros((in_band.shape[0], 1), dtype=bool)
        shifted = np.concatenate([prev_col, in_band[:, :-1]], axis=1)
        event_start = in_band & (~shifted)

        for li in range(levels_arr.shape[0]):
            local_pos = np.where(event_start[li])[0]
            if local_pos.size == 0:
                continue
            level = levels_arr[li]

            for lp in local_pos:
                gi = day_idx[lp]
                if gi == 0:
                    continue
                approach_side = "below" if close[gi - 1] < level else "above"

                j = gi + window_min
                if j >= n:
                    continue
                if (gaps[gi + 1: j + 1] > max_gap_min).any():
                    continue

                end_close = close[j]
                side_end = "below" if end_close < level else "above"
                outcome = "bounce" if side_end == approach_side else "continuation"
                magnitude = abs(end_close - level)

                results.append({
                    "time": times[gi],
                    "level": level,
                    "set_id": set_ids[li],
                    "level_type": f"control_{level_types[li]}",
                    "approach_side": approach_side,
                    "outcome": outcome,
                    "magnitude": magnitude,
                })

    return pd.DataFrame(results)
