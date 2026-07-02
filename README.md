# USD/BRL Round Numbers

Replicação da metodologia de Carol Osler para o efeito de "número redondo" (suporte/resistência psicológico) em câmbio intradiário, aplicada ao par **USD/BRL** — nunca testado antes para o Real, até onde levantamos na literatura.

**Status:** concluído. Resultado **nulo** — não há evidência do efeito de Osler para o USD/BRL neste período, nos dois mecanismos candidatos que a própria Osler documenta (números redondos **e** extremos locais/*swing points*). Entregáveis fechados: o [paper](paper/main.pdf) (LaTeX → PDF), a análise reprodutível (`src/`) e a [experiência web](https://hackathon-trainee-fea-dev.github.io/usdbrl-round-numbers/) de divulgação (ao vivo). Ver [Status e próximos passos](#status-e-próximos-passos) no fim.

**🔗 Site ao vivo:** https://hackathon-trainee-fea-dev.github.io/usdbrl-round-numbers/

> **Nota de rigor.** Todos os parâmetros do teste foram fixados **antes** de rodar o confirmatório — não foram ajustados depois de ver resultados —, para evitar p-hacking / sequential testing. As etapas exploratórias que antecederam o desenho final (uma fase pré-Osler e uma versão intermediária do controle) estão registradas em [Transparência metodológica](#transparência-metodológica), apenas como rastro auditável; a resposta do projeto é o resultado confirmatório abaixo.

## Hipótese

Níveis de preço "redondos" (ex.: R$5,00, R$5,50, R$5,10) funcionam como suporte/resistência psicológico em USD/BRL, gerando dois efeitos testáveis no intradiário:

- **H1a — Reversão ("bounce"):** ao tocar um nível redondo, o preço tende a recuar/reverter com mais frequência do que ao tocar um nível de controle (não redondo).
- **H1b — Aceleração:** quando o preço de fato rompe um nível redondo (não reverte), a magnitude do movimento subsequente tende a ser maior do que após romper um nível de controle.

## Metodologia (ancorada em Osler 2000)

Réplica direta de **Osler, C. (2000), "Support for Resistance: Technical Analysis and Intraday Exchange Rates", FRBNY Economic Policy Review, Vol. 6, No. 2**, adaptada para os dados disponíveis (M1 real via MT5, não order-flow proprietário).

> **Fonte dos parâmetros.** O desenho foi conferido ao pé da letra contra o artigo original de **Osler (2000)** no *FRBNY Economic Policy Review* (vol. 6, nº 2, pp. 53–68). O procedimento literal (controle de 20 suportes + 20 resistências por dia, teste de sinal binomial mensal, definições de hit/bounce) está reproduzido abaixo exatamente como no artigo, salvo as adaptações inevitáveis ao cenário brasileiro, sempre sinalizadas.

### Evento unificado (H1a/H1b em um único teste)

1. **Banda de toque:** o preço "toca" um nível redondo quando chega a **0,01%** de distância dele (percentual, escalado pelo range observado — não um valor fixo em centavos). Robustez: 0,00% e 0,02% (mesmos valores testados por Osler).
2. **Janela de classificação:** 15 minutos após o toque (horizonte primário de Osler); 30 minutos como robustez.
3. **Classificação:**
   - Se o preço **voltou** para o lado original do nível dentro da janela → **bounce** (evidência para H1a).
   - Se o preço **permaneceu do outro lado / seguiu** → **continuação** (evidência para H1b; magnitude = quanto se afastou do nível).

> **H1a é a réplica literal; H1b é extensão.** Osler (2000) testa *reversão* (bounce), mas **não** testa aceleração — no texto: *"The hypothesis that prices will trend once a trading signal is breached … is not examined here"* (p.2). Por isso H1a (bounce) é a replicação literal, enquanto **H1b (aceleração/magnitude) entra como extensão explícita**, ancorada em Curcio et al. (1997) e Brock, Lakonishok & LeBaron (1992) — os trabalhos que a própria Osler cita para "os preços se movem rapidamente uma vez rompido o nível".

### Grupo de controle / placebo

Não é offset de grid nem bootstrap de blocos dos retornos — é o **algoritmo de níveis aleatórios do próprio Osler**. Para cada dia de pregão, gera-se **20 resistências (R) + 20 suportes (S)** — o número exato do paper:

```
R_i = Abertura_dia + b_i × range_mês      b_i ~ Uniforme(0, 1)
S_i = Abertura_dia − a_i × range_mês      a_i ~ Uniforme(0, 1)     i = 1..20
```

onde `range_mês` é o maior gap absoluto entre a abertura e as máximas/mínimas intradiárias observadas naquele mês. Os níveis artificiais são **arredondados à precisão de cotação** (4 casas decimais para o USD/BRL — Osler 2000, endnote 3). Compara-se a taxa de bounce/continuação nos níveis redondos reais vs. nesses níveis artificiais.

Osler gerou **10.000 conjuntos** completos. Aqui o run primário usa **N = 5.000** (meio-termo defensável: a estatística de referência do controle é uma **média sobre os conjuntos**, que converge muito antes de 10.000). Parametrizável em `src/run_analysis.py` (`N_SETS`). A geração é feita **por dia, sob demanda** dentro do scan de eventos (`src/events.py`), para não materializar os ~45 milhões de níveis (5.000 × 224 dias × 40) em memória.

### Sessão de negociação (equivalente BR ao recorte 9h–16h NY)

Osler restringe a amostra a 9h–16h NY para excluir o overnight ilíquido do feed 24h da EBS. Aqui a fonte já é um símbolo **onshore** `USDBRL` (FBS-Demo) que **só cota durante o pregão brasileiro**: não existe barra fora de ~14h–23h no timestamp do servidor. O filtro `filter_session` mantém a janela consistente **[15:30, 23:00)** (uniformiza os dias que abrem 15:30 e descarta as poucas barras esparsas de abertura antecipada) — ou seja, a restrição de sessão já vem embutida na fonte, e o filtro só a torna uniforme. O offset exato servidor→horário de Brasília não é confirmável sem documentação do broker (FBS ≈ UTC+2/+3), então a janela é reportada pelo timestamp dos dados.

### Granularidade dos níveis redondos

Hierarquia por força decrescente: **R$1,00 / R$0,50 / R$0,10 / R$0,05**, com **R$0,01 como placebo de falsificação** (nível "redondo" fraco demais para ter efeito psicológico esperado — serve de checagem negativa). A hierarquia foi informada por análise de poder estatístico sobre os dados MT5.

### Extremos locais (mínimos/máximos) — segundo mecanismo candidato

Osler (2000) não deriva os níveis que testa a partir de nenhum algoritmo — o teste central do paper usa níveis **publicados por seis firmas de análise técnica**, e ela apenas *observa*, a posteriori, que esses níveis terminam em 0 ou 5 em 96% dos casos (Tabela 4, p.57). Uma nota de rodapé do próprio paper (endnote 8) revela que, num paper-irmão **não publicado** ("Are Currency Markets Efficient? Predictable Trend Reversals in Intraday Exchange Rates", FRBNY, fev/2000), ela testou se números redondos *ou* extremos locais (mínimos/máximos) — os dois insumos que as firmas mais citam para escolher seus níveis — têm poder preditivo isoladamente. Ela reporta que **ambos têm**, embora nenhum dos dois explique sozinho todo o poder preditivo dos níveis publicados pelas firmas.

Esse paper-irmão não está disponível publicamente e o algoritmo exato que Osler usou para extremos locais não foi localizado. `src/local_levels.py` implementa, portanto, uma **operacionalização própria e documentada** desse segundo mecanismo — ao contrário do controle 20R+20S (réplica literal), este módulo não é uma réplica de um método conhecido, é um desenho novo para um conceito que Osler menciona mas não detalha:

- **Definição (fractal clássico de *swing point*).** Um dia é um **máximo local** ("resistência") confirmado se seu high for maior que o high de *todos* os `k=5` dias de pregão anteriores e seguintes; simétrico para **mínimo local** ("suporte") via low. `k=5` é o fractal padrão de 5 barras (popularizado por Bill Williams) — escolha documentada, ainda não testada por robustez.
- **Sem look-ahead.** A confirmação só é possível `k` dias *depois* do dia candidato (é preciso ver os `k` dias seguintes para saber que ele foi mesmo o extremo). O nível só entra na lista de "ativos" a partir do dia seguinte ao da confirmação.
- **Roster diário.** Os 20 máximos + 20 mínimos confirmados mais recentemente até aquele dia (pode ser menos no início da amostra) — paridade estatística deliberada com o controle 20R+20S de Osler, para manter os dois testes na mesma escala.
- Testado com o **mesmo teste confirmatório e o mesmo controle** (20R+20S/dia) usados nas grades redondas — só muda a origem do nível de tratamento.

### Teste confirmatório

Dois testes complementares, cada grade (redonda ou extremo local) contra a mesma nula de controle.

**(1) PRIMÁRIO — sinal binomial mensal (o teste literal de Osler 2000).** Osler *não* usa percentil de Monte Carlo. O procedimento dela (pp.61-62):

1. Para cada mês, calcula a bounce frequency dos níveis reais → `BP_mês`.
2. Para cada mês, calcula a bounce frequency de cada um dos N conjuntos de controle e tira a **média sobre os conjuntos** → `BA_mês`.
3. Conta em quantos dos `N_meses` vale `BP_mês > BA_mês`.
4. **Teste de sinal binomial:** essa contagem vs. `Binomial(N_meses, 0,5)`; a significância é a cauda superior.

onde `bounce frequency = bounces / total de hits`. A mesma lógica de sinal mensal é aplicada a H1b, trocando a bounce frequency pela magnitude média de continuação (`MP_mês` vs `MA_mês`). Teste **unilateral** (as hipóteses são direcionais).

**(2) COMPLEMENTAR — p-valor empírico Monte Carlo `(r+1)/(N+1)`.** Com apenas ~13 meses de amostra, o sinal binomial é **pouco potente** (precisa de ~10-11 dos 13 meses para p < 0,05). Como checagem mais potente, reportamos em paralelo o p-valor empírico de North, Curtis & Sham (2002): a estatística *agregada* (pooled sobre todos os meses) dos níveis redondos vs. a distribuição dessa mesma estatística sobre os N conjuntos de controle, com `r = #{T_k ≥ T_obs}`.

Cada grade real (R$1,00 / R$0,50 / R$0,10 / R$0,05) é testada; reporta-se o p por grade e, em paralelo, a correção **Bonferroni** sobre as 4 grades (conservadora — grades aninhadas/correlatas). A grade **R$0,01 é placebo de falsificação**: espera-se que *não* seja significativa; se for, é sinal de **artefato**, não de ancoragem real. A grade **`local_extrema`** (extremos locais, ver acima) é testada com o mesmo aparato, mas fora da família Bonferroni das 4 grades redondas — é uma hipótese independente, não uma variante aninhada da grade redonda.

`N = 5.000` conjuntos de controle no run primário. Parametrizável em `src/run_analysis.py` (`N_SETS`, `SEED`).

> **Nota de integridade — correção metodológica.** Uma primeira rodada usou um *proxy* não-literal (controle de 1 R + 1 S por dia, N = 2.000, e p-valor de Monte Carlo como teste primário). Após conferir o desenho contra o **artigo original de Osler (2000)**, ele foi corrigido para a fidelidade literal descrita acima (controle 20+20/dia, teste de sinal binomial mensal). **O resultado nulo de H1a se manteve** entre o proxy e a versão literal — o que reforça a robustez da conclusão. Esta versão literal é a definitiva.

## Dados

- **Fonte primária:** MetaTrader5, símbolo `USDBRL`, conta demo **FBS-Demo**, M1 real (não agregado), de **2025-07-30 a 2026-07-01** (336 dias corridos), 224 dias distintos de pregão.
- **Robustez out-of-sample (planejada):** repetir o mesmo desenho sobre outra corretora demo (ex.: **Tickmill-Demo**) para checar se o nulo é do mercado ou do feed — ver [próximos passos](#status-e-próximos-passos).
- **Sessão:** símbolo *onshore* que só cota o pregão brasileiro; a análise usa a janela consistente **[15:30, 23:00)** do timestamp do servidor (98.694 barras). Ver "Sessão de negociação" acima.
- **PTAX diário (BCB):** taxa oficial de referência do Banco Central, usada apenas como checagem de sanidade da fonte (ver abaixo), não como fonte intradiária.
- Ver detalhes completos de todas as fontes avaliadas e descartadas (HistData, Dukascopy, TradingView, Bloomberg) em [`docs/data-sources.md`](docs/data-sources.md).

### Sanity check da fonte (MT5 vs. PTAX oficial)

Para confirmar que o feed de corretora demo é um proxy legítimo do USD/BRL à vista, casamos o `close` M1 do MT5 com a **PTAX de venda de fechamento** do BCB (API Olinda) **no mesmo instante** — a PTAX é apurada ~13h de Brasília (≈16h UTC), que cai dentro da nossa sessão. Match *nearest* com tolerância de 5 min, 223 dias casados. Roda com `python -m src.sanity_ptax`.

![Sanity check MT5 vs PTAX](figures/sanity_ptax.png)

- **Fonte validada:** correlação de nível **0,998** — o feed reproduz cada oscilação da taxa oficial, **sem erro de escala, unidade ou inversão**.
- **Achado — prêmio de nível:** o feed demo fica **~+72 bps (≈0,7%) acima** da PTAX de forma estável (mediana +71,8 bps, desvio 20 bps, **sem deriva secular** ao longo do ano), comportamento típico de cotação sintética de conta demo (markup de corretora).
- **Limitação decorrente:** os níveis testados são "redondos" *no preço do feed*; o offset de ~0,7% os desloca frente aos redondos do mercado real. Isso é **desprezível para a grade grossa** (R$1,00 ≈ 18% de espaçamento) mas uma fração não-trivial das grades finas (R$0,05 ≈ 0,9%; R$0,01 ≈ 0,18%). Ou seja, **o nulo da grade R$1,00 é o mais confiável**, e o achado reforça o caveat de "cotação demo, não order flow". Não altera a conclusão nula — apenas enfraquece o poder de detectar um eventual efeito real nas grades finas.

### Reprodutibilidade

O snapshot usado na análise (`data/raw/usdbrl_m1_fbs_demo.csv`) é **versionado diretamente no repositório** (não fica em `.gitignore`), justamente para que qualquer pessoa consiga reproduzir a análise sem precisar de uma conta demo MT5 própria. Para gerar um snapshot novo/atualizado, use `src/ingest_mt5.py` com o terminal MT5 aberto e logado. O snapshot da PTAX (`data/raw/ptax_bcb_fechamento.csv`) também é versionado, para que o sanity check rode offline.

## Resultado confirmatório

**Resultado nulo: não há evidência de nenhum dos dois mecanismos de suporte/resistência documentados por Osler (número redondo e extremo local) para o USD/BRL neste conjunto de dados** (13 meses de M1, FBS-Demo, sessão [15:30, 23:00), ~98,7 mil barras). Rodado com `N = 5.000` conjuntos de controle sob o desenho literal. Tabela completa (primário + 3 variantes de robustez, incluindo `local_extrema`) em [`results/confirmatory_results.csv`](results/confirmatory_results.csv); reproduzível com `python -m src.run_analysis`.

Desenho primário (banda 0,01%, janela 15 min). `p_binomial` = teste literal de sinal mensal; `p_MC` = Monte Carlo complementar:

| Grade | Hipótese | Meses (BP>BA) | Est. obs. | Nula (média) | p_binomial | p_MC |
|-------|----------|:-------------:|----------:|-------------:|-----------:|-----:|
| R$1,00 | H1a bounce | 0/2 | 0,447 | 0,550 | 1,000 | 1,000 |
| R$0,50 | H1a bounce | 3/6 | 0,546 | 0,550 | 0,656 | 0,814 |
| R$0,10 | H1a bounce | 4/12 | 0,519 | 0,550 | 0,927 | 1,000 |
| R$0,05 | H1a bounce | 8/13 | 0,551 | 0,550 | 0,291 | 0,347 |
| R$1,00 | H1b magnitude | 1/2 | 0,0039 | 0,0046 | 0,750 | 1,000 |
| R$0,50 | H1b magnitude | 4/6 | 0,0047 | 0,0046 | 0,344 | 0,058 |
| R$0,10 | H1b magnitude | 7/12 | 0,0048 | 0,0046 | 0,387 | **0,001** |
| R$0,05 | H1b magnitude | 5/13 | 0,0047 | 0,0046 | 0,867 | **0,004** |
| **R$0,01 (placebo)** | H1a bounce | 6/13 | 0,546 | 0,550 | 0,709 | 0,827 |
| **R$0,01 (placebo)** | H1b magnitude | 6/13 | 0,0047 | 0,0046 | 0,709 | **0,025** |
| **Extremo local (extensão)** | H1a bounce | 6/11 | 0,542 | 0,550 | 0,500 | 0,975 |
| **Extremo local (extensão)** | H1b magnitude | 8/11 | 0,0054 | 0,0046 | 0,113 | **0,000** |

Leitura:

- **H1a (reversão) — nulo, os dois testes concordam, nas duas famílias de nível.** A taxa de bounce nos níveis redondos não supera a de níveis arbitrários: fica igual ou um pouco *abaixo* da média nula (~0,55, valor próximo do ~56% que a própria Osler reporta). Nenhum `p_binomial` nem `p_MC` < 0,05, em nenhuma grade redonda.
- **H1b (aceleração) — nulo pelo teste literal; o "sinal" do Monte Carlo é artefato.** O sinal binomial mensal não acusa nada (todos `p_binomial` ≥ 0,34). O Monte Carlo *pooled* marca algumas grades como significativas (0,10 → 0,001; 0,05 → 0,004) — **mas marca também o placebo R$0,01 (0,025)**, que por construção não deveria ter efeito psicológico. Como o placebo mostra o mesmo padrão, isso é um **artefato de agregação**, não ancoragem: os níveis redondos (e o placebo, que ladrilha quase todo o eixo de preço) sentam exatamente sobre o caminho do preço, enquanto os controles ficam espalhados pelo range mensal — o que enviesa a comparação *pooled* de magnitude. O teste de sinal mensal, que compara mês a mês contra `BA_mês`, não cai nesse viés, e o placebo o denuncia. **Não há evidência crível de aceleração.**
- **Extremos locais (extensão, mesmo desenho) — reproduz exatamente o mesmo veredito.** Testar o segundo mecanismo que Osler cita (mínimos/máximos locais, endnote 8) em vez de número redondo dá o mesmo resultado: H1a nula nos dois testes (`p_binomial`=0,500, `p_MC`=0,975); H1b nula pelo teste literal (`p_binomial`=0,113) mas marcada pelo Monte Carlo *pooled* (`p`=0,0002) — o mesmo padrão de artefato de agregação diagnosticado no placebo, robusto às 4 variantes de banda/janela. Os dois candidatos que a própria Osler documenta para a origem do efeito psicológico foram testados, e **nenhum mostra sinal de suporte/resistência para o USD/BRL** nesta amostra.
- **Robustez:** o nulo de H1a se mantém nas variantes de banda (0,00% / 0,02%) e janela (30 min), nas duas famílias de nível. O padrão de H1b (literal nulo, MC positivo inclusive no placebo e no extremo local) também se repete em todas as variantes, confirmando o diagnóstico de artefato.

**Limitação central — baixa potência (parcial).** Com apenas 13 meses, `Binomial(13, 0,5)` exige ~10-11 meses com `BP>BA` para p < 0,05; grades grossas (R$1,00) têm ainda menos meses com hits (só 2). Mas a checagem de poder abaixo mostra que essa limitação **não se aplica** às grades bem povoadas (R$0,05, R$0,10, extremo local): um efeito do tamanho do que Osler mediu em pares G10 seria detectado. Outras limitações: cotação de corretora demo (não order flow), e a assimetria natural entre o número de eventos de uma grade real e de um conjunto de controle (herdada do desenho de Osler). Ainda assim, a convergência dos dois testes para H1a e o diagnóstico de artefato para H1b tornam a conclusão robusta dentro da amostra disponível.

O mesmo nulo já havia aparecido em análises exploratórias anteriores, com um desenho diferente (ver [Transparência metodológica](#transparência-metodológica)): os mecanismos documentados por Osler para pares de mercados desenvolvidos **não se replicam** de forma detectável para o Real neste período.

### Diagnóstico do nulo

Falha de implementação, de poder estatístico, ou o efeito realmente não está lá?

Diante de um nulo duplo (número redondo e extremo local), vale checar diretamente se a ausência de efeito é um artefato da implementação antes de aceitá-la como conclusão.

**1. A linha de base do controle reproduz o número que a própria Osler publica.** A frequência de bounce dos níveis de controle aleatórios (a nula, sem qualquer efeito especial) ficou em **54,9%–55,5%** neste desenho; Osler reporta **56,2%** para os níveis de controle dela (Table 8, p.61 do paper original — o feed FX tem autocorrelação serial negativa, então *qualquer* nível bate de volta um pouco mais da metade das vezes, por construção). Esse número não depende de nenhuma lógica específica de tratamento (número redondo, extremo local) — só do motor de detecção de toque, classificação bounce/continuação e do algoritmo de controle. Bater tão perto do valor publicado é evidência de que essa maquinaria compartilhada está correta.

**2. Checagem de poder: um efeito do tamanho do de Osler seria detectado?** `src/power_check.py` injeta artificialmente um viés de reversão controlado nos eventos *reais* da grade R$0,05 (converte uma fração aleatória de "continuation" em "bounce") e reaplica o teste confirmatório real contra o controle real:

| Viés injetado | Bounce observado | p_binomial | p_MC | Meses (BP>BA) |
|---:|---:|---:|---:|:---:|
| +0,0pp (dado real) | 55,1% | 0,291 | 0,369 | 8/13 |
| +4,0pp | 59,1% | 0,046 | 0,002 | 10/13 |
| +4,6pp | 59,7% | **0,011** | **0,002** | 11/13 |
| +6,0pp | 61,1% | 0,011 | 0,002 | 11/13 |

`+4,6pp` não é arbitrário: é o efeito que a própria Osler mede para o marco alemão (ela reporta +4,2pp marco, +5,6pp iene, +4,0pp libra — p.61). Nesse tamanho de efeito, o teste confirmatório real acusa significância nos dois testes. Ou seja: **se o USD/BRL tivesse um efeito do tamanho do que Osler encontrou em pares G10, este pipeline o teria detectado.** O nulo observado não é, portanto, uma falha de poder estatístico nas grades bem povoadas — a grade R$1,00 continua sendo um caso à parte de baixa potência (só 2 meses com toques), já discutido acima. Reproduzível com `python -m src.power_check` → [`results/power_check.csv`](results/power_check.csv).

**3. Por que o efeito então não aparece? Três diferenças reais em relação ao desenho de Osler — nenhuma delas um bug:**

- **Curadoria de nível, não enumeração mecânica (a diferença estruturalmente mais importante).** O tratamento de Osler nunca foi "todo número redondo": foram **2 a 18 níveis por firma por dia**, escolhidos por analistas profissionais combinando leitura de fluxo de ordens, linhas de tendência e julgamento. Este projeto (e o próprio teste de números redondos/extremos locais isolados que Osler cita no paper-irmão) testa, em vez disso, **todo** múltiplo de R$0,05 ou **todo** ponto de inflexão confirmado, mecanicamente. Se só uma fração dos níveis redondos/extremos é psicologicamente relevante de fato, misturá-los com muitos níveis irrelevantes dilui qualquer efeito real na agregação — um problema de diluição estrutural, inerente a testar número redondo/extremo local *diretamente*, não um erro de implementação.
- **Definição de toque: OHLC vs. bid/ask.** Osler define um toque especificamente pelo lado do book que dispararia uma ordem real — o **bid** encostando no suporte, o **ask** encostando na resistência. Os dados brutos aqui têm uma única série OHLC (não bid/ask separado) mais uma coluna `spread` (~16 pontos na amostra inspecionada) — cerca de **3x mais larga** que a própria banda de toque de 0,01% (~5-6 pontos perto de uma cotação de 5,60). O "toque" medido aqui é, portanto, um proxy mais grosseiro do que dispararia de fato uma ordem do que a definição bid/ask literal de Osler.
- **Estrutura de mercado: BRL vs. G10.** A explicação da própria Osler para o mecanismo (Osler 2003, *Journal of Finance*) é a concentração de ordens stop-loss/take-profit em números redondos — característica de um mercado G10 fortemente influenciado por mesas de análise técnica no fim dos anos 1990. O USD/BRL é um par emergente com uma base de participantes diferente (mais fluxo macro/carry, menos mesa técnica de varejo), então o mecanismo de concentração de ordens que sustenta o efeito em G10 pode simplesmente ser mais fraco ou ausente aqui — independente de qualquer problema de medição.

Em suma: a maquinaria de detecção/classificação reproduz a linha de base publicada por Osler e demonstrou poder de capturar um efeito do tamanho do dela quando um é injetado. O nulo observado é mais bem explicado por diferenças reais entre "todo número redondo/extremo, medido em OHLC, num par emergente" e "níveis curados por analistas, medidos em bid/ask, em pares G10" — sendo a curadoria a diferença estruturalmente mais importante.

### Corroboração visual — event-study do toque

Além do teste confirmatório, um *event-study* alinha cada toque de nível em `k = 0` e acompanha o **retorno acumulado assinado** (em bps) de −10 a +30 minutos. O sinal segue a direção de aproximação (`+1` se veio de baixo, `−1` se veio de cima), de modo que no eixo y **positivo = continuação** e **negativo = reversão/bounce**. Se H1a fosse verdadeira, a curva dos níveis redondos ficaria *abaixo* da curva de controle no trecho pós-toque.

![Event-study do toque em nível](figures/event_study.png)

Os dois painéis (caminho completo + zoom pós-toque) mostram o nulo de forma direta: pós-toque, os retornos assinados ficam próximos de zero e as curvas dos níveis redondos **coincidem com a banda de controle** de Osler — nenhum sinal de reversão sistemática. O gráfico é leitura visual do resultado, não substitui o teste (a viz usa `N = 25` conjuntos de controle *pooled*, suficiente para uma média suave; o teste confirmatório usa `N = 5.000`). Reproduzível com `python -m src.event_study`; a tabela `média ± SE` por passo e grupo fica em [`results/event_study_paths.csv`](results/event_study_paths.csv) (reaproveitável na experiência web).

## Estrutura do repositório

```
Makefile             atalhos reprodutíveis (make help lista os alvos)
requirements.txt     dependências Python
.github/workflows/   CI: pages.yml publica web/ no GitHub Pages a cada push
docs/                documentação de apoio (ex.: fontes de dados avaliadas)
data/
  raw/               snapshots brutos M1 puxados do MT5 (versionados)
  processed/         dados intermediários derivados (não versionados, regeneráveis)
src/                 pacote de análise (rodar com python -m src.<módulo>)
  ingest_mt5.py      ingestão do histórico M1 via MetaTrader5
  round_levels.py    geração da grade de níveis redondos nominais
  local_levels.py    níveis por extremo local (swing point, k=5 dias) — extensão, ver README
  control_levels.py  gerador de níveis de controle (20 R + 20 S por dia, Osler 2000)
  events.py          filtro de sessão + toque + classificação + scan mensal de controle
  stats.py           teste de sinal binomial mensal (literal) + Monte Carlo (complementar)
  run_analysis.py    driver ponta a ponta (primário + robustez, número redondo + extremo local)
  power_check.py     checagem de poder: injeta efeito do tamanho do de Osler e reaplica o teste
  event_study.py     event-study assinado do toque (redondo vs. controle) → figura + CSV
  sanity_ptax.py     sanity check da fonte: MT5 vs. PTAX oficial do BCB (match por instante)
  export_web_data.py exporta o data.json da experiência web a partir dos dados brutos
paper/               paper científico (o entregável de rigor)
  main.tex           fonte LaTeX
  refs.bib           bibliografia
  main.pdf           PDF compilado (versionado)
web/                 experiência web imersiva (scrollytelling, Canvas 2D vanilla)
  index.html         estrutura dos capítulos
  styles.css         identidade visual "terminal noturno"
  main.js            creative coding: linha de preço, paredes, event-study, scroll suave
  data.json          dados pré-computados servidos à página
results/             tabelas de saída do teste confirmatório e da checagem de poder (versionadas)
figures/             figuras de research (event-study, sanity check)
```

## Entregáveis

1. **Paper científico ([`paper/main.pdf`](paper/main.pdf))** — o entregável de rigor, com o desenho pré-registrado acima (testes, p-valores, robustez, event-study, sanity check). Fonte em LaTeX (`paper/main.tex` + `paper/refs.bib`); recompile com `make paper`.
2. **Análise reprodutível (`src/`)** — o pipeline ponta a ponta que gera os resultados e figuras do paper, com o snapshot de dados versionado para reprodução offline.
3. **Experiência web imersiva (`web/`, [ao vivo](https://hackathon-trainee-fea-dev.github.io/usdbrl-round-numbers/))** — a *camada de comunicação*, pensada para um público leigo entender a história sozinho, sem jargão. Um scrollytelling em Canvas 2D vanilla (sem frameworks) com identidade visual própria ("terminal noturno"): seis capítulos que vão da crença popular → um ano de dólar minuto a minuto e seus toques → o teste como "redondo vs. número sorteado" → o que o dólar faz *depois* de encostar (event-study) → o veredito nulo (com as ressalvas). Os números vêm de `web/data.json`, exportado por `src/export_web_data.py` a partir dos mesmos dados e resultados. O conteúdo técnico-estatístico fica de propósito no paper, não na experiência web.

## Como rodar

Todos os atalhos estão no `Makefile` (`make help` lista os alvos). Sem `make` (Windows), copie o comando equivalente.

```bash
make install       # instala as dependências (pandas, numpy, statsmodels, MetaTrader5)
make research      # roda tudo: teste confirmatório + sanity + event-study + web-data
make web           # serve a experiência web em http://localhost:4321
make paper         # recompila paper/main.pdf (precisa de um TeX no PATH)
```

Ou, alvo a alvo: `make analysis` (→ `results/confirmatory_results.csv`), `make power-check` (→ `results/power_check.csv`, ver [Diagnóstico do nulo](#diagnóstico-do-nulo)), `make sanity` (→ `figures/sanity_ptax.png`), `make event-study` (→ `figures/event_study.png`), `make web-data` (→ `web/data.json`). A ingestão do MT5 (`python -m src.ingest_mt5`) exige o terminal MetaTrader5 aberto e logado; como o snapshot já é versionado, ela **não** faz parte do fluxo padrão.

### Deploy da experiência web

A `web/` é 100% estática (HTML/CSS/JS, sem build) e é publicada no **GitHub Pages** a cada push na `main` pelo workflow [`.github/workflows/pages.yml`](.github/workflows/pages.yml). Todos os caminhos de assets são relativos, então o site roda tanto na raiz de um domínio quanto sob o subpath do Pages. Para reativar num fork: **Settings → Pages → Source = "GitHub Actions"**.

## Status e próximos passos

**Status: concluído.** As perguntas do projeto foram respondidas com os três entregáveis fechados (paper, análise, web), testando os dois mecanismos candidatos que Osler documenta (número redondo e extremo local). A checagem de poder (ver [Diagnóstico do nulo](#diagnóstico-do-nulo)) mostra que a conclusão **não** é, nas grades bem povoadas, um nulo por baixa potência — um efeito do tamanho do de Osler teria sido detectado. A ressalva real é outra: **este projeto testa uma enumeração mecânica de níveis (todo número redondo, todo extremo confirmado), não os níveis curados por analistas que Osler efetivamente usou** — a amostra curta e a cotação demo seguem sendo ressalvas adicionais, mas secundárias a essa. As direções abaixo atacam essas ressalvas — nenhuma é necessária para a conclusão atual, mas todas a fortaleceriam.

- **Níveis curados, não mecânicos.** A diferença mais estrutural em relação ao desenho de Osler. Aproximações possíveis: níveis publicados por casas de análise técnica locais, ou um filtro de relevância (ex.: apenas extremos com volume/amplitude acima de um percentil) em vez de "todo swing point confirmado".
- **Toque via bid/ask, não OHLC.** Os dados atuais têm uma única série de preço; um feed com bid/ask separado testaria a definição literal de Osler (bid encostando no suporte, ask na resistência) em vez do proxy atual (~3x mais largo que a banda de toque).
- **Amostra mais longa (maior potência nas grades grossas).** O gargalo remanescente é a grade R$1,00 (só 2 meses com toques) e a robustez das variantes. Estender para vários anos de M1 ajudaria especificamente aí.
- **Fonte de mercado real (sem o prêmio demo).** Repetir sobre um feed sem o markup de ~72 bps (dados reais de corretora ou provedor institucional) alinharia os níveis redondos finos aos do mercado, removendo o caveat que hoje só deixa a grade R$1,00 plenamente confiável.
- **Robustez out-of-sample entre corretoras.** Rodar o mesmo desenho em outra demo (ex.: Tickmill-Demo) separa o que é do mercado do que é do feed.
- **Order flow real.** Osler explica o efeito pela concentração de ordens *stop*/*take-profit*. Com dados de livro/ordem, dá para testar o *mecanismo* diretamente, não só a sua consequência de preço — e também explicaria por que o USD/BRL, um par com menos fluxo técnico de varejo, pode ter esse mecanismo mais fraco.
- **Extensão a outros ativos (stretch goal).** Aplicar o mesmo arcabouço ao Ibovespa/ações brasileiras, onde números redondos (ex.: 100.000 pts) também são folclore de mesa.

## Transparência metodológica

Para manter o caminho auditável, registramos aqui as etapas exploratórias que **antecederam** o desenho final e que **não** contam como teste confirmatório (foram sequência de testes, com risco de p-hacking). Ficam documentadas apenas como rastro de como o desenho definitivo foi travado, não como resposta do projeto:

- **Fase exploratória inicial** sobre os dados FBS-Demo (~99.823 barras M1), com um desenho pré-Osler (grid + offset arbitrário): teste binário de bounce por bootstrap e regressão de magnitude com erros-padrão Newey-West — resultado nulo (nenhum p-valor < 0,05) em 8 combinações grade × horizonte.
- Nessa fase foi descoberto e corrigido um bug de gap de fim de semana que inflava a contagem de eventos em ~11–12%.
- A correção do controle *proxy* → literal de Osler está descrita na "Nota de integridade" (seção [Teste confirmatório](#teste-confirmatório)); o resultado nulo se manteve em todas as versões.

## Referências

- Osler, C. (2000). "Support for Resistance: Technical Analysis and Intraday Exchange Rates." *FRBNY Economic Policy Review*, 6(2).
- Osler, C. (2003). "Currency Orders and Exchange Rate Dynamics: An Explanation for the Predictive Success of Technical Analysis." *Journal of Finance*, 58(5).
- Alexander, S. (1961). "Price Movements in Speculative Markets: Trends or Random Walks?" *Industrial Management Review*.
- Brock, W., Lakonishok, J., & LeBaron, B. (1992). "Simple Technical Trading Rules and the Stochastic Properties of Stock Returns." *Journal of Finance*, 47(5).
- Curcio, R., Goodhart, C., Guillaume, D., & Payne, R. (1997). "Do Technical Trading Rules Generate Profits? Conclusions from the Intra-day Foreign Exchange Market." *LSE Financial Markets Group Discussion Paper* (âncora do H1b — aceleração após rompimento).
- North, B. V., Curtis, D., & Sham, P. C. (2002). "A Note on the Calculation of Empirical P Values from Monte Carlo Procedures." *American Journal of Human Genetics*, 71(2), 439–441.
- Davison, A. C., & Hinkley, D. V. (1997). *Bootstrap Methods and Their Application.* Cambridge University Press.
