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

show_benchmark = st.sidebar.checkbox("Benchmark (TWR %)", True)

# -------------------------------------------------
# GOOGLE SHEET
# -------------------------------------------------
sheet_id = "1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw"
url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"

@st.cache_data(ttl=300)
def load_trades():
    df = pd.read_csv(url)
    df["Date"] = pd.to_datetime(df["Date"])
    if "Cash" not in df.columns:
        df["Cash"] = 0.0
    return df

df_trades = load_trades()

symbols = df_trades.loc[df_trades["Symbol"] != "CASH", "Symbol"].unique().tolist()

# -------------------------------------------------
# MILAT TARİHİ
# -------------------------------------------------
milat_date = df_trades["Date"].min()

# -------------------------------------------------
# FİYATLAR
# -------------------------------------------------
prices = yf.download(
    symbols + ["SPY"],
    start=milat_date,
    interval="1d",
    progress=False
)["Close"]

# -------------------------------------------------
# POZİSYONLAR
# -------------------------------------------------
positions = pd.DataFrame(0.0, index=prices.index, columns=symbols)

for s in symbols:
    s_trades = (
        df_trades[df_trades["Symbol"] == s]
        .set_index("Date")
        .reindex(prices.index, fill_value=0)
    )
    positions[s] = s_trades["Quantity"].cumsum()

# -------------------------------------------------
# HİSSE DEĞERİ
# -------------------------------------------------
stock_value = (positions * prices[symbols]).sum(axis=1)

# -------------------------------------------------
# NAKİT HESABI
# -------------------------------------------------
cash_flows = (
    df_trades
    .groupby("Date")["Cash"]
    .sum()
    .reindex(prices.index, fill_value=0)
)

cash_balance = cash_flows.cumsum()

# -------------------------------------------------
# PORTFÖY NAV
# -------------------------------------------------
portfolio_value = stock_value + cash_balance
portfolio_value = portfolio_value[portfolio_value > 0]

# -------------------------------------------------
# PORTFÖY OHLC
# -------------------------------------------------
portfolio_df = pd.DataFrame({"Close": portfolio_value})
portfolio_df["Open"] = portfolio_df["Close"].shift(1)
portfolio_df["High"] = portfolio_df[["Open", "Close"]].max(axis=1)
portfolio_df["Low"] = portfolio_df[["Open", "Close"]].min(axis=1)
portfolio_df.dropna(inplace=True)

# -------------------------------------------------
# TWR (PORTFÖY)
# -------------------------------------------------
twr_returns = []
prev_nav = None

for date in portfolio_df.index:
    nav_today = portfolio_df.loc[date, "Close"]
    flow = cash_flows.get(date, 0)

    if prev_nav is None:
        twr_returns.append(0)
    else:
        twr_returns.append((nav_today - flow) / prev_nav - 1)

    prev_nav = nav_today

twr_returns = pd.Series(twr_returns, index=portfolio_df.index)
port_twr_pct = (1 + twr_returns).cumprod() * 100

# -------------------------------------------------
# SPY TWR
# -------------------------------------------------
spy_prices = prices["SPY"].dropna()
spy_prices = spy_prices.loc[port_twr_pct.index.min():]

spy_ret = spy_prices.pct_change().fillna(0)
spy_twr_pct = (1 + spy_ret).cumprod() * 100

# Tarih hizalama
common_index = port_twr_pct.index.intersection(spy_twr_pct.index)
port_twr_pct = port_twr_pct.loc[common_index]
spy_twr_pct = spy_twr_pct.loc[common_index]

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
            x=port_twr_pct.index,
            y=port_twr_pct,
            name="Portföy Getirisi (TWR)",
            line=dict(width=2)
        ),
        row=2, col=1
    )

    fig.add_trace(
        go.Scatter(
            x=spy_twr_pct.index,
            y=spy_twr_pct,
            name="SPY Getirisi",
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
