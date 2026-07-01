"""
Dashboard interativo — "O dólar respeita números redondos?"

Camada de COMUNICAÇÃO do projeto (o rigor estatístico está no paper/README).
A ideia é que qualquer pessoa, sem background técnico, consiga navegar a
história sozinha: a crença popular, os dados, o teste em linguagem simples e o
veredito.

Roda a partir da raiz do repositório:

    streamlit run dashboard/app.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import events, round_levels  # noqa: E402

RAW_PATH = ROOT / "data" / "raw" / "usdbrl_m1_fbs_demo.csv"
CONFIRM_CSV = ROOT / "results" / "confirmatory_results.csv"
EVENT_CSV = ROOT / "results" / "event_study_paths.csv"

TOL = 0.0001        # banda de toque primária (0,01%), igual à análise
WINDOW = 15         # janela de classificação (min), horizonte primário

# rótulos amigáveis das grades (nada de "0.05" cru pro usuário)
GRID_LABEL = {
    "1.00": "R$ 1,00",
    "0.50": "R$ 0,50",
    "0.10": "R$ 0,10",
    "0.05": "R$ 0,05",
    "0.01_placebo": "R$ 0,01",
}
GRID_COLOR = {
    "1.00": "#1f77b4", "0.50": "#2ca02c", "0.10": "#ff7f0e",
    "0.05": "#d62728", "0.01_placebo": "#7f7f7f",
}


def esc(s: str) -> str:
    """Escapa '$' para o Streamlit não interpretar como LaTeX no markdown."""
    return s.replace("$", "\\$")

st.set_page_config(page_title="O dólar respeita números redondos?",
                   page_icon="🎯", layout="wide")


# ---------------------------------------------------------------------------
# Carregamento (cacheado)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def load_series() -> pd.DataFrame:
    df = events.filter_session(pd.read_csv(RAW_PATH))
    series = events._prepare_series(df)
    series["date"] = series["time"].dt.date
    series["month_str"] = series["time"].dt.strftime("%Y-%m")
    return series


@st.cache_data(show_spinner=False)
def price_range() -> tuple:
    s = load_series()
    return float(s["low"].min()), float(s["high"].max())


@st.cache_data(show_spinner=False)
def compute_touches(grid_name: str) -> pd.DataFrame:
    """Detecta e classifica todos os toques de uma grade (voltou vs passou)."""
    series = load_series()
    lo, hi = price_range()
    step = round_levels.GRIDS[grid_name]
    levels = round_levels.generate_round_levels(lo, hi, step)

    frames = []
    for level in levels:
        ev = events.detect_touch_events(series, level, TOL)
        if ev.empty:
            continue
        cl = events.classify_events(series, ev, level, WINDOW, max_gap_min=5)
        if cl.empty:
            continue
        frames.append(cl)
    if not frames:
        return pd.DataFrame(columns=["time", "level", "outcome"])
    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["time"]).dt.date
    out["outcome_pt"] = out["outcome"].map({"bounce": "Voltou", "continuation": "Passou reto"})
    return out


@st.cache_data(show_spinner=False)
def load_confirm() -> pd.DataFrame:
    return pd.read_csv(CONFIRM_CSV)


@st.cache_data(show_spinner=False)
def load_event_paths() -> pd.DataFrame:
    return pd.read_csv(EVENT_CSV)


# ---------------------------------------------------------------------------
# Telas
# ---------------------------------------------------------------------------

def tela_pergunta():
    st.title("🎯 O dólar respeita números redondos?")
    st.markdown(
        "> Existe uma crença antiga no mercado: o dólar **“bate e volta”** em "
        "números redondos como **R\\$ 5,00** ou **R\\$ 5,50**, como se esses valores "
        "fossem paredes invisíveis. Operadores desenham linhas neles o dia todo."
    )
    st.markdown(
        "A economista **Carol Osler** achou evidência desse efeito em moedas de "
        "países ricos (dólar, iene, marco) lá em 2000. **Ninguém tinha testado "
        "isso para o Real.** Foi o que a gente fez: pegamos **um ano de cotações "
        "minuto a minuto** do dólar e perguntamos, com números na mão:"
    )
    st.header("O número redondo é mesmo uma parede — ou é só superstição?")

    lo, hi = price_range()
    series = load_series()
    c1, c2, c3 = st.columns(3)
    c1.metric("Período analisado", "≈ 1 ano", "jul/2025 – jul/2026")
    c2.metric("Cotações (minuto a minuto)", f"{len(series):,}".replace(",", "."))
    c3.metric("Faixa do dólar no período", f"R$ {lo:.2f} – {hi:.2f}")

    st.info("👈 Use o menu à esquerda para seguir a história — ou pule direto "
            "para **“O veredito”**.")


def tela_explorador():
    st.title("🔎 Veja com seus próprios olhos")
    st.markdown(
        "Abaixo está o preço do dólar. As **linhas horizontais** são os números "
        "redondos. Cada **ponto** é uma vez em que o dólar *encostou* num deles — "
        "🟢 verde se ele **voltou** (respeitou a “parede”), 🔴 vermelho se "
        "**passou reto**."
    )

    series = load_series()
    months = sorted(series["month_str"].unique())

    c1, c2 = st.columns([1, 1])
    with c1:
        grid_name = st.radio(
            "Quão redondo?", list(GRID_LABEL.keys())[:4],
            format_func=lambda g: GRID_LABEL[g], horizontal=True,
            help="Números mais redondos (R\\$ 1,00) são mais raros; menos redondos "
                 "(R\\$ 0,05) aparecem mais vezes.",
        )
    with c2:
        month = st.select_slider("Mês", options=months, value=months[len(months) // 2])

    win = series[series["month_str"] == month]
    touches = compute_touches(grid_name)
    tw = touches[touches["date"].isin(set(win["date"]))]

    lo, hi = win["low"].min(), win["high"].max()
    step = round_levels.GRIDS[grid_name]
    levels = round_levels.generate_round_levels(lo, hi, step)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=win["time"], y=win["close"], mode="lines",
        line=dict(color="#333", width=1), name="Dólar", hoverinfo="skip"))
    for lv in levels:
        fig.add_hline(y=lv, line=dict(color=GRID_COLOR[grid_name], width=1, dash="dot"),
                      opacity=0.5)
    for outcome, color, sym in [("Voltou", "#2ca02c", "circle"),
                                ("Passou reto", "#d62728", "x")]:
        pts = tw[tw["outcome_pt"] == outcome]
        if pts.empty:
            continue
        pt = pts.merge(win[["time", "close"]], on="time", how="left")
        fig.add_trace(go.Scatter(
            x=pt["time"], y=pt["close"], mode="markers", name=outcome,
            marker=dict(color=color, size=8, symbol=sym, line=dict(width=0.5, color="white"))))

    fig.update_layout(
        height=520, hovermode="x unified", margin=dict(t=30, b=10, l=10, r=10),
        yaxis_title="Dólar (R$)", legend=dict(orientation="h", y=1.02, x=0),
        plot_bgcolor="white")
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="#eee")
    st.plotly_chart(fig, use_container_width=True)

    n_voltou = int((tw["outcome_pt"] == "Voltou").sum())
    n_total = len(tw)
    if n_total:
        st.caption(
            f"Em **{month}**, na grade **{esc(GRID_LABEL[grid_name])}**: o dólar encostou "
            f"**{n_total}** vezes e voltou em **{n_voltou}** delas "
            f"(**{n_voltou / n_total * 100:.0f}%**). Guarde esse número — na próxima "
            "tela a gente compara com o acaso.")
    else:
        st.caption("Nenhum toque nessa grade neste mês — tente uma grade menos "
                   "redonda (R\\$ 0,10 / R\\$ 0,05) ou outro mês.")


def tela_teste():
    st.title("⚖️ O teste, sem estatística")
    st.markdown(
        "Saber que o dólar “voltou 55% das vezes” não diz nada sozinho. **55% é "
        "muito ou pouco?** Precisamos de uma régua. A régua é o **acaso**:"
    )
    st.markdown(
        "> Para cada número redondo de verdade, sorteamos um **número qualquer** "
        "(não redondo) e medimos quantas vezes o dólar “voltou” nele também. "
        "Se o redondo fosse uma parede de verdade, o dólar **voltaria mais** no "
        "redondo do que no número sorteado."
    )
    st.markdown("Foi exatamente o método de Osler. E o resultado para o Real:")

    conf = load_confirm()
    prim = conf[(conf["parametro"] == "primario_0.01pct_15min") &
                (conf["hipotese"] == "H1a_bounce")].copy()
    prim = prim[prim["grade"] != "0.01_placebo"]
    order = ["1.00", "0.50", "0.10", "0.05"]
    prim["grade"] = pd.Categorical(prim["grade"], order, ordered=True)
    prim = prim.sort_values("grade")

    labels = [GRID_LABEL[g] for g in prim["grade"]]
    redondo = prim["estatistica_obs"].to_numpy() * 100
    sorteado = prim["nula_media"].to_numpy() * 100

    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=redondo, name="Número REDONDO",
                         marker_color="#d62728",
                         text=[f"{v:.0f}%" for v in redondo], textposition="outside"))
    fig.add_trace(go.Bar(x=labels, y=sorteado, name="Número QUALQUER (sorteado)",
                         marker_color="#9e9e9e",
                         text=[f"{v:.0f}%" for v in sorteado], textposition="outside"))
    fig.update_layout(
        barmode="group", height=430, yaxis_title="% das vezes que o dólar voltou",
        yaxis_range=[0, 75], legend=dict(orientation="h", y=1.05, x=0),
        margin=dict(t=40, b=10, l=10, r=10), plot_bgcolor="white")
    fig.update_yaxes(gridcolor="#eee")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("As barras têm praticamente a mesma altura.")
    st.markdown(
        "Em todos os níveis, o dólar volta **quase igual** num número redondo e "
        "num número sorteado no acaso — sempre em torno de **55%**. "
        "**O número redondo não é uma parede.** Se fosse, a barra vermelha seria "
        "visivelmente mais alta que a cinza. Não é.")


def tela_event_study():
    st.title("⏱️ E depois que encosta, o que acontece?")
    st.markdown(
        "Outra forma de olhar: nos **30 minutos seguintes** a um toque, para onde "
        "o dólar vai *na média*? Alinhamos todos os toques no instante do toque "
        "(o “0” do gráfico) e seguimos o caminho médio."
    )
    st.caption("Acima da linha do zero = o dólar **seguiu em frente** (rompeu). "
               "Abaixo = **voltou** (bounce). Se o número redondo fosse especial, "
               "a linha dele descolaria da linha do acaso.")

    paths = load_event_paths()
    paths = paths[paths["k_min"] >= 0]
    # rótulo do CSV ("R$0,50") -> nome interno da grade ("0.50")
    grp_round = {"R$1,00": "1.00", "R$0,50": "0.50", "R$0,10": "0.10", "R$0,05": "0.05"}

    show = st.multiselect(
        "Quais números mostrar?", list(grp_round.keys()),
        default=["R$0,50", "R$0,10"],
        help="A linha preta (acaso) está sempre visível para comparação.")

    fig = go.Figure()
    ctrl = paths[paths["grupo"] == "Controle (Osler)"]
    fig.add_trace(go.Scatter(
        x=ctrl["k_min"], y=ctrl["mean_bps"], mode="lines",
        line=dict(color="black", width=3), name="Número QUALQUER (acaso)"))
    for label in show:
        gname = grp_round[label]
        sub = paths[paths["grupo"] == label]
        fig.add_trace(go.Scatter(
            x=sub["k_min"], y=sub["mean_bps"], mode="lines",
            line=dict(color=GRID_COLOR[gname], width=2), name=f"Redondo {label}"))

    fig.add_hline(y=0, line=dict(color="#bbb", width=1))
    fig.update_layout(
        height=470, hovermode="x unified",
        xaxis_title="Minutos depois de encostar no número",
        yaxis_title="Caminho médio do dólar (bps)",
        legend=dict(orientation="h", y=1.05, x=0),
        margin=dict(t=40, b=10, l=10, r=10), plot_bgcolor="white")
    fig.update_yaxes(gridcolor="#eee")
    fig.update_xaxes(gridcolor="#eee")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        "As linhas ficam **coladas** e grudadas no zero. Depois de encostar num "
        "número redondo, o dólar em média **não faz nada de diferente** do que "
        "faria em qualquer outro ponto. De novo: **sem parede.**")


def tela_veredito():
    st.title("🏁 O veredito")
    st.success(
        "**Não.** No período analisado, o dólar **não trata números redondos de "
        "forma especial.** Ele bate e volta em R\\$ 5,50 com a mesma frequência com "
        "que faz isso em qualquer número sorteado no acaso.")
    st.markdown(
        "O efeito que Carol Osler documentou para moedas de países ricos "
        "**não apareceu para o Real** nesses dados. A “parede invisível” dos "
        "números redondos, aqui, parece ser mais **superstição** do que física do "
        "mercado.")

    st.divider()
    st.markdown("#### Sendo honestos (as ressalvas)")
    c1, c2 = st.columns(2)
    c1.markdown(
        "🕐 **Olhamos ~1 ano.** É pouco para cravar “nunca acontece” — dá para "
        "afirmar que, se existe algum efeito, ele é **pequeno demais para ser "
        "visto** nesse período.")
    c2.markdown(
        "💹 **Cotação de corretora (conta demo).** Ela acompanha o dólar oficial "
        "quase perfeitamente, mas com um pequeno desvio de nível — outro motivo "
        "para ler o resultado com cuidado nas grades bem finas.")
    st.info("Quer o rigor estatístico completo (testes, p-valores, robustez)? "
            "Está no **paper / README** do projeto.")


# ---------------------------------------------------------------------------
# Navegação
# ---------------------------------------------------------------------------

PAGES = {
    "A pergunta": tela_pergunta,
    "Veja você mesmo": tela_explorador,
    "O teste": tela_teste,
    "Depois que encosta": tela_event_study,
    "O veredito": tela_veredito,
}

st.sidebar.title("O dólar & os números redondos")
st.sidebar.caption("Uma investigação em 5 telas")
choice = st.sidebar.radio("Navegue pela história:", list(PAGES.keys()))
st.sidebar.divider()
st.sidebar.caption("Réplica da metodologia de Carol Osler (2000) para o USD/BRL. "
                   "Dados: MT5 (FBS-Demo), M1, sessão do pregão.")

PAGES[choice]()
