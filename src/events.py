"""
Motor de deteccao de eventos e classificacao bounce/continuacao.

Replica do desenho de Osler (2000): um "evento" ocorre quando o preco toca um
nivel (redondo ou de controle) dentro de uma banda de tolerancia percentual;
classifica-se o resultado observando o lado do nivel em que o preco esta ao
final de uma janela fixa apos o toque.

    - bounce / reversao        (evidencia H1a): preco volta pro lado de onde veio.
    - continuacao / aceleracao (evidencia H1b): preco permanece/segue pro outro
      lado; magnitude = distancia percorrida alem do nivel.

Parametros primarios do desenho pre-registrado: banda = 0,01% de distancia do
nivel, janela = 15 min (robustez: banda 0,00%/0,02%, janela 30 min).

## Sessao de negociacao

Osler restringe a amostra a 9h-16h NY para excluir o overnight iliquido do
feed 24h da EBS. Aqui a fonte ja e um simbolo *onshore* USDBRL (FBS-Demo) que
so cota durante o pregao brasileiro: os dados existem apenas ~15:30-22:59 no
timestamp do servidor. `filter_session` uniformiza isso mantendo a janela
consistente [15:30, 23:00) e descartando o punhado de barras esparsas de
abertura antecipada -- o equivalente BR ao recorte de sessao de Osler.

## Decisoes de implementacao (documentadas p/ transparencia; nao alteram os
## parametros travados):

- "Toque" = a faixa [low, high] da barra intersecta a banda do nivel -- via
  high/low, nao so o close, pra nao perder toques intrabarra (adaptacao
  documentada: nao temos quote tick-by-tick, so OHLC M1).
- Um evento e a *primeira* barra de cada sequencia continua dentro da banda.
- Lado de aproximacao = lado do close da barra imediatamente anterior.
- Eventos sem `window_min` barras completas ate o fim da serie sao descartados.
- Eventos cuja janela atravessa um gap de negociacao > `max_gap_min` (ex.
  fechamento overnight/fim de semana) sao descartados.
"""
import numpy as np
import pandas as pd

from src import control_levels


SESSION_START = "15:30"   # timestamp do servidor FBS (ver docstring)
SESSION_END = "23:00"     # exclusivo


# ---------------------------------------------------------------------------
# Sessao
# ---------------------------------------------------------------------------

def filter_session(df: pd.DataFrame, start: str = SESSION_START, end: str = SESSION_END,
                   time_col: str = "time") -> pd.DataFrame:
    """
    Mantem apenas as barras cujo horario (do timestamp) cai em [start, end).
    Aplicar UMA vez, upstream, antes de gerar OHLC diario / niveis / eventos.
    """
    d = df.copy()
    t = pd.to_datetime(d[time_col], utc=True)
    tod = t.dt.strftime("%H:%M")
    keep = (tod >= start) & (tod < end)
    return d.loc[keep].reset_index(drop=True)


def _prepare_series(df: pd.DataFrame, time_col: str = "time") -> pd.DataFrame:
    d = df[[time_col, "open", "high", "low", "close"]].copy()
    d[time_col] = pd.to_datetime(d[time_col], utc=True)
    d = d.sort_values(time_col).reset_index(drop=True)
    d["gap_min"] = d[time_col].diff().dt.total_seconds().div(60)
    d["month"] = d[time_col].dt.tz_convert(None).dt.to_period("M")
    return d


# ---------------------------------------------------------------------------
# Niveis redondos: nivel fixo, valido na serie inteira.
# ---------------------------------------------------------------------------

def detect_touch_events(series: pd.DataFrame, level: float, tolerance_pct: float) -> pd.DataFrame:
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
    event_idx = event_idx[event_idx > 0]
    if event_idx.size == 0:
        return pd.DataFrame(columns=["idx", "time", "approach_side"])

    prev_close = close[event_idx - 1]
    approach_side = np.where(prev_close < level, "below", "above")

    return pd.DataFrame({
        "idx": event_idx,
        "time": series["time"].to_numpy()[event_idx],
        "approach_side": approach_side,
    })


def classify_events(series: pd.DataFrame, events: pd.DataFrame, level: float,
                    window_min: int, max_gap_min: int) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame(columns=["time", "month", "level", "approach_side", "outcome", "magnitude"])

    n = len(series)
    close = series["close"].to_numpy()
    gaps = series["gap_min"].to_numpy()
    months = series["month"].to_numpy()

    rows = []
    for idx, time, approach_side in events[["idx", "time", "approach_side"]].itertuples(index=False):
        i = int(idx)
        j = i + window_min
        if j >= n:
            continue
        if (gaps[i + 1: j + 1] > max_gap_min).any():
            continue

        end_close = close[j]
        side_end = "below" if end_close < level else "above"
        outcome = "bounce" if side_end == approach_side else "continuation"
        rows.append({
            "time": time,
            "month": months[i],
            "level": level,
            "approach_side": approach_side,
            "outcome": outcome,
            "magnitude": abs(end_close - level),
        })

    return pd.DataFrame(rows)


