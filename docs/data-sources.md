# Fontes de dados intradiárias — avaliadas, escolhida e descartadas

Documento de rastro metodológico: registra **todas** as fontes de USD/BRL intradiário
consideradas para o projeto, por que cada uma foi descartada e por que a fonte final
foi escolhida. Complementa a seção [Dados do README](../README.md#dados).

O requisito era **resolução de 1 minuto real** dentro do pregão brasileiro,
para não descaracterizar o efeito de curto prazo que Osler (2000) testa. Fontes que só
entregavam 15 minutos ou densidade ruim no horário de pregão foram rejeitadas por esse
critério.

## Fonte escolhida — MetaTrader5 (contas demo de corretoras reais)

Pacote Python `MetaTrader5` conectado a **contas demo gratuitas de corretoras forex
reais**, símbolo `USDBRL` (par forex/CFD, cotação de mercado real — não é PTAX oficial
nem WDO/futuro).

| Corretora        | Papel                    | Histórico M1                         | Continuidade | Pregões | Barras/dia |
|------------------|--------------------------|--------------------------------------|--------------|---------|------------|
| **FBS-Demo**     | Primária                 | ~336 dias corridos (2025-07-30 →)    | 99,7% em 1 min exato | 224 | ~445 |
| **Tickmill-Demo**| Checagem cruzada/robustez| ~323 dias corridos (2025-08-11 →)    | 98,9%        | 219     | ~455       |

Por que essa fonte:

- **1 minuto de verdade** nas duas — não foi preciso o compromisso de 15 minutos.
- Os preços das duas corretoras **batem entre si** (bid ~5,24–5,25 nas mesmas datas),
  forte indício de que refletem cotação real de mercado, e não preço sintético de conta demo.
- Snapshot versionado no repo (`data/raw/`) para reprodução offline.

**Limite técnico da API:** `copy_rates_from_pos` / `copy_rates_from` tem teto de
**99.999 barras por chamada** (retorna `Invalid params` acima disso). Contornado
encadeando chamadas com `copy_rates_from(symbol, timeframe, anchor_date, 99999)`, movendo
`anchor_date` para trás a cada iteração até a resposta parar de avançar (início do
histórico do servidor).

## Fontes descartadas

- **HistData.com** — confirmado que **não tem USD/BRL** (cobre 66 pares majors e alguns
  emergentes, sem BRL).
- **Dukascopy** — confirmado via a lista de instrumentos do `dukascopy-node`: **não tem
  USD/BRL**.
- **Bloomberg** — sem acesso a terminal (a assinatura disponível era só do Bloomberg.com,
  o site de notícias, que não dá dados intradiários).
- **TradingView `FX_IDC:USDBRL`** (composite/retail, via `tvdatafeed`) — densidade péssima
  dentro do horário de pregão da B3 (~40% de cobertura; dias recentes quase vazios).
  Descartado.
- **TradingView `BMFBOVESPA:WDO1!`** (futuro mini-dólar B3, via `tvdatafeed`) — densidade
  ótima em pregão, mas profundidade curta (~7.140 barras M1, ~16 dias) sem login; o login
  autenticado esbarra no rate limit da própria TradingView no endpoint de signin (confirmado
  por inspeção HTTP direta — não era problema de credencial). Além disso, o basis
  WDO-vs-PTAX é instável (−0,0158 a +0,0224, com troca de sinal), o que inviabiliza uma
  correção simples para taxa à vista. Contratos históricos individuais (WDOK2026 etc.) dão
  mais profundidade, mas só em 15 min — resolução rejeitada.
- **MetaQuotes-Demo** (servidor genérico de teste da MetaQuotes, MT5) — funcionou de
  primeira, mas só ~127 dias de histórico M1 do `USDBRL`; superado pelas contas demo de
  corretoras reais (FBS/Tickmill).

## Armadilhas técnicas (documentadas para não repetir)

- **Nome de servidor MT5 ≠ nome de exibição.** O campo "Server" mostrado pela corretora
  (ex.: "Tickmill-Demo") pode não ser o hostname real de conexão (era
  `demo.mt5tickmill.com`). Selecionar o servidor errado na tela de login causa "carregando"
  infinito, sem erro claro.
- **O terminal trava ao alternar entre múltiplas contas salvas no Navigator.** O
  double-click não dispara novo login de verdade (o Journal não registra tentativa de rede
  para a conta nova; fica preso reconectando na antiga). Resolvido com reinstalação limpa do
  terminal.
- **"Algo Trading" precisa estar ativado** no terminal para a API Python (`mt5.initialize()`)
  autenticar — sem isso, erro "Authorization failed".
