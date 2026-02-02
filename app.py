import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("📈 Portfolio Performance & Stock Contribution Analysis with Cash + Benchmark (Graph)")

# --- GOOGLE SHEETS CSV LINKS ---
STOCKS_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv&sheet=Stocks"
CASH_URL   = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv&sheet=Cash"

# --- LOAD DATA ---
stocks_df = pd.read_csv(STOCKS_URL)
cash_df   = pd.read_csv(CASH_URL)

# --- CLEAN STOCKS ---
stocks_df["Date"] = pd.to_datetime(stocks_df["Date"])
stocks_df["Quantity"] = pd.to_numeric(stocks_df["Quantity"], errors="raise")
stocks_df["Price"] = pd.to_numeric(stocks_df["Price"], errors="raise")
stocks_df["Cost"] = stocks_df["Quantity"] * stocks_df["Price"]

# --- INVESTED CAPITAL ---
invested_capital = stocks_df[stocks_df["Quantity"] > 0]["Cost"].sum()

# --- SYMBOLS ---
symbols = stocks_df["Symbol"].unique().tolist()
price_symbols = [s for s in symbols]

# --- PRICE DATA ---
price_data = yf.download(price_symbols, period="6mo", progress=False)["Close"]
if isinstance(price_data, pd.Series):
    price_data = price_data.to_frame()

def last_price(symbol):
    return price_data[symbol].dropna().iloc[-1]

def prev_close(symbol):
    closes = price_data[symbol].dropna()
    return closes.iloc[-2] if len(closes) >= 2 else closes.iloc[-1]

# --- CURRENT VALUE & CONTRIBUTION ---
current_value = 0.0
rows = []

for symbol in symbols:
    sdf = stocks_df[stocks_df["Symbol"] == symbol]
    net_qty = sdf["Quantity"].sum()
    buy_cost = sdf[sdf["Quantity"]>0]["Cost"].sum()
    price = last_price(symbol)
    prev = prev_close(symbol)
    value = net_qty * price
    total_change = value - buy_cost
    total_change_pct = (total_change / buy_cost * 100) if buy_cost != 0 else 0
    daily_change = price - prev
    daily_change_pct = (daily_change / prev * 100) if prev != 0 else 0
    current_value += value
    rows.append({
        "Symbol": symbol,
        "Price": round(price,2),
        "Change": round(daily_change,2),
        "Change %": round(daily_change_pct,2),
        "Quantity": net_qty,
        "Cost": round(buy_cost,2),
        "Total Change": round(total_change,2),
        "Total % Change": round(total_change_pct,2),
        "Current Value": round(value,2)
    })

# --- CASH ---
# Sütun adlarını normalize et
cash_df.columns = cash_df.columns.str.strip().str.replace("\n","")
cash_df["Amount"] = pd.to_numeric(cash_df["Amount"], errors="raise")
cash_remaining = cash_df["Amount"].sum()
cash_ratio_pct = (cash_remaining / (current_value + cash_remaining) * 100) if (current_value + cash_remaining) != 0 else 0

# --- TOTAL RETURN ---
total_return_pct = (current_value - invested_capital) / invested_capital * 100

# --- METRICS ---
st.subheader("📊 Portfolio Summary")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Invested Capital ($)", f"{invested_capital:,.2f}")
c2.metric("Current Value ($)", f"{current_value:,.2f}")
c3.metric("Total Portfolio Return (%)", f"{total_return_pct:.2f}%")
c4.metric("Cash Remaining", f"{cash_ratio_pct:.2f}%", f"${cash_remaining:,.2f}")

# --- CONTRIBUTION TABLE ---
st.subheader("🧩 Stock Contribution Analysis")
contrib_df = pd.DataFrame(rows).sort_values("Total Change", ascending=False)
st.dataframe(contrib_df, use_container_width=True)

# --- BENCHMARK + PORTFOLIO GRAPH ---
st.subheader("📈 Portfolio vs Benchmarks")
benchmarks = {"US500":"^GSPC","US100":"^NDX"}

portfolio_daily = stocks_df.groupby("Date").apply(lambda x: (x["Quantity"]*x["Price"]).sum()).rename("Portfolio Value")
portfolio_daily = portfolio_daily.sort_index()

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=portfolio_daily.index, y=portfolio_daily.values,
    mode='lines+markers', name='Portfolio', line=dict(color='blue')
))

for name, ticker in benchmarks.items():
    data = yf.download(ticker, start=portfolio_daily.index.min(), end=portfolio_daily.index.max(), progress=False)["Close"]
    if isinstance(data, pd.DataFrame):
        data = data.iloc[:,0]
    fig.add_trace(go.Scatter(
        x=data.index, y=data.values, mode='lines', name=name
    ))

fig.update_layout(
    title="Portfolio vs Benchmarks",
    xaxis_title="Date",
    yaxis_title="Value ($)",
    legend_title="Legend",
    height=500
)
st.plotly_chart(fig, use_container_width=True)