def run_round_level_events(df: pd.DataFrame, grids: dict, tolerance_pct: float = 0.0001,
                           window_min: int = 15, max_gap_min: int = 5,
                           time_col: str = "time") -> pd.DataFrame:
    """
    Deteccao + classificacao de eventos pra todas as grades de niveis redondos.
    `df` deve JA estar filtrado por sessao (ver filter_session).
    Retorna eventos com coluna `month` (para o teste de sinal mensal de Osler).
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
# Niveis de controle: 20 R + 20 S por dia, N conjuntos (literal Osler 2000).
# Gerados sob demanda por dia e reduzidos a estatisticas por (conjunto, mes),
# para nao materializar os ~45M niveis. Retorna as matrizes que o teste de
# sinal binomial mensal (stats.py) precisa.
# ---------------------------------------------------------------------------

def run_control_monthly_stats(df: pd.DataFrame, n_sets: int, seed: int,
                              tolerance_pct: float = 0.0001, window_min: int = 15,
                              levels_per_side: int = control_levels.LEVELS_PER_SIDE,
                              max_gap_min: int = 5, time_col: str = "time") -> dict:
    """
    Para cada dia, sorteia 2*levels_per_side niveis de controle por conjunto,
    detecta toques (vetorizado sobre todos os niveis do dia) e classifica.
    Acumula por (conjunto, mes): hits, bounces, n_continuacoes e soma de
    magnitudes.

    `df` deve JA estar filtrado por sessao.

    Retorna dict com:
        months      : lista ordenada de Periods (mes)
        hits        : array (n_sets, n_months)
        bounces     : array (n_sets, n_months)
        cont_count  : array (n_sets, n_months)
        mag_sum     : array (n_sets, n_months)
    """
    series = _prepare_series(df, time_col=time_col)
    daily = control_levels.daily_levels_table(df, time_col=time_col)

    close = series["close"].to_numpy()
    high = series["high"].to_numpy()
    low = series["low"].to_numpy()
    gaps = series["gap_min"].to_numpy()
    n = len(series)

    series_dates = series[time_col].dt.date
    day_positions = series_dates.groupby(series_dates).groups  # date -> Index de posicoes

    months = sorted(daily["month"].unique())
    month_col = {m: i for i, m in enumerate(months)}
    n_months = len(months)

    hits = np.zeros((n_sets, n_months))
    bounces = np.zeros((n_sets, n_months))
    cont_count = np.zeros((n_sets, n_months))
    mag_sum = np.zeros((n_sets, n_months))

    win_offsets = np.arange(1, window_min + 1)
    rng = np.random.default_rng(seed)

    for row in daily.itertuples(index=False):
        # sorteio consome o rng na ordem dos dias -> reproduzivel
        levels, set_ids, _side = control_levels.draw_day_levels(
            row.open, row.month_range, n_sets, rng, levels_per_side)

        day_pos = np.asarray(day_positions[row.date])
        D = day_pos.size
        if D == 0:
            continue
        m_col = month_col[row.month]

        d_low = low[day_pos]
        d_high = high[day_pos]

        band_lo = levels[:, None] * (1 - tolerance_pct)
        band_hi = levels[:, None] * (1 + tolerance_pct)
        in_band = (d_low[None, :] <= band_hi) & (d_high[None, :] >= band_lo)   # (L, D)

        shifted = np.concatenate([np.zeros((in_band.shape[0], 1), dtype=bool), in_band[:, :-1]], axis=1)
        event_start = in_band & (~shifted)

        ev_rows, ev_cols = np.nonzero(event_start)
        if ev_rows.size == 0:
            continue

        gi = day_pos[ev_cols]                 # posicao global do toque
        j = gi + window_min                   # fim da janela (global)

        m1 = (gi > 0) & (j < n)
        if not m1.any():
            continue
        ev_rows, gi, j = ev_rows[m1], gi[m1], j[m1]

        # checagem de gap dentro da janela (vetorizada)
        idx_mat = gi[:, None] + win_offsets[None, :]         # (K, window_min)
        gap_ok = ~(gaps[idx_mat] > max_gap_min).any(axis=1)
        if not gap_ok.any():
            continue
        ev_rows, gi, j = ev_rows[gap_ok], gi[gap_ok], j[gap_ok]

        lvl_ev = levels[ev_rows]
        set_ev = set_ids[ev_rows]
        approach_below = close[gi - 1] < lvl_ev
        end_below = close[j] < lvl_ev
        is_bounce = (end_below == approach_below)
        magnitude = np.abs(close[j] - lvl_ev)

        hits[:, m_col] += np.bincount(set_ev, minlength=n_sets)
        bounces[:, m_col] += np.bincount(set_ev[is_bounce], minlength=n_sets)
        cont_mask = ~is_bounce
        cont_count[:, m_col] += np.bincount(set_ev[cont_mask], minlength=n_sets)
        mag_sum[:, m_col] += np.bincount(set_ev[cont_mask], weights=magnitude[cont_mask], minlength=n_sets)

    return {
        "months": months,
        "hits": hits,
        "bounces": bounces,
        "cont_count": cont_count,
        "mag_sum": mag_sum,
    }


# ---------------------------------------------------------------------------
# Niveis de extremo local (swing points): roster varia por dia (ver
# local_levels.py), mas e uma UNICA realizacao real (nao ha "conjuntos"
# simulados como no controle). Reaproveita o scan vetorizado por dia do
# controle, mas retorna eventos granulares (como run_round_level_events),
# para poder ser testado contra o MESMO controle 20R+20S ja usado pelos
# niveis redondos -- mesma maquina estatistica (stats.py), so muda o
# "grid" de origem.
# ---------------------------------------------------------------------------

def run_local_extrema_events(df: pd.DataFrame, daily_levels: dict, tolerance_pct: float = 0.0001,
                             window_min: int = 15, max_gap_min: int = 5,
                             time_col: str = "time") -> pd.DataFrame:
    """
    `daily_levels`: dict {date: [niveis...]} de local_levels.daily_active_levels.
    `df` deve JA estar filtrado por sessao. Retorna eventos no mesmo formato
    de run_round_level_events (grid="local_extrema", level_type="local").
    """
    series = _prepare_series(df, time_col=time_col)
    close = series["close"].to_numpy()
    high = series["high"].to_numpy()
    low = series["low"].to_numpy()
    gaps = series["gap_min"].to_numpy()
    months = series["month"].to_numpy()
    times = series[time_col].to_numpy()
    n = len(series)

    series_dates = series[time_col].dt.date
    day_positions = series_dates.groupby(series_dates).groups

    win_offsets = np.arange(1, window_min + 1)
    rows = []

    for date, levels_today in daily_levels.items():
        if not levels_today or date not in day_positions:
            continue
        day_pos = np.asarray(day_positions[date])
        if day_pos.size == 0:
            continue

        levels = np.asarray(levels_today, dtype=float)
        d_low = low[day_pos]
        d_high = high[day_pos]

        band_lo = levels[:, None] * (1 - tolerance_pct)
        band_hi = levels[:, None] * (1 + tolerance_pct)
        in_band = (d_low[None, :] <= band_hi) & (d_high[None, :] >= band_lo)

        shifted = np.concatenate([np.zeros((in_band.shape[0], 1), dtype=bool), in_band[:, :-1]], axis=1)
        event_start = in_band & (~shifted)

        ev_rows, ev_cols = np.nonzero(event_start)
        if ev_rows.size == 0:
            continue

        gi = day_pos[ev_cols]
        j = gi + window_min
        m1 = (gi > 0) & (j < n)
        if not m1.any():
            continue
        ev_rows, gi, j = ev_rows[m1], gi[m1], j[m1]

        idx_mat = gi[:, None] + win_offsets[None, :]
        gap_ok = ~(gaps[idx_mat] > max_gap_min).any(axis=1)
        if not gap_ok.any():
            continue
        ev_rows, gi, j = ev_rows[gap_ok], gi[gap_ok], j[gap_ok]

        lvl_ev = levels[ev_rows]
        approach_below = close[gi - 1] < lvl_ev
        end_below = close[j] < lvl_ev
        is_bounce = end_below == approach_below
        magnitude = np.abs(close[j] - lvl_ev)

        for idx in range(len(gi)):
            rows.append({
                "time": times[gi[idx]],
                "month": months[gi[idx]],
                "level": lvl_ev[idx],
                "approach_side": "below" if approach_below[idx] else "above",
                "outcome": "bounce" if is_bounce[idx] else "continuation",
                "magnitude": magnitude[idx],
            })

    if not rows:
        return pd.DataFrame(columns=["time", "month", "level", "approach_side",
                                     "outcome", "magnitude", "grid", "level_type"])
    result = pd.DataFrame(rows)
    result["grid"] = "local_extrema"
    result["level_type"] = "local"
    return result
