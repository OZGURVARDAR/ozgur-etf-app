import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(layout="wide")
st.title("📊 Portfolio Return Checker (Cash Ignored)")

# =========================
# LOAD GOOGLE SHEETS
# =========================
SHEET_ID = "1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw"
SHEET_NAME = "Sheet1"

url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}"
df = pd.read_csv(url)

# Clean
df["Quantity"] = pd.to_numeric(df["Quantity"])
df["Price"] = pd.to_numeric(df["Price"])
df["Date"] = pd.to_datetime(df["Date"])

# =========================
# INVESTED CAPITAL
# =========================
df["Cost"] = df["Quantity"] * df["Price"]
invested_capital = df["Cost"].sum()

# =========================
# CURRENT PRICES
# =========================
symbols = df["Symbol"].unique().tolist()

prices = yf.download(
    tickers=symbols,
    period="5d",
    group_by="ticker",
    auto_adjust=True,
    progress=False
)

def get_last_price(symbol):
    if len(symbols) == 1:
        return prices["Close"].iloc[-1]
    return prices[symbol]["Close"].iloc[-1]

# =========================
# CURRENT VALUE
# =========================
current_value = 0

for _, row in df.iterrows():
    last_price = get_last_price(row["Symbol"])
    current_value += row["Quantity"] * last_price

# =========================
# RETURN
# =========================
total_return_pct = (current_value - invested_capital) / invested_capital * 100

# =========================
# DISPLAY
# =========================
st.metric(
    label="📈 Total Portfolio Return (%)",
    value=f"{total_return_pct:.2f}%"
)

st.divider()

st.subheader("Details")
st.write(f"**Invested Capital:** ${invested_capital:,.2f}")
st.write(f"**Current Value:** ${current_value:,.2f}")
