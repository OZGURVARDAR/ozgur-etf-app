# modules/stocks_chart.py
import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

def show():
    st.subheader("📈 Stocks Interactive Charts")

    # --- GOOGLE SHEETS CSV LINK ---
    SHEET_URL = (
        "https://docs.google.com/spreadsheets/d/"
        "1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"
    )

    # --- LOAD STOCK SYMBOLS FROM SHEET ---
    df = pd.read_csv(SHEET_URL)
    df = df[df["Symbol"] != "CASH"]
    symbols = df["Symbol"].unique().tolist()

    # --- FOR EACH STOCK SYMBOL ---
    for symbol in symbols:
        st.markdown(f"### {symbol}")
        df_prices = yf.download(symbol, period="6mo", interval="1d", progress=False)
        df_prices.dropna(inplace=True)

        # --- SMA / EMA ---
        df_prices["SMA20"] = df_prices["Close"].rolling(window=20).mean()
        df_prices["EMA20"] = df_prices["Close"].ewm(span=20, adjust=False).mean()

        # --- ATH ---
        ath = df_prices["Close"].max()
        df_prices["ATH"] = ath

        # --- RSI ---
        delta = df_prices["Close"].diff()
        gain = delta.clip(lower=0)
        loss = -1 * delta.clip(upper=0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        df_prices["RSI"] = 100 - (100 / (1 + rs))

        # --- CREATE PLOTLY FIGURE ---
        fig = go.Figure()

        # Candlestick
        fig.add_trace(go.Candlestick(
            x=df_prices.index,
            open=df_prices['Open'],
            high=df_prices['High'],
            low=df_prices['Low'],
            close=df_prices['Close'],
            name='Price'
        ))

        # SMA/EMA
        fig.add_trace(go.Scatter(
            x=df_prices.index, y=df_prices['SMA20'], mode='lines', name='SMA20', line=dict(color='blue')
        ))
        fig.add_trace(go.Scatter(
            x=df_prices.index, y=df_prices['EMA20'], mode='lines', name='EMA20', line=dict(color='orange')
        ))

        # ATH line
        fig.add_trace(go.Scatter(
            x=df_prices.index, y=df_prices['ATH'], mode='lines', name='ATH', line=dict(color='red', dash='dash')
        ))

        # RSI on secondary y-axis
        fig.add_trace(go.Scatter(
            x=df_prices.index, y=df_prices["RSI"], name="RSI", yaxis="y2", line=dict(color="purple")
        ))

        # Layout settings
        fig.update_layout(
            xaxis_rangeslider_visible=False,
            yaxis_title="Price ($)",
            yaxis2=dict(
                overlaying="y",
                side="right",
                range=[0, 100],
                title="RSI"
            ),
            height=500,
            margin=dict(t=40, b=40)
        )

        st.plotly_chart(fig, use_container_width=True)

