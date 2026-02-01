import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("📊 Portföy Getirisi – Temel ve Doğru")

# -----------------------------
# GOOGLE SHEETS
# -----------------------------
sheet_id = "1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw"
url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"

@st.cache_data
def load_data():
    df = pd.read_csv(url)
    df["Date"] = pd.to_datetime(df["Date"])

    # 🔴 ZORUNLU TİP DÖNÜŞÜMÜ
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce").fillna(0)
    df["Price"] = pd.to_numeric(df["Price"], errors="coerce").fillna(0)

    return df

df = load_data()
df = df[df["Symbol"] != "CASH"]

# -----------------------------
# SEMBOLLER
# -----------------------------
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

current_value = float(portfolio_value.iloc[-1])

# -----------------------------
# TOPLAM YATIRIM (SADECE ALIM)
# -----------------------------
invested = float(
    (df[df["Quantity"] > 0]["Quantity"] * df["Price"]).sum()
)

# -----------------------------
# GETİRİ
# -----------------------------
total_return_pct = (current_value - invested) / invested * 100

st.metric("Toplam Portföy Getirisi (%)", f"{total_return_pct:.2f}%")
st.write(f"💰 Toplam Yatırılan: {invested:,.2f} $")
st.write(f"📈 Güncel Değer: {current_value:,.2f} $")

# -----------------------------
# GRAFİK (SADE)
# -----------------------------
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=portfolio_value.index,
    y=portfolio_value,
    mode="lines",
    name="Portföy Değeri"
))

fig.update_layout(
    template="plotly_dark",
    height=600
)

st.plotly_chart(fig, use_container_width=True_
