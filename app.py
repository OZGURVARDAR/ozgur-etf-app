import streamlit as st
import pandas as pd
import yfinance as yf

# -------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------
st.set_page_config(layout="wide")
st.title("📈 Portfolio Return (Core Engine Stable)")

# -------------------------------------------------
# GOOGLE SHEETS CSV LINK
# -------------------------------------------------
SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"
)

# -------------------------------------------------
# LOAD & CLEAN DATA
# -------------------------------------------------
df = pd.read_csv(SHEET_URL)

df["Date"] = pd.to_datetime(df["Date"])
df["Quantity"] = pd.to_numeric(df["Quantity"], errors="raise")
df["Price"] = pd.to_numeric(df["Price"], errors="raise")

# CASH işlemleri portföy hesaplarına dahil edilmez
df = df[df["Symbol"] != "CASH"]


# -------------------------------------------------
# CORE PORTFOLIO CALCULATION ENGINE
# -------------------------------------------------
def calculate_portfolio_metrics(df: pd.DataFrame) -> dict:
    """
    Core portfolio calculation engine.
    This logic is locked to preserve historical correctness (%11.48).
    """

    # --- INVESTED CAPITAL ---
    df = df.copy()
    df["Cost"] = df["Quantity"] * df["Price"]
    invested_capital = df.loc[df["Quantity"] > 0, "Cost"].sum()

    # --- CURRENT VALUE ---
    symbols = df["Symbol"].unique().tolist()

    prices = yf.download(
        symbols,
        period="5d",
        progress=False
    )["Close"]

    if isinstance(prices, pd.Series):
        prices = prices.to_frame()

    def get_last_price(symbol: str) -> float:
        return prices[symbol].dropna().iloc[-1]

    current_value = 0.0
    for symbol in symbols:
        net_quantity = df.loc[df["Symbol"] == symbol, "Quantity"].sum()
        current_value += net_quantity * get_last_price(symbol)

    # --- RETURN ---
    total_return_pct = (
        (current_value - invested_capital) / invested_capital * 100
    )

    return {
        "invested_capital": invested_capital,
        "current_value": current_value,
        "total_return_pct": total_return_pct
    }


# -------------------------------------------------
# RUN CORE ENGINE
# -------------------------------------------------
metrics = calculate_portfolio_metrics(df)

invested_capital = metrics["invested_capital"]
current_value = metrics["current_value"]
total_return_pct = metrics["total_return_pct"]

# -------------------------------------------------
# OUTPUT
# -------------------------------------------------
st.metric("Invested Capital ($)", f"{invested_capital:,.2f}")
st.metric("Current Value ($)", f"{current_value:,.2f}")
st.metric("Total Portfolio Return (%)", f"{total_return_pct:.2f}%")
