import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(layout="wide", page_title="Özgür ETF – TWR")

# ===============================
# GOOGLE SHEETS
# ===============================
SHEET_ID = "1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw"
URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

@st.cache_data(ttl=300)
def load_data():
    df = pd.read_csv(URL)
    df["Date"] = pd.to_datetime(df["Date"])
    for c in ["Quantity", "Price", "Cash"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    return df

df = load_data()

# ===============================
# TARİHLER
# ===============================
start = df["Date"].min()
end = pd.Timestamp.today()

# ===============================
# SEMBOLLER
# ===============================
symbols = df.loc[df["Symbol"] != "CASH", "Symbol"].unique().tolist()

# ===============================
# FİYATLAR (HATA KIRILMAZ)
# ===============================
raw = yf.download(symbols + ["SPY"], start=start, end=end, progress=False)

# ---- Adj Close varsa al, yoksa Close ----
if isinstance(raw.columns, pd.MultiIndex):
    if "Adj Close" in raw.columns.levels[0]:
        prices = raw["Adj Close"]
    else:
        prices = raw["Close"]
else:
    prices = raw["Adj Close"] if "Adj Close" in raw.columns else raw["Close"]

prices = prices.ffill()

# ===============================
# POZİSYONLAR
# ===============================
positions = pd.DataFrame(0.0, index=prices.index, columns=symbols)

for s in symbols:
    qty = (
        df[df["Symbol"] == s]
        .set_index("Date")["Quantity"]
        .reindex(prices.index, fill_value=0)
    )
    positions[s] = qty.cumsum()

# ===============================
# PORTFÖY DEĞERİ
# ===============================
asset_value = (positions * prices[symbols]).sum(axis=1)

cash_flows = (
    df.set_index("Date")["Cash"]
    .reindex(prices.index, fill_value=0)
)

cash_balance = cash_flows.cumsum()

total_value = asset_value + cash_balance
total_value = total_value[total_value > 0]

# ===============================
# TWR (GERÇEK GETİRİ)
# ===============================
returns = []
prev = None

for d in total_value.index:
    V = total_value.loc[d]
    CF = cash_flows.loc[d]

    if prev is not None and prev != 0:
        returns.append((V - CF) / prev - 1)

    prev = V

twr = (pd.Series(returns) + 1).prod() - 1

# ===============================
# SPY
# ===============================
spy = prices["SPY"].loc[total_value.index]
spy_ret = spy / spy.iloc[0] - 1

# ===============================
# GRAFİK
# ===============================
fig = make_subplots(
    rows=2,
    cols=1,
    shared_xaxes=True,
    row_heights=[0.7, 0.3]
)

fig.add_trace(
    go.Scatter(x=total_value.index, y=total_value, name="Portföy Değeri"),
    row=1, col=1
)

fig.add_trace(
    go.Scatter(
        x=spy_ret.index,
        y=spy_ret * 100,
        name="SPY (%)",
        line=dict(dash="dash")
    ),
    row=2, col=1
)

fig.update_layout(
    template="plotly_dark",
    height=900,
    xaxis_rangeslider_visible=False
)

fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])

st.plotly_chart(fig, use_container_width=True)

st.metric("Portföy TWR (%)", f"{twr*100:.2f}")
st.metric("SPY (%)", f"{spy_ret.iloc[-1]*100:.2f}")
