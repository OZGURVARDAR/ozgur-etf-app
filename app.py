import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("📊 Portföy Getirisi – DOĞRU HESAP (Cash Yok)")

# -----------------------------
# GOOGLE SHEETS
# -----------------------------
sheet_id = "1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw"
url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"

@st.cache_data
def load_trades():
    df = pd.read_csv(url)
    df["Date"] = pd.to_datetime(df["Date"])
    return df

df = load_trades()
df = df[df["Symbol"] != "CASH"]

symbols = df["Symbol"].unique().tolist()
start_date = df["Date"].min()

# -----------------------------
# FİYATLAR
# -----------------------------
prices = yf.download(
    symbols,
    start=start_date,
    progress=False
)["Close"]

# -----------------------------
# POZİSYONLAR
# -----------------------------
positions = pd.DataFrame(0.0, index=prices.index, columns=symbols)

for s in symbols:
    trades = (
        df[df["Symbol"] == s]
        .set_index("Date")
        .reindex(prices.index, fill_value=0)
    )
    positions[s] = trades["Quantity"].cumsum()

# -----------------------------
# PORTFÖY DEĞERİ
# -----------------------------
portfolio_value = (positions * prices).sum(axis=1)
portfolio_value = portfolio_value[portfolio_value > 0]

# -----------------------------
# TOPLAM YATIRILAN PARA
# -----------------------------
# SADECE ALIMLAR
invested = (df[df["Quantity"] > 0]["Quantity"] * df["Price"]).sum()

current_value = portfolio_value.iloc[-1]

total_return_pct = (current_value - invested) / invested * 100

# -----------------------------
# SONUÇ
# -----------------------------
st.metric(
    label="Toplam Portföy Getirisi (%)",
    value=f"{total_return_pct:.2f}%"
)

st.write(f"💰 Toplam Yatırılan: {invested:,.2f} $")
st.write(f"📈 Güncel Değer: {current_value:,.2f} $")

# -----------------------------
# BASİT MUM (KONTROL)
# -----------------------------
df_candle = pd.DataFrame({"Close": portfolio_value})
df_candle["Open"] = df_candle["Close"].shift(1)
df_candle["High"] = df_candle[["Open", "Close"]].max(axis=1)
df_candle["Low"] = df_candle[["Open", "Close"]].min(axis=1)
df_candle.dropna(inplace=True)

fig = go.Figure(go.Candlestick(
    x=df_candle.index,
    open=df_candle["Open"],
    high=df_candle["High"],
    low=df_candle["Low"],
    close=df_candle["Close"]
))

fig.update_layout(
    template="plotly_dark",
    height=600,
    xaxis_rangeslider_visible=False
)

st.plotly_chart(fig, use_container_width=True)
