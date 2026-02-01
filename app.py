import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# -------------------------------------------------
# STREAMLIT
# -------------------------------------------------
st.set_page_config(page_title="Özgür ETF Terminal", layout="wide")

# -------------------------------------------------
# SIDEBAR
# -------------------------------------------------
st.sidebar.header("🛠 Grafik Ayarları")

chart_type = st.sidebar.selectbox(
    "Grafik Tipi",
    ["Mum Grafiği", "Heikin Ashi", "Çizgi Grafik"]
)

show_ema = st.sidebar.checkbox("EMA'ları Göster", True)
ema1_val = st.sidebar.number_input("EMA 1", value=20, min_value=1)
ema2_val = st.sidebar.number_input("EMA 2", value=50, min_value=1)

show_benchmark = st.sidebar.checkbox("Benchmark (SPY)", True)

# -------------------------------------------------
# GOOGLE SHEET
# -------------------------------------------------
sheet_id = "1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw"
url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"

@st.cache_data(ttl=300)
def load_trades():
    df = pd.read_csv(url)
    df["Date"] = pd.to_datetime(df["Date"])
    return df.groupby(["Date", "Symbol"])["Quantity"].sum().reset_index()

df_trades = load_trades()
symbols = df_trades["Symbol"].unique().tolist()

# -------------------------------------------------
# PRICE DATA
# -------------------------------------------------
prices = yf.download(
    symbols + ["SPY"],
    start="2020-01-01",
    progress=False
)["Close"]

# -------------------------------------------------
# PORTFÖY HESABI
# -------------------------------------------------
positions = pd.DataFrame(0.0, index=prices.index, columns=symbols)

for s in symbols:
    trades = (
        df_trades[df_trades["Symbol"] == s]
        .set_index("Date")
        .reindex(prices.index, fill_value=0)
    )
    positions[s] = trades["Quantity"].cumsum()

portfolio = (positions * prices[symbols]).sum(axis=1)
portfolio = portfolio[portfolio > 0]

df = pd.DataFrame({"Close": portfolio})
df["Open"] = df["Close"].shift(1)
df["High"] = df[["Open", "Close"]].max(axis=1)
df["Low"] = df[["Open", "Close"]].min(axis=1)
df.dropna(inplace=True)

# -------------------------------------------------
# FIGURE
# -------------------------------------------------
rows = 2 if show_benchmark else 1
fig = make_subplots(
    rows=rows,
    cols=1,
    shared_xaxes=True,
    row_heights=[0.7, 0.3] if show_benchmark else [1]
)

# -------------------------------------------------
# MAIN CHART
# -------------------------------------------------
if chart_type == "Mum Grafiği":
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["Open"],
        high=df["High"],
        low=df["Low"],
        close=df["Close"],
        name="Portföy"
    ), row=1, col=1)

elif chart_type == "Heikin Ashi":
    ha_close = df[["Open", "High", "Low", "Close"]].mean(axis=1)
    ha_open = ha_close.shift(1)
    ha_open.iloc[0] = df["Open"].iloc[0]

    ha_high = pd.concat([df["High"], ha_open, ha_close], axis=1).max(axis=1)
    ha_low = pd.concat([df["Low"], ha_open, ha_close], axis=1).min(axis=1)

    fig.add_trace(go.Candlestick(
        x=df.index,
        open=ha_open,
        high=ha_high,
        low=ha_low,
        close=ha_close,
        name="Heikin Ashi"
    ), row=1, col=1)

else:
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df["Close"],
        name="Portföy"
    ), row=1, col=1)

# EMA
if show_ema:
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df["Close"].ewm(span=ema1_val).mean(),
        name=f"EMA {ema1_val}"
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=df.index,
        y=df["Close"].ewm(span=ema2_val).mean(),
        name=f"EMA {ema2_val}"
    ), row=1, col=1)

# -------------------------------------------------
# BENCHMARK (BASE 100)
# -------------------------------------------------
if show_benchmark and "SPY" in prices.columns:

    port_ret = df["Close"].pct_change().fillna(0)
    port_index = (1 + port_ret).cumprod() * 100

    spy_prices = prices["SPY"].dropna()
    spy_prices = spy_prices.loc[port_index.index.min():]

    spy_ret = spy_prices.pct_change().fillna(0)
    spy_index = (1 + spy_ret).cumprod() * 100

    common = port_index.index.intersection(spy_index.index)
    port_index = port_index.loc[common]
    spy_index = spy_index.loc[common]

    fig.add_trace(go.Scatter(
        x=port_index.index,
        y=port_index,
        name="Portföy (Base 100)"
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=spy_index.index,
        y=spy_index,
        name="SPY (Base 100)",
        line=dict(dash="dash")
    ), row=2, col=1)

# -------------------------------------------------
# LAYOUT
# -------------------------------------------------
fig.update_layout(
    template="plotly_dark",
    height=900,
    xaxis_rangeslider_visible=False
)
fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
fig.update_yaxes(side="right")

st.plotly_chart(fig, use_container_width=True)
