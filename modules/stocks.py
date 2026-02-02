# modules/stocks.py
import streamlit as st
import pandas as pd
import numpy as np
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
    df["Date"] = pd.to_datetime(df["Date"])
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="raise")
    df["Price"] = pd.to_numeric(df["Price"], errors="raise")
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

    # --- CALCULATE TOTAL PORTFOLIO METRICS ---
    total_cost = stocks_df["Total Cost ($)"].sum()
    total_current_value = stocks_df["Current Value ($)"].sum()
    total_pl = total_current_value - total_cost
    total_pl_pct = (total_pl / total_cost * 100) if total_cost != 0 else 0

    # --- SHOW TOTAL PORTFOLIO METRICS ---
    st.subheader("💰 Total Portfolio Overview")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Cost ($)", f"{total_cost:,.2f}")
    col2.metric("Current Value ($)", f"{total_current_value:,.2f}")
    col3.metric("Total P/L ($)", f"{total_pl:,.2f}")
    col4.metric("Total P/L (%)", f"{total_pl_pct:.2f}%")

    # --- COLOR FORMATTING FUNCTION ---
    def color_profit(val):
        if isinstance(val, (int, float)):
            if val > 0:
                return 'color: green'
            elif val < 0:
                return 'color: red'
        return 'color: black'

    # --- DETAILED TABLE ---
    st.subheader("💹 Detailed Stocks Table")
    st.dataframe(
        stocks_df.style.format({
            "Total Cost ($)": "{:,.2f}",
            "Current Price ($)": "{:,.2f}",
            "Current Value ($)": "{:,.2f}",
            "Total P/L ($)": "{:,.2f}",
            "Total P/L (%)": "{:.2f}%",
            "Daily Change ($)": "{:,.2f}",
            "Daily Change (%)": "{:.2f}%"
        }).applymap(color_profit, subset=[
            "Total P/L ($)", "Total P/L (%)", "Daily Change ($)", "Daily Change (%)"
        ]),
        use_container_width=True,
        hide_index=True  # ← Index / sıra numarasını gizledik
    )
