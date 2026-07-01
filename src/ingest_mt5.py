"""
Ingestao: puxa o historico M1 completo de USDBRL do MT5 (conta demo ativa no momento)
e salva em data/raw/. Contorna o teto de 99.999 barras/chamada encadeando copy_rates_from
com ancora movel ate o inicio real do historico do servidor.

Uso: rode com o terminal MT5 aberto e logado na conta desejada (FBS-Demo ou Tickmill-Demo).
"""
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone
import sys

if not mt5.initialize():
    print(f"initialize() falhou, codigo de erro = {mt5.last_error()}")
    sys.exit(1)

acc = mt5.account_info()
print(f"Conectado: {acc.server} (login {acc.login})")

symbol = "USDBRL"
mt5.symbol_select(symbol, True)

all_dfs = []
anchor = datetime.now(timezone.utc)
seen_min = None
for i in range(20):
    rates = mt5.copy_rates_from(symbol, mt5.TIMEFRAME_M1, anchor, 99999)
    if rates is None or len(rates) == 0:
        break
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    new_min = df["time"].min()
    if seen_min is not None and new_min >= seen_min:
        break
    all_dfs.append(df)
    seen_min = new_min
    anchor = new_min

mt5.shutdown()

df = pd.concat(all_dfs).drop_duplicates(subset="time").sort_values("time").reset_index(drop=True)
print(f"Total barras: {len(df)}")
print(f"Intervalo: {df['time'].min()} ate {df['time'].max()}")

out_path = f"data/raw/usdbrl_m1_{acc.server.lower().replace('-', '_')}.csv"
df.to_csv(out_path, index=False)
print(f"Salvo em {out_path}")
