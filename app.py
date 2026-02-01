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
    return df.groupby(["Date", "Symbol"])["Quantity"].sum().reset_index()

df_trades = load_trades()
symbols = df_trades["Symbol"].unique().tolist()

# -------------------------------------------------
# MILAT TARİHİ (İLK ALIM)
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
# PORTFÖY HESABI (NAV)
# -------------------------------------------------
positions = pd.DataFrame(0.0, index=prices.index, columns=symbols)

for s in symbols:
    s_trades = (
        df_trades[df_trades["Symbol"] == s]
        .set_index("Date")
        .reindex(prices.index, fill_value=0)
    )
    positions[s] = s_trades["Quantity"].cumsum()

portfolio_value = (positions * prices[symbols]).sum(axis=1)
portfolio_value = portfolio_value[portfolio_value > 0]

portfolio_df = pd.DataFrame({"Close": portfolio_value})
portfolio_df["Open"] = portfolio_df["Close"].shift(1)
portfolio_df["High"] = portfolio_df[["Open", "Close"]].max(axis=1)
portfolio_df["Low"] = portfolio_df[["Open", "Close"]].min(axis=1)
portfolio_df.dropna(inplace=True)

# -------------------------------------------------
# BENCHMARK GETİRİ (%)
# -------------------------------------------------
if show_benchmark:
    # Portföy %
    port_ret = (
        portfolio_df["Close"] / portfolio_df["Close"].iloc[0] - 1
    ) * 100

    # SPY %
    spy_prices = prices["SPY"].dropna()
    spy_ret = (
        spy_prices / spy_prices.iloc[0] - 1
    ) * 100

    # Tarih hizalama
    common_index = port_ret.index.intersection(spy_ret.index)
    port_ret = port_ret.loc[common_index]
    spy_ret = spy_ret.loc[common_index]

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
            name="Portföy"
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
            name="Portföy"
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
# BENCHMARK PANEL (%)
# -------------------------------------------------
if show_benchmark:
    fig.add_trace(
        go.Scatter(
            x=port_ret.index,
            y=port_ret,
            name="Portföy Getirisi (%)",
            line=dict(width=2)
        ),
        row=2, col=1
    )

    fig.add_trace(
        go.Scatter(
            x=spy_ret.index,
            y=spy_ret,
            name="SPY Getirisi (%)",
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
