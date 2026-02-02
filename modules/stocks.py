# modules/stocks.py
import streamlit as st
import pandas as pd
import yfinance as yf

def show():
    st.header("📊 Stocks Portfolio Module")
    
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

    # --- GET LATEST PRICES ---
    symbols = df["Symbol"].unique().tolist()
    prices = yf.download(symbols, period="5d", progress=False)["Close"]
    if isinstance(prices, pd.Series):
        prices = prices.to_frame()

    def get_last_price(symbol: str) -> float:
        return prices[symbol].dropna().iloc[-1]

    # --- CALCULATE STOCK METRICS ---
    stock_data = []

    for symbol in symbols:
        stock_df = df[df["Symbol"] == symbol]
        quantity = stock_df["Quantity"].sum()
        total_cost = (stock_df["Quantity"] * stock_df["Price"]).sum()
        last_price = get_last_price(symbol)
        current_value = quantity * last_price
        total_pl = current_value - total_cost
        total_pl_pct = (total_pl / total_cost) * 100 if total_cost != 0 else 0
        
        # Günlük değişim (dolar ve %)
        prev_close = prices[symbol].dropna().iloc[-2] if len(prices[symbol].dropna()) > 1 else last_price
        daily_change = last_price - prev_close
        daily_change_pct = (daily_change / prev_close * 100) if prev_close != 0 else 0
        
        stock_data.append({
            "Symbol": symbol,
            "Quantity": quantity,
            "Total Cost ($)": total_cost,
            "Current Price ($)": last_price,
            "Current Value ($)": current_value,
            "Total P/L ($)": total_pl,
            "Total P/L (%)": total_pl_pct,
            "Daily Change ($)": daily_change,
            "Daily Change (%)": daily_change_pct
        })

    stocks_df = pd.DataFrame(stock_data)

    # --- OUTPUT METRICS ---
    st.subheader("📊 Stocks Portfolio Overview")
    for i, row in stocks_df.iterrows():
        st.metric(
            label=f"{row['Symbol']} - Current Value ($)",
            value=f"{row['Current Value ($)']:,.2f}",
            delta=f"{row['Total P/L (%)']:.2f}%"
        )

    st.subheader("💹 Detailed Stocks Table")
    st.dataframe(stocks_df.style.format({
        "Total Cost ($)": "{:,.2f}",
        "Current Price ($)": "{:,.2f}",
        "Current Value ($)": "{:,.2f}",
        "Total P/L ($)": "{:,.2f}",
        "Total P/L (%)": "{:.2f}%",
        "Daily Change ($)": "{:,.2f}",
        "Daily Change (%)": "{:.2f}%"
    }))

