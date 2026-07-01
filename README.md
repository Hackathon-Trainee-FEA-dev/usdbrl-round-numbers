# USD/BRL Round Numbers

Replicação da metodologia de Carol Osler para o efeito de "número redondo" (suporte/resistência psicológico) em câmbio intradiário, aplicada ao par **USD/BRL** — nunca testado antes para o Real, até onde levantamos na literatura.

> **Este README documenta o desenho pré-registrado antes de rodar o teste confirmatório.** Os parâmetros abaixo foram travados antes de qualquer resultado ser observado, para evitar p-hacking / sequential testing. Resultados exploratórios de uma fase piloto anterior (com desenho diferente, descartado) existem apenas como motivação histórica e **não** devem ser citados como resposta final — ver seção "Fase piloto" abaixo.

## Hipótese

Níveis de preço "redondos" (ex.: R$5,00, R$5,50, R$5,10) funcionam como suporte/resistência psicológico em USD/BRL, gerando dois efeitos testáveis no intradiário:

- **H1a — Reversão ("bounce"):** ao tocar um nível redondo, o preço tende a recuar/reverter com mais frequência do que ao tocar um nível de controle (não redondo).
- **H1b — Aceleração:** quando o preço de fato rompe um nível redondo (não reverte), a magnitude do movimento subsequente tende a ser maior do que após romper um nível de controle.

## Metodologia (ancorada em Osler 2000)

Réplica direta de **Osler, C. (2000), "Support for Resistance: Technical Analysis and Intraday Exchange Rates", FRBNY Economic Policy Review, Vol. 6, No. 2**, adaptada para os dados disponíveis (M1 real via MT5, não order-flow proprietário).

> Fonte dos parâmetros: cópia mirror do paper (o PDF original do NY Fed bloqueou fetch automatizado com erro 403). Os números foram considerados confiáveis o bastante para ancorar o desenho, mas **serão confirmados contra o PDF original antes da versão final do paper.**

### Evento unificado (H1a/H1b em um único teste)

1. **Banda de toque:** o preço "toca" um nível redondo quando chega a **0,01%** de distância dele (percentual, escalado pelo range observado — não um valor fixo em centavos). Robustez: 0,00% e 0,02% (mesmos valores testados por Osler).
2. **Janela de classificação:** 15 minutos após o toque (horizonte primário de Osler); 30 minutos como robustez.
3. **Classificação:**
   - Se o preço **voltou** para o lado original do nível dentro da janela → **bounce** (evidência para H1a).
   - Se o preço **permaneceu do outro lado / seguiu** → **continuação** (evidência para H1b; magnitude = quanto se afastou do nível).

### Grupo de controle / placebo

Não é offset de grid nem bootstrap de blocos dos retornos — é o **algoritmo de níveis aleatórios do próprio Osler**: para cada dia, gerar níveis artificiais

```
R = Abertura + b × range
S = Abertura − a × range
a, b ~ Uniforme(0, 1)
```

onde `range` é o maior gap absoluto entre a abertura e as máximas/mínimas intradiárias observadas naquele mês. Compara-se a taxa de bounce/continuação nos níveis redondos reais vs. nesses níveis artificiais (Osler usou 10.000 conjuntos; ajustamos N pelo custo computacional).

### Granularidade dos níveis redondos

Hierarquia por força decrescente: **R$1,00 / R$0,50 / R$0,10 / R$0,05**, com **R$0,01 como placebo de falsificação** (nível "redondo" fraco demais para ter efeito psicológico esperado — serve de checagem negativa). Definida por análise de poder estatístico real sobre os dados MT5 durante a fase piloto.

### Teste confirmatório (p-valor empírico Monte Carlo)

Segue diretamente a lógica de Osler (2000): os `N` conjuntos de níveis de controle artificiais formam uma **distribuição nula empírica** de como um nível *arbitrário* se comporta. A estatística observada nos níveis redondos reais é comparada contra essa distribuição.

- **H1a (reversão):** taxa de bounce nos níveis redondos > taxa de bounce em níveis arbitrários. Estatística: `bounce_rate = n_bounce / (n_bounce + n_continuation)`. Teste **unilateral** (a hipótese de Osler é direcional).
- **H1b (aceleração):** magnitude média dos eventos de *continuação* nos níveis redondos > nos de controle. Estatística: média de `|close_fim_janela − nível|` entre continuações. Também unilateral.

