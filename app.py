import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# -------------------------------------------------
# STREAMLIT AYARLARI
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

st.sidebar.markdown("---")
st.sidebar.subheader("Göstergeler")

show_ema = st.sidebar.checkbox("EMA'ları Göster", value=True)
ema1_val = st.sidebar.number_input("EMA 1 Periyot", value=20, min_value=1)
ema2_val = st.sidebar.number_input("EMA 2 Periyot", value=50, min_value=1)

show_rsi = st.sidebar.checkbox("RSI Göster", value=False)
show_drawdown = st.sidebar.checkbox("Drawdown Göster", value=False)
show_benchmark = st.sidebar.checkbox("Benchmark (S&P 500) Kıyasla", value=False)
show_pie = st.sidebar.checkbox("Portföy Dağılımını Göster", value=True)

# -------------------------------------------------
# GOOGLE SHEET'TEN İŞLEM VERİSİ
# -------------------------------------------------
sheet_id = "1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw"
url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"

@st.cache_data(ttl=300)
def load_trades():
    df = pd.read_csv(url)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.groupby(["Date", "Symbol"])["Quantity"].sum().reset_index()
    return df

df_trades = load_trades()
symbols = df_trades["Symbol"].unique().tolist()

download_list = symbols + (["SPY"] if show_benchmark else [])

prices_all = yf.download(
    download_list,
    start="2020-01-01",
    interval="1d",
    progress=False
)

# -------------------------------------------------
# PORTFÖY HESAPLAMA (NAV)
# -------------------------------------------------
close_prices = prices_all["Close"]
if isinstance(close_prices, pd.Series):
    close_prices = close_prices.to_frame(symbols[0])

positions = pd.DataFrame(
    0,
    index=close_prices.index,
    columns=symbols
)

for s in symbols:
    s_trades = (
        df_trades[df_trades["Symbol"] == s]
        .set_index("Date")
        .reindex(close_prices.index)
        .fillna(0)
    )
    positions[s] = s_trades["Quantity"].cumsum()

portfolio_value = (positions * close_prices).sum(axis=1)
portfolio_value = portfolio_value[portfolio_value > 0]

portfolio_df = pd.DataFrame({"Close": portfolio_value})

portfolio_df["Open"] = portfolio_df["Close"].shift(1)
portfolio_df["High"] = portfolio_df[["Open", "Close"]].max(axis=1)
portfolio_df["Low"] = portfolio_df[["Open", "Close"]].min(axis=1)
portfolio_df.dropna(inplace=True)

# -------------------------------------------------
# GRAFİK
# -------------------------------------------------
rows = 1
row_heights = [0.7]

if show_rsi:
    rows += 1
    row_heights.append(0.15)

if show_drawdown:
    rows += 1
    row_heights.append(0.15)

fig = make_subplots(
    rows=rows,
    cols=1,
    shared_xaxes=True,
    vertical_spacing=0.03,
    row_heights=row_heights
)

# -------------------------------------------------
# ANA GRAFİK
# -------------------------------------------------
if chart_type == "Heikin Ashi":
    ha_close = portfolio_df[["Open", "High", "Low", "Close"]].mean(axis=1)
    ha_open = ha_close.copy()
    ha_open.iloc[0] = portfolio_df["Open"].iloc[0]

    for i in range(1, len(ha_open)):
        ha_open.iloc[i] = (ha_open.iloc[i-1] + ha_close.iloc[i-1]) / 2

    ha_high = pd.concat(
        [portfolio_df["High"], ha_open, ha_close], axis=1
    ).max(axis=1)

    ha_low = pd.concat(
        [portfolio_df["Low"], ha_open, ha_close], axis=1
    ).min(axis=1)

    fig.add_trace(
        go.Candlestick(
            x=portfolio_df.index,
            open=ha_open,
            high=ha_high,
            low=ha_low,
            close=ha_close,
            name="Heikin Ashi Portföy"
        ),
        row=1, col=1
    )

elif chart_type == "Çizgi Grafik":
    fig.add_trace(
        go.Scatter(
            x=portfolio_df.index,
            y=portfolio_df["Close"],
            name="Portföy"
        ),
        row=1, col=1
    )

else:
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
# BENCHMARK
# -------------------------------------------------
if show_benchmark and "SPY" in prices_all["Close"].columns:
    # Portföyün gerçek başlangıç tarihi
start_date = portfolio_df.index[0]

spy_raw = prices_all["Close"]["SPY"].dropna()

# SPY'ı portföy başlangıcından başlat
spy = spy_raw.loc[start_date:]

# Aynı tarihlere hizala
spy = spy.reindex(portfolio_df.index).ffill()

# Doğru normalize
spy_norm = spy / spy.iloc[0] * portfolio_df["Close"].iloc[0]


    fig.add_trace(
        go.Scatter(
            x=spy_norm.index,
            y=spy_norm,
            name="S&P 500 (SPY)",
            line=dict(dash="dash")
        ),
        row=1, col=1
    )

# -------------------------------------------------
# RSI
# -------------------------------------------------
current_row = 2
if show_rsi:
    delta = portfolio_df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean().replace(0, 1e-9)

    rsi = 100 - (100 / (1 + avg_gain / avg_loss))

    fig.add_trace(
        go.Scatter(x=portfolio_df.index, y=rsi, name="RSI"),
        row=current_row, col=1
    )
    current_row += 1

# -------------------------------------------------
# DRAWDOWN
# -------------------------------------------------
if show_drawdown:
    dd = (
        (portfolio_df["Close"] - portfolio_df["Close"].cummax())
        / portfolio_df["Close"].cummax()
    ) * 100

    fig.add_trace(
        go.Scatter(
            x=portfolio_df.index,
            y=dd,
            fill="tozeroy",
            name="Drawdown %"
        ),
        row=current_row, col=1
    )

# -------------------------------------------------
# GÖRÜNÜM
# -------------------------------------------------
fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
fig.update_layout(
    template="plotly_dark",
    height=850,
    xaxis_rangeslider_visible=False
)
fig.update_yaxes(side="right")

st.plotly_chart(fig, use_container_width=True)

# -------------------------------------------------
# PASTA GRAFİĞİ
# -------------------------------------------------
if show_pie:
    st.sidebar.markdown("---")
    st.sidebar.subheader("Portföy Dağılımı")

    last_prices = close_prices.iloc[-1]
    pie_values = []

    for s in symbols:
        qty = df_trades[df_trades["Symbol"] == s]["Quantity"].sum()
        pie_values.append(qty * last_prices[s])

    pie_fig = go.Figure(
        data=[go.Pie(labels=symbols, values=pie_values, hole=0.35)]
    )
    pie_fig.update_layout(template="plotly_dark", height=350)
    st.sidebar.plotly_chart(pie_fig, use_container_width=True)
