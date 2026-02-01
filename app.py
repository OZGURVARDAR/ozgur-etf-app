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

show_benchmark = st.sidebar.checkbox("Benchmark (SPY %)", True)

# -------------------------------------------------
# GOOGLE SHEET
# -------------------------------------------------
sheet_id = "1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw"
url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"

@st.cache_data(ttl=300)
def load_trades():
    df = pd.read_csv(url)
    df["Date"] = pd.to_datetime(df["Date"])
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce").fillna(0.0)
    df["Price"] = pd.to_numeric(df["Price"], errors="coerce").fillna(0.0)
    df["Cash"] = pd.to_numeric(df["Cash"], errors="coerce").fillna(0.0)
    return df

df = load_trades()

# -------------------------------------------------
# MILAT TARİHİ
# -------------------------------------------------
milat_date = df["Date"].min()

# -------------------------------------------------
# SEMBOLLER
# -------------------------------------------------
symbols = sorted(df.loc[df["Symbol"] != "CASH", "Symbol"].unique().tolist())

# -------------------------------------------------
# FİYATLAR
# -------------------------------------------------
prices = yf.download(
    symbols + ["SPY"],
    start=milat_date,
    progress=False
)["Close"]

# -------------------------------------------------
# POZİSYONLAR (HİSSE ADETİ)
# -------------------------------------------------
positions = pd.DataFrame(0.0, index=prices.index, columns=symbols)

for sym in symbols:
    qty_series = (
        df[df["Symbol"] == sym]
        .groupby("Date")["Quantity"]
        .sum()
        .reindex(prices.index, fill_value=0)
    )
    positions[sym] = qty_series.cumsum()

# -------------------------------------------------
# CASH BAKİYESİ
# -------------------------------------------------
cash_flows = (
    df.groupby("Date")["Cash"]
    .sum()
    .reindex(prices.index, fill_value=0)
)

cash_balance = cash_flows.cumsum()

# -------------------------------------------------
# PORTFÖY NAV
# -------------------------------------------------
stock_value = (positions * prices[symbols]).sum(axis=1)
portfolio_nav = stock_value + cash_balance
portfolio_nav = portfolio_nav[portfolio_nav > 0]

# -------------------------------------------------
# OHLC (GRAFİK İÇİN)
# -------------------------------------------------
portfolio_df = pd.DataFrame({"Close": portfolio_nav})
portfolio_df["Open"] = portfolio_df["Close"].shift(1)
portfolio_df["High"] = portfolio_df[["Open", "Close"]].max(axis=1)
portfolio_df["Low"] = portfolio_df[["Open", "Close"]].min(axis=1)
portfolio_df.dropna(inplace=True)

# -------------------------------------------------
# GERÇEK GETİRİ (%)
# -------------------------------------------------
initial_nav = portfolio_df["Close"].iloc[0]
portfolio_return = (portfolio_df["Close"] / initial_nav - 1) * 100

# -------------------------------------------------
# SPY BENCHMARK (%)
# -------------------------------------------------
spy_prices = prices["SPY"].dropna()
spy_prices = spy_prices.loc[portfolio_return.index.min():]

spy_return = (spy_prices / spy_prices.iloc[0] - 1) * 100
spy_return = spy_return.loc[portfolio_return.index]

# -------------------------------------------------
# FIGURE
# -------------------------------------------------
rows = 2 if show_benchmark else 1
row_heights = [0.7, 0.3] if show_benchmark else [1]

fig = make_subplots(
    rows=rows,
    cols=1,
    shared_xaxes=True,
    vertical_spacing=0.05,
    row_heights=row_heights
)

# -------------------------------------------------
# ANA GRAFİK
# -------------------------------------------------
if chart_type == "Mum Grafiği":
    fig.add_trace(
        go.Candlestick(
            x=portfolio_df.index,
            open=portfolio_df["Open"],
            high=portfolio_df["High"],
            low=portfolio_df["Low"],
            close=portfolio_df["Close"],
            name="Portföy NAV"
        ),
        row=1, col=1
    )

elif chart_type == "Heikin Ashi":
    ha_close = portfolio_df[["Open", "High", "Low", "Close"]].mean(axis=1)
    ha_open = ha_close.shift(1).fillna(portfolio_df["Open"])
    ha_high = pd.concat([portfolio_df["High"], ha_open, ha_close], axis=1).max(axis=1)
    ha_low = pd.concat([portfolio_df["Low"], ha_open, ha_close], axis=1).min(axis=1)

    fig.add_trace(
        go.Candlestick(
            x=portfolio_df.index,
            open=ha_open,
            high=ha_high,
            low=ha_low,
            close=ha_close,
            name="Heikin Ashi"
        ),
        row=1, col=1
    )

else:
    fig.add_trace(
        go.Scatter(
            x=portfolio_df.index,
            y=portfolio_df["Close"],
            name="Portföy NAV"
        ),
        row=1, col=1
    )

# -------------------------------------------------
# EMA
# -------------------------------------------------
if show_ema:
    fig.add_trace(
        go.Scatter(
            x=portfolio_df.index,
            y=portfolio_df["Close"].ewm(span=ema1_val).mean(),
            name=f"EMA {ema1_val}"
        ),
        row=1, col=1
    )

    fig.add_trace(
        go.Scatter(
            x=portfolio_df.index,
            y=portfolio_df["Close"].ewm(span=ema2_val).mean(),
            name=f"EMA {ema2_val}"
        ),
        row=1, col=1
    )

# -------------------------------------------------
# BENCHMARK PANEL
# -------------------------------------------------
if show_benchmark:
    fig.add_trace(
        go.Scatter(
            x=portfolio_return.index,
            y=portfolio_return,
            name="Portföy Getiri (%)",
            line=dict(width=2)
        ),
        row=2, col=1
    )

    fig.add_trace(
        go.Scatter(
            x=spy_return.index,
            y=spy_return,
            name="SPY Getiri (%)",
            line=dict(dash="dash", width=2)
        ),
        row=2, col=1
    )

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
