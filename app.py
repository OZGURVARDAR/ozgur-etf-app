import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(layout="wide")
st.title("📈 Portfolio Performance & Stock Contribution Analysis with Cash")

# --- GOOGLE SHEETS CSV LINK ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

# --- LOAD DATA ---
df = pd.read_csv(SHEET_URL)

# --- BASIC CLEAN ---
df["Date"] = pd.to_datetime(df["Date"])
df["Quantity"] = pd.to_numeric(df["Quantity"], errors="raise")
df["Price"] = pd.to_numeric(df["Price"], errors="raise")

# --- COST BASIS ---
df["Cost"] = df["Quantity"] * df["Price"]

# --- INVESTED CAPITAL (EXCLUDE CASH) ---
invested_capital = df[df["Symbol"] != "CASH"]
invested_capital = invested_capital[invested_capital["Quantity"] > 0]["Cost"].sum()

# --- SYMBOLS (INCLUDE CASH FOR PORTFOLIO VALUE) ---
symbols = df["Symbol"].unique().tolist()

# --- PRICE DATA (LAST + PREV CLOSE) FOR NON-CASH ---
price_symbols = [s for s in symbols if s != "CASH"]
price_data = yf.download(
    price_symbols,
    period="5d",
    progress=False
)["Close"]

if isinstance(price_data, pd.Series):
    price_data = price_data.to_frame()

def last_price(symbol):
    if symbol == "CASH":
        return 1.0  # Nakit birim fiyatı
    return price_data[symbol].dropna().iloc[-1]

def prev_close(symbol):
    if symbol == "CASH":
        return 1.0
    closes = price_data[symbol].dropna()
    return closes.iloc[-2] if len(closes) >= 2 else closes.iloc[-1]

# --- CURRENT VALUE & CONTRIBUTION TABLE ---
current_value = 0.0
rows = []

for symbol in symbols:
    sdf = df[df["Symbol"] == symbol]

    net_qty = sdf["Quantity"].sum()
    buy_cost = sdf[sdf["Quantity"] > 0]["Cost"].sum()

    price = last_price(symbol)
    prev = prev_close(symbol)

    value = net_qty * price
    total_change = value - buy_cost if symbol != "CASH" else 0
    total_change_pct = (total_change / buy_cost) * 100 if buy_cost != 0 else 0

    daily_change = price - prev if symbol != "CASH" else 0
    daily_change_pct = (daily_change / prev) * 100 if prev != 0 else 0

    current_value += value

    rows.append({
        "Symbol": symbol,
        "Price": round(price, 2),
        "Change": round(daily_change, 2),
        "Change %": round(daily_change_pct, 2),
        "Quantity": net_qty,
        "Cost": round(buy_cost, 2),
        "Total Change": round(total_change, 2),
        "Total % Change": round(total_change_pct, 2),
        "Current Value": round(value, 2)
    })

# --- TOTAL RETURN (EXCLUDE CASH) ---
total_return_pct = (current_value - invested_capital - df[df["Symbol"]=="CASH"]["Cost"].sum()) / invested_capital * 100

# --- SUMMARY ---
st.subheader("📊 Portfolio Summary (Cash Included for Value)")
c1, c2, c3, c4 = st.columns(4)
cash_value = df[df["Symbol"]=="CASH"]["Cost"].sum()

c1.metric("Invested Capital ($)", f"{invested_capital:,.2f}")
c2.metric("Current Value ($)", f"{current_value:,.2f}")
c3.metric("Total Portfolio Return (%)", f"{total_return_pct:.2f}%")
c4.metric("Cash Ratio (%)", f"{(cash_value / current_value * 100):.2f}%")

# --- CONTRIBUTION TABLE ---
st.subheader("🧩 Stock Contribution Analysis with Cash")
contrib_df = pd.DataFrame(rows).sort_values("Total Change", ascending=False)
st.dataframe(contrib_df, use_container_width=True)
