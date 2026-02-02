# modules/stocks_chart.py
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go

def show():
    st.subheader("📈 Portfolio Daily Value Chart")

    # --- GOOGLE SHEETS CSV LINK ---
    SHEET_URL = (
        "https://docs.google.com/spreadsheets/d/"
        "1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"
    )

    # --- LOAD STOCK DATA ---
    df = pd.read_csv(SHEET_URL)
    df = df[df["Symbol"] != "CASH"]
    symbols = df["Symbol"].unique().tolist()

    if len(symbols) == 0:
        st.info("No stocks found in portfolio.")
        return

    # --- FETCH DAILY CLOSE PRICES ---
    prices = yf.download(symbols, period="6mo", interval="1d", progress=False)["Close"]
    
    # Eğer sadece bir hisse varsa dataframe yerine series gelebilir
    if isinstance(prices, pd.Series):
        prices = prices.to_frame()

    # --- CALCULATE DAILY PORTFOLIO VALUE ---
    portfolio_daily = pd.DataFrame(index=prices.index)
    portfolio_daily["Total Value"] = 0

    for symbol in symbols:
        quantity = df.loc[df["Symbol"] == symbol, "Quantity"].sum()
        portfolio_daily["Total Value"] += prices[symbol] * quantity

    # --- OPTIONAL: SMA / EMA of portfolio value ---
    portfolio_daily["SMA20"] = portfolio_daily["Total Value"].rolling(window=20).mean()
    portfolio_daily["EMA20"] = portfolio_daily["Total Value"].ewm(span=20, adjust=False).mean()

    # --- PLOTLY CHART ---
    fig = go.Figure()

    # Portfolio Total Value
    fig.add_trace(go.Scatter(
        x=portfolio_daily.index,
        y=portfolio_daily["Total Value"],
        mode="lines",
        name="Portfolio Value",
        line=dict(color="blue")
    ))

    # SMA / EMA
    fig.add_trace(go.Scatter(
        x=portfolio_daily.index,
        y=portfolio_daily["SMA20"],
        mode="lines",
        name="SMA20",
        line=dict(color="green", dash="dash")
    ))
    fig.add_trace(go.Scatter(
        x=portfolio_daily.index,
        y=portfolio_daily["EMA20"],
        mode="lines",
        name="EMA20",
        line=dict(color="orange", dash="dot")
    ))

    # Layout
    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Portfolio Value ($)",
        height=500,
        margin=dict(t=40, b=40)
    )

    st.plotly_chart(fig, use_container_width=True)
