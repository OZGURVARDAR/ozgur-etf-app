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
    ["Mum Grafiği", "Çizgi Grafik"]
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

    # ZORUNLU NUMERIC TEMİZLİK
    for col in ["Quantity", "Price"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # CASH SATIRLARINI AT
    df = df[df["Symbol"] != "CASH"]

    return df

df_trades = load_trades()

# -------------------------------------------------
# MİLAT TARİHİ
# -------------------------------------------------
start_date = df_trades["Date"].min()

symbols = df_trades["Symbol"].unique().tolist()

# -------------------------------------------------
# FİYATLAR
# -------------------------------------------------
prices = yf.download(
    symbols + ["SPY"],
    start=start_date,
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
# PORTFÖY DEĞERİ (SADECE HİSSE)
# -------------------------------------------------
portfolio_value = (positions * prices[symbols]).sum(axis=1)
portfolio_value = portfolio_value[portfolio_value > 0]

# -------------------------------------------------
# % GETİRİLER
# -------------------------------------------------
port_ret = (portfolio_value / portfolio_value.iloc[0] - 1) * 100

spy_prices = prices["SPY"].dropna()
spy_prices = spy_prices.loc[port_ret.index.min():]
spy_ret = (spy_prices / spy_prices.iloc[0] - 1) * 100

common_index = port_ret.index.intersection(spy_ret.index)
port_ret = port_ret.loc[common_index]
spy_ret = spy_ret.loc[common_index]
portfolio_value = portfolio_value.loc[common_index]

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

# --- ANA GRAFİK ---
if chart_type == "Mum Grafiği":
    df_price = pd.DataFrame({"Close": portfolio_value})
    df_price["Open"] = df_price["Close"].shift(1)
    df_price["High"] = df_price[["Open", "Close"]].max(axis=1)
    df_price["Low"] = df_price[["Open", "Close"]].min(axis=1)
    df_price.dropna(inplace=True)

    fig.add_trace(
        go.Candlestick(
            x=df_price.index,
            open=df_price["Open"],
            high=df_price["High"],
            low=df_price["Low"],
            close=df_price["Close"],
            name="Portföy"
        ),
        row=1, col=1
    )
else:
    fig.add_trace(
        go.Scatter(
            x=portfolio_value.index,
            y=portfolio_value,
            name="Portföy"
        ),
        row=1, col=1
    )

# EMA
if show_ema:
    fig.add_trace(
        go.Scatter(
            x=portfolio_value.index,
            y=portfolio_value.ewm(span=ema1_val).mean(),
            name=f"EMA {ema1_val}"
        ),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=portfolio_value.index,
            y=portfolio_value.ewm(span=ema2_val).mean(),
            name=f"EMA {ema2_val}"
        ),
        row=1, col=1
    )

# --- BENCHMARK ---
if show_benchmark:
    fig.add_trace(
        go.Scatter(
            x=port_ret.index,
            y=port_ret,
            name="Portföy Getiri (%)"
        ),
        row=2, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=spy_ret.index,
            y=spy_ret,
            name="SPY Getiri (%)",
            line=dict(dash="dash")
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
