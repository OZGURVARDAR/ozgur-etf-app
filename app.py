import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("📈 Portfolio Performance & Stock Contribution Analysis with Cash + Benchmark (Graph)")

# --- GOOGLE SHEETS CSV LINK ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

# --- LOAD DATA ---
df = pd.read_csv(SHEET_URL)

# --- BASIC CLEAN ---
df["Date"] = pd.to_datetime(df["Date"])
df["Quantity"] = pd.to_numeric(df["Quantity"], errors="raise")
df["Price"] = pd.to_numeric(df["Price"], errors="raise")
df["Cost"] = df["Quantity"] * df["Price"]

# --- INVESTED CAPITAL (EXCLUDE CASH) ---
invested_capital = df[df["Symbol"] != "CASH"]
invested_capital = invested_capital[invested_capital["Quantity"] > 0]["Cost"].sum()

# --- SYMBOLS ---
symbols = df["Symbol"].unique().tolist()
price_symbols = [s for s in symbols if s != "CASH"]

# --- PRICE DATA FOR NON-CASH ---
price_data = yf.download(price_symbols, period="6mo", progress=False)["Close"]
if isinstance(price_data, pd.Series):
    price_data = price_data.to_frame()

def last_price(symbol):
    if symbol == "CASH":
        return 1.0
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

# --- CASH ---
cash_row = df[df["Symbol"]=="CASH"]
cash_value = cash_row["Cost"].sum() if not cash_row.empty else 0
cash_remaining = cash_value
cash_ratio_pct = (cash_remaining / current_value * 100) if current_value != 0 else 0

# --- TOTAL RETURN (EXCLUDE CASH) ---
total_return_pct = (current_value - invested_capital - cash_value) / invested_capital * 100

# --- SUMMARY METRICS ---
st.subheader("📊 Portfolio Summary (Cash Included for Value)")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Invested Capital ($)", f"{invested_capital:,.2f}")
c2.metric("Current Value ($)", f"{current_value:,.2f}")
c3.metric("Total Portfolio Return (%)", f"{total_return_pct:.2f}%")
c4.metric("Cash Remaining", f"{cash_ratio_pct:.2f}%", f"${cash_remaining:,.2f}")

# --- CONTRIBUTION TABLE ---
st.subheader("🧩 Stock Contribution Analysis with Cash")
contrib_df = pd.DataFrame(rows).sort_values("Total Change", ascending=False)
st.dataframe(contrib_df, use_container_width=True)

# --- BENCHMARK + PORTFOLIO GRAPH ---
st.subheader("📈 Portfolio vs Benchmarks (Graph)")

benchmarks = {
    "US500": "^GSPC",
    "US100": "^NDX"
}

timeframes = {
    "1W": 7,
    "1M": 30,
    "3M": 90,
    "6M": 180,
    "YTD": "YTD",
    "1Y": 365,
    "ALL": None
}

# PORTFOLIO DAILY VALUE
portfolio_daily = df.groupby("Date").apply(
    lambda x: sum(x[x["Symbol"]!="CASH"]["Quantity"]*x[x["Symbol"]!="CASH"]["Price"]) +
              sum(x[x["Symbol"]=="CASH"]["Cost"])
).rename("Portfolio Value")

portfolio_daily = portfolio_daily.sort_index()

# --- PLOTLY GRAPH ---
fig = go.Figure()

# Portfolio line
fig.add_trace(go.Scatter(
    x=portfolio_daily.index,
    y=portfolio_daily.values,
    mode='lines+markers',
    name='Portfolio',
    line=dict(color='blue')
))

# Benchmarks
for name, ticker in benchmarks.items():
    # ALL için portföye uyan tarih aralığı
    start_date = portfolio_daily.index.min()
    end_date = portfolio_daily.index.max()
    data = yf.download(ticker, start=start_date, end=end_date, progress=False)["Close"]
    if isinstance(data, pd.DataFrame):
        data = data.iloc[:,0]
    fig.add_trace(go.Scatter(
        x=data.index,
        y=data.values,
        mode='lines',
        name=name
    ))

fig.update_layout(
    title="Portfolio vs Benchmarks",
    xaxis_title="Date",
    yaxis_title="Value ($)",
    legend_title="Legend",
    height=500
)

st.plotly_chart(fig, use_container_width=True)
