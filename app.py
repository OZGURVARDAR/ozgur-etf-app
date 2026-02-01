import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(layout="wide")
st.title("📊 Portfolio Return (Cash Ignored – Stable Version)")

# =========================
# LOAD GOOGLE SHEETS
# =========================
SHEET_ID = "1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw"
SHEET_NAME = "Sheet1"

url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}"
df = pd.read_csv(url)

# =========================
# CLEAN DATA
# =========================
df["Quantity"] = (
    df["Quantity"]
    .astype(str)
    .str.replace(",", ".", regex=False)
    .astype(float)
)

df["Price"] = (
    df["Price"]
    .astype(str)
    .str.replace(",", ".", regex=False)
    .astype(float)
)

df["Date"] = pd.to_datetime(df["Date"])

# =========================
# INVESTED CAPITAL
# =========================
df["Cost"] = df["Quantity"] * df["Price"]
invested_capital = df["Cost"].sum()

# =========================
# CURRENT VALUE (SAFE MODE)
# =========================
current_value = 0.0

symbols = df["Symbol"].unique()

for symbol in symbols:
    qty = df[df["Symbol"] == symbol]["Quantity"].sum()

    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="5d")

    if hist.empty:
        st.error(f"Price not found for {symbol}")
        st.stop()

    last_price = hist["Close"].iloc[-1]
    current_value += qty * last_price

# =========================
# RETURN
# =========================
total_return_pct = (current_value - invested_capital) / invested_capital * 100

# =========================
# DISPLAY
# =========================
st.metric(
    "📈 Total Portfolio Return (%)",
    f"{total_return_pct:.2f}%"
)

st.write(f"**Invested Capital:** ${invested_capital:,.2f}")
st.write(f"**Current Value:** ${current_value:,.2f}")
