import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(layout="wide")

st.title("📈 Portfolio Return (Clean Version)")

# --- GOOGLE SHEETS CSV LINK ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

# --- LOAD DATA ---
df = pd.read_csv(SHEET_URL)

# --- BASIC CLEAN ---
df["Date"] = pd.to_datetime(df["Date"])
df["Quantity"] = pd.to_numeric(df["Quantity"], errors="raise")
df["Price"] = pd.to_numeric(df["Price"], errors="raise")

df = df[df["Symbol"] != "CASH"]

# --- INVESTED CAPITAL (NET COST BASIS) ---
df["Cost"] = df["Quantity"] * df["Price"]
invested_capital = df[df["Quantity"] > 0]["Cost"].sum()

# --- CURRENT VALUE ---
symbols = df["Symbol"].unique().tolist()

prices = yf.download(
    symbols,
    period="5d",
    progress=False
)["Close"]

if isinstance(prices, pd.Series):
    prices = prices.to_frame()

def last_price(symbol):
    return prices[symbol].dropna().iloc[-1]

current_value = 0.0

for symbol in symbols:
    net_qty = df[df["Symbol"] == symbol]["Quantity"].sum()
    current_value += net_qty * last_price(symbol)

# --- RETURN ---
total_return_pct = (current_value - invested_capital) / invested_capital * 100

# --- OUTPUT ---
st.metric("Invested Capital ($)", f"{invested_capital:,.2f}")
st.metric("Current Value ($)", f"{current_value:,.2f}")
st.metric("Total Portfolio Return (%)", f"{total_return_pct:.2f}%")
