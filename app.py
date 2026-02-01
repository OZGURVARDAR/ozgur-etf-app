import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go

# -------------------------------------------------
# STREAMLIT
# -------------------------------------------------
st.set_page_config(page_title="Özgür – Basit Portföy Testi", layout="wide")

st.title("📊 Basit Portföy Getiri Testi (Cash & Benchmark YOK)")

# -------------------------------------------------
# GOOGLE SHEETS
# -------------------------------------------------
sheet_id = "1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw"
url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"

@st.cache_data(ttl=300)
def load_trades():
    df = pd.read_csv(url)
    df["Date"] = pd.to_datetime(df["Date"])
    return df

df_trades = load_trades()

# SADECE HİSSELER (CASH HARİÇ)
df_trades = df_trades[df_trades["Symbol"] != "CASH"]

symbols = df_trades["Symbol"].unique().tolist()

# -------------------------------------------------
# TARİH ARALIĞI
# -------------------------------------------------
start_date = df_trades["Date"].min()

# -------------------------------------------------
# FİYATLAR
# -------------------------------------------------
prices = yf.download(
    symbols,
    start=start_date,
    interval="1d",
    progress=False
)["Close"]

# -------------------------------------------------
# POZİSYONLAR
# -------------------------------------------------
positions = pd.DataFrame(0.0, index=prices.index, columns=symbols)

for s in symbols:
    trades_s = (
        df_trades[df_trades["Symbol"] == s]
        .set_index("Date")
        .reindex(prices.index, fill_value=0)
    )
    positions[s] = trades_s["Quantity"].cumsum()

# -------------------------------------------------
# PORTFÖY DEĞERİ (NAV)
# -------------------------------------------------
portfolio_value = (positions * prices).sum(axis=1)
portfolio_value = portfolio_value[portfolio_value > 0]

# -------------------------------------------------
# TOPLAM GETİRİ (%)
# -------------------------------------------------
total_return_pct = (
    portfolio_value.iloc[-1] / portfolio_value.iloc[0] - 1
) * 100

st.markdown(
    f"""
    <div style="
        background-color:#111;
        padding:20px;
        border-radius:10px;
        text-align:center;
        font-size:28px;
        font-weight:bold;
        color:#00ff99;
    ">
        Toplam Portföy Getirisi: {total_return_pct:.2f}%
    </div>
    """,
    unsafe_allow_html=True
)

# -------------------------------------------------
# MUM GRAFİĞİ (BASİT)
# -------------------------------------------------
df = pd.DataFrame({"Close": portfolio_value})
df["Open"] = df["Close"].shift(1)
df["High"] = df[["Open", "Close"]].max(axis=1)
df["Low"] = df[["Open", "Close"]].min(axis=1)
df.dropna(inplace=True)

fig = go.Figure()

fig.add_trace(
    go.Candlestick(
        x=df.index,
        open=df["Open"],
        high=df["High"],
        low=df["Low"],
        close=df["Close"],
        name="Portföy"
    )
)

fig.update_layout(
    template="plotly_dark",
    height=700,
    xaxis_rangeslider_visible=False
)

fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
fig.update_yaxes(side="right")

st.plotly_chart(fig, use_container_width=True)
