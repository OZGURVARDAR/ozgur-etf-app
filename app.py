import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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
ema1_val = st.sidebar.number_input("EMA 1", value=20)
ema2_val = st.sidebar.number_input("EMA 2", value=50)

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

prices = yf.download(
    symbols + ["SPY"],
    start="2020-01-01",
    progress=False
)["Close"]

# -------------------------------------------------
# PORTFÖY HESABI (DOĞRU)
# -------------------------------------------------
positions = pd.DataFrame(0.0, index=prices.index, columns=symbols)

for s in symbols:
    s_trades = (
        df_trades[df_trades["Symbol"] == s]
        .set_index("Date")
        .reindex(prices.index, fill_value=0)
    )
    positions[s] = s_trades["Quantity"].cumsum()

portfolio = (positions * prices[symbols]).sum(axis=1)
portfolio = portfolio[portfolio > 0]

df = pd.DataFrame({"Close": portfolio})
df["Open"] = df["Close"].shift(1)
df["High"] = df[["Open", "Close"]].max(axis=1)
df["Low"] = df[["Open", "Close"]].min(axis=1)
df.dropna(inplace=True)

# -------------------------------------------------
# RETURN INDEX (BENCHMARK İÇİN)
# -------------------------------------------------
port_index = (1 + df["Close"].pct_change().fillna(0)).cumprod()

spy = prices["SPY"].loc[port_index.index.min():]
spy_index = (1 + spy.pct_change().fillna(0)).cumprod()

# -------------------------------------------------
# FIGURE
# -------------------------------------------------
fig = make_subplots(
    rows=2 if show_benchmark else 1,
    cols=1,
    shared_xaxes=True,
    row_heights=[0.7, 0.3] if show_benchmark else [1]
)

# --- MAIN PRICE ---
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
    ha_open = ha_close.shift(1).fillna(df["Open"])
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

# --- BENCHMARK ---
if show_benchmark:
    fig.add_trace(go.Scatter(
        x=port_index.index,
        y=port_index,
        name="Portföy Getiri"
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=spy_index.index,
        y=spy_index,
        name="SPY Getiri",
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
