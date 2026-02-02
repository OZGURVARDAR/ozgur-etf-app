import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(layout="wide")
st.title("📈 Portfolio Performance & Contribution Analysis")

# --- GOOGLE SHEETS CSV LINK ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

# --- LOAD DATA ---
df = pd.read_csv(SHEET_URL)

# --- BASIC CLEAN ---
df["Date"] = pd.to_datetime(df["Date"])
df["Quantity"] = pd.to_numeric(df["Quantity"], errors="raise")
df["Price"] = pd.to_numeric(df["Price"], errors="raise")

# Exclude cash completely from performance
df = df[df["Symbol"] != "CASH"]

# --- COST BASIS ---
df["Cost"] = df["Quantity"] * df["Price"]
invested_capital = df[df["Quantity"] > 0]["Cost"].sum()

# --- CURRENT PRICES ---
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

# --- CURRENT VALUE ---
current_value = 0.0
symbol_data = []

for symbol in symbols:
    symbol_df = df[df["Symbol"] == symbol]

    net_qty = symbol_df["Quantity"].sum()
    buy_cost = symbol_df[symbol_df["Quantity"] > 0]["Cost"].sum()
    price = last_price(symbol)
    value = net_qty * price

    contribution = value - buy_cost
    contribution_pct = (contribution / invested_capital) * 100 if invested_capital != 0 else 0

    current_value += value

    symbol_data.append({
        "Symbol": symbol,
        "Net Quantity": net_qty,
        "Avg Buy Price": buy_cost / symbol_df[symbol_df["Quantity"] > 0]["Quantity"].sum()
        if symbol_df[symbol_df["Quantity"] > 0]["Quantity"].sum() != 0 else 0,
        "Current Price": price,
        "Current Value ($)": value,
        "Contribution ($)": contribution,
        "Contribution (%)": contribution_pct
    })

# --- TOTAL RETURN ---
total_return_pct = (current_value - invested_capital) / invested_capital * 100

# --- OUTPUT METRICS ---
st.subheader("📊 Portfolio Summary")
col1, col2, col3 = st.columns(3)
col1.metric("Invested Capital ($)", f"{invested_capital:,.2f}")
col2.metric("Current Value ($)", f"{current_value:,.2f}")
col3.metric("Total Portfolio Return (%)", f"{total_return_pct:.2f}%")

# --- CONTRIBUTION TABLE ---
st.subheader("🧩 Contribution by Asset")
contrib_df = pd.DataFrame(symbol_data).sort_values("Contribution ($)", ascending=False)
st.dataframe(contrib_df, use_container_width=True)
