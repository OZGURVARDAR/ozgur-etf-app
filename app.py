import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go

st.set_page_config(page_title="Portfolio Tracker", layout="wide")

# =====================================================
# 1) GOOGLE SHEETS (PUBLIC CSV)
# =====================================================
SHEET_ID = "1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

df = pd.read_csv(CSV_URL)
df["Date"] = pd.to_datetime(df["Date"])
df = df.sort_values("Date")

# Sadece hisse işlemleri
df = df[df["Symbol"] != "CASH"]
df = df[df["Quantity"] > 0]

# =====================================================
# 2) TOPLAM MALİYET
# =====================================================
df["Cost"] = df["Quantity"] * df["Price"]
total_invested = df["Cost"].sum()

# =====================================================
# 3) GÜNCEL FİYATLAR
# =====================================================
symbols = df["Symbol"].unique().tolist()

prices = yf.download(
    symbols,
    start=df["Date"].min(),
    progress=False
)["Adj Close"]

if isinstance(prices, pd.Series):
    prices = prices.to_frame()

# =====================================================
# 4) PORTFÖY GÜNCEL DEĞER
# =====================================================
latest_prices = prices.iloc[-1]

current_value = 0
for _, row in df.iterrows():
    sym = row["Symbol"]
    qty = row["Quantity"]
    current_value += qty * latest_prices[sym]

total_return_pct = (current_value - total_invested) / total_invested * 100

# =====================================================
# 5) ZAMAN SERİSİ (PORTFÖY DEĞERİ)
# =====================================================
portfolio_ts = pd.DataFrame(index=prices.index)
portfolio_ts["Value"] = 0.0

for _, row in df.iterrows():
    sym = row["Symbol"]
    qty = row["Quantity"]
    portfolio_ts["Value"] += prices[sym] * qty

# =====================================================
# 6) UI
# =====================================================
st.title("📈 Portfolio Performance (Cash Ignored)")

col1, col2, col3 = st.columns(3)
col1.metric("Toplam Yatırım ($)", f"{total_invested:,.2f}")
col2.metric("Güncel Değer ($)", f"{current_value:,.2f}")
col3.metric("Toplam Getiri (%)", f"{total_return_pct:.2f}%")

fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=portfolio_ts.index,
        y=portfolio_ts["Value"],
        mode="lines",
        name="Portfolio Value"
    )
)

fig.update_layout(
    title="Portföy Değeri (Zaman İçinde)",
    xaxis_title="Tarih",
    yaxis_title="USD",
    template="plotly_dark"
)

st.plotly_chart(fig, use_container_width=True)