Para cada conjunto de controle `k = 1..N`, calcula-se a mesma estatística, formando a nula `{T_k}`. O p-valor empírico unilateral usa a fórmula `(r + 1) / (N + 1)` de North, Curtis & Sham (2002), onde `r = #{T_k ≥ T_obs}` (o `+1` evita p = 0 e corresponde a incluir a própria amostra observada).

Cada grade real (R$1,00 / R$0,50 / R$0,10 / R$0,05) é testada contra a mesma nula; reporta-se o p-valor por grade e, em paralelo, a correção **Bonferroni** sobre as 4 grades reais (conservadora, já que as grades são aninhadas/correlatas). A grade **R$0,01 é placebo**: espera-se que *não* seja significativa — se for, é sinal de artefato, não de ancoragem real.

`N = 2.000` conjuntos de controle no run primário (resolução de p ≈ 1/2001); Osler usou 10.000, e o custo computacional aqui permite escalar até lá (~3 min) como robustez. Parametrizável em `src/control_levels.py`.

> **Pré-registro:** este teste (estatística, lado, fórmula de p-valor, tratamento de múltiplas grades e placebo) foi fixado e commitado **antes** de rodar o resultado confirmatório — ver histórico do git.

## Dados

- **Fonte primária:** MetaTrader5, símbolo `USDBRL`, conta demo **FBS-Demo**, M1 real (não agregado), ~336 dias corridos (2025-07-30 até hoje), 224 dias distintos de pregão.
- **Robustez out-of-sample:** conta demo **Tickmill-Demo** (corretora diferente, mesmo desenho).
- **PTAX diário (BCB):** usado apenas como checagem de sanidade em nível diário, não como fonte intradiária.
- Ver detalhes completos de todas as fontes avaliadas e descartadas (HistData, Dukascopy, TradingView, Bloomberg) na documentação interna do projeto.

### Reprodutibilidade

O snapshot usado na análise (`data/raw/usdbrl_m1_fbs_demo.csv`) é **versionado diretamente no repositório** (não fica em `.gitignore`), justamente para que qualquer pessoa consiga reproduzir a análise sem precisar de uma conta demo MT5 própria. Para gerar um snapshot novo/atualizado, use `src/ingest_mt5.py` com o terminal MT5 aberto e logado.

## Estrutura do repositório

```
data/
  raw/         snapshots brutos M1 puxados do MT5 (versionados)
  processed/   dados intermediários derivados (não versionados, regeneráveis)
src/           código de ingestão, definição de eventos, estatística e visualização
notebooks/     exploração e validação ad-hoc
```

## Entregáveis

1. Paper/análise com o desenho pré-registrado acima.
2. Dashboard interativo (Streamlit), reaproveitando os mesmos módulos de `src/`.

## Fase piloto (histórico, não confirmatório)

Antes de travar o desenho acima, uma fase exploratória sobre os dados FBS-Demo (~99.823 barras M1) gerou aprendizados que levaram às decisões atuais, mas cujos números **não valem como teste confirmatório** (sequência de testes / risco de p-hacking):

- Descoberta e correção de um bug de gap de fim de semana que inflava a contagem de eventos em ~11-12%.
- Teste binário de bounce (bootstrap simples) e regressão de magnitude com erros-padrão Newey-West, ambos sobre um desenho de grid + offset arbitrário (pré-Osler) — resultado nulo (nenhum p-valor < 0,05) em 8 combinações grid × horizonte.

Esses resultados ficam documentados apenas como motivação para o desenho atual, não como resposta do projeto.

## Referências

- Osler, C. (2000). "Support for Resistance: Technical Analysis and Intraday Exchange Rates." *FRBNY Economic Policy Review*, 6(2).
- Osler, C. (2003). "Currency Orders and Exchange Rate Dynamics: An Explanation for the Predictive Success of Technical Analysis." *Journal of Finance*, 58(5).
- Alexander, S. (1961). "Price Movements in Speculative Markets: Trends or Random Walks?" *Industrial Management Review*.
- Brock, W., Lakonishok, J., & LeBaron, B. (1992). "Simple Technical Trading Rules and the Stochastic Properties of Stock Returns." *Journal of Finance*, 47(5).
- North, B. V., Curtis, D., & Sham, P. C. (2002). "A Note on the Calculation of Empirical P Values from Monte Carlo Procedures." *American Journal of Human Genetics*, 71(2), 439–441.
- Davison, A. C., & Hinkley, D. V. (1997). *Bootstrap Methods and Their Application.* Cambridge University Press.
