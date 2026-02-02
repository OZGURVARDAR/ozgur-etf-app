import streamlit as st
import pandas as pd
import yfinance as yf

# --- PAGE CONFIG ---
st.set_page_config(layout="wide")
st.title("📈 Portfolio Return (Clean Version)")

# --- GOOGLE SHEETS CSV LINK ---
SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"
)

# --- LOAD DATA ---
df = pd.read_csv(SHEET_URL)

# --- BASIC CLEAN ---
df["Date"] = pd.to_datetime(df["Date"])
df["Quantity"] = pd.to_numeric(df["Quantity"], errors="raise")
df["Price"] = pd.to_numeric(df["Price"], errors="raise")

# Exclude CASH rows
df = df[df["Symbol"] != "CASH"]

# --- PORTFOLIO CALCULATION FUNCTION ---
def calculate_portfolio_metrics(df: pd.DataFrame) -> dict:
    """
    Calculate invested capital, current value, and total return %.
    """
    # Invested capital
    df["Cost"] = df["Quantity"] * df["Price"]
    invested_capital = df.loc[df["Quantity"] > 0, "Cost"].sum()

    # Get latest prices
    symbols = df["Symbol"].unique().tolist()
    prices = yf.download(symbols, period="5d", progress=False)["Close"]
    if isinstance(prices, pd.Series):
        prices = prices.to_frame()

    # Current value
    current_value = 0.0
    for symbol in symbols:
        net_quantity = df.loc[df["Symbol"] == symbol, "Quantity"].sum()
        last_price = prices[symbol].dropna().iloc[-1]
        current_value += net_quantity * last_price

    # Portfolio return %
    total_return_pct = (current_value - invested_capital) / invested_capital * 100

    return {
        "invested_capital": invested_capital,
        "current_value": current_value,
        "total_return_pct": total_return_pct
    }

# --- CALCULATE METRICS ---
metrics = calculate_portfolio_metrics(df)

# --- OUTPUT ---
st.metric("Invested Capital ($)", f"{metrics['invested_capital']:,.2f}")
st.metric("Current Value ($)", f"{metrics['current_value']:,.2f}")
st.metric("Total Portfolio Return (%)", f"{metrics['total_return_pct']:.2f}%")
