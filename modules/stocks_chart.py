# modules/stocks_chart.py
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import numpy as np

def show():
    st.subheader("📈 Portfolio Interactive Chart")

    # --- SIDEBAR SETTINGS ---
    chart_type = st.sidebar.selectbox("Portfolio Chart Type", ["Line", "Candlestick", "Heiken Ashi"])
    ema1_days = st.sidebar.number_input("EMA 1 (days)", min_value=1, max_value=200, value=50)
    ema2_days = st.sidebar.number_input("EMA 2 (days)", min_value=1, max_value=200, value=100)
    show_rsi = st.sidebar.checkbox("Show RSI", value=False)
    show_ath = st.sidebar.checkbox("Show ATH", value=False)
    enable_trendline = st.sidebar.checkbox("Enable Trendline Drawing", value=True)

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
        st.info("No stocks in portfolio.")
        return

    # --- FETCH DAILY CLOSE PRICES ---
    prices = yf.download(symbols, period="6mo", interval="1d", progress=False)["Close"]
    if isinstance(prices, pd.Series):
        prices = prices.to_frame()

    # --- CALCULATE DAILY PORTFOLIO VALUE ---
    portfolio_daily = pd.DataFrame(index=prices.index)
    portfolio_daily["Total Value"] = 0
    for symbol in symbols:
        quantity = df.loc[df["Symbol"] == symbol, "Quantity"].sum()
        portfolio_daily["Total Value"] += prices[symbol] * quantity

    # --- EMA ---
    portfolio_daily[f"EMA{ema1_days}"] = portfolio_daily["Total Value"].ewm(span=ema1_days, adjust=False).mean()
    portfolio_daily[f"EMA{ema2_days}"] = portfolio_daily["Total Value"].ewm(span=ema2_days, adjust=False).mean()

    # --- HEIKEN ASHI ---
    if chart_type == "Heiken Ashi" or chart_type == "Candlestick":
        df_ha = portfolio_daily.copy()
        df_ha["HA_Close"] = (df_ha["Total Value"] + df_ha["Total Value"].shift(1).fillna(df_ha["Total Value"].iloc[0])) / 2
        df_ha["HA_Open"] = (df_ha["Total Value"].shift(1).fillna(df_ha["Total Value"].iloc[0]) + df_ha["Total Value"].shift(2).fillna(df_ha["Total Value"].iloc[0])) / 2
        df_ha["HA_High"] = df_ha[["HA_Open", "HA_Close", "Total Value"]].max(axis=1)
        df_ha["HA_Low"] = df_ha[["HA_Open", "HA_Close", "Total Value"]].min(axis=1)

    # --- PLOTLY FIGURE ---
    fig = go.Figure()

    # --- Portfolio Value ---
    if chart_type == "Line":
        fig.add_trace(go.Scatter(
            x=portfolio_daily.index,
            y=portfolio_daily["Total Value"],
            mode="lines",
            name="Portfolio Value",
            line=dict(color="blue", width=2)
        ))
    elif chart_type == "Candlestick":
        fig.add_trace(go.Candlestick(
            x=portfolio_daily.index,
            open=portfolio_daily["Total Value"],
            high=portfolio_daily["Total Value"],
            low=portfolio_daily["Total Value"],
            close=portfolio_daily["Total Value"],
            name="Portfolio Value"
        ))
    elif chart_type == "Heiken Ashi":
        fig.add_trace(go.Candlestick(
            x=df_ha.index,
            open=df_ha["HA_Open"],
            high=df_ha["HA_High"],
            low=df_ha["HA_Low"],
            close=df_ha["HA_Close"],
            name="Portfolio Value (Heiken Ashi)"
        ))

    # --- EMA LINES ---
    fig.add_trace(go.Scatter(
        x=portfolio_daily.index,
        y=portfolio_daily[f"EMA{ema1_days}"],
        mode="lines",
        name=f"EMA{ema1_days}",
        line=dict(color="green", width=2)
    ))
    fig.add_trace(go.Scatter(
        x=portfolio_daily.index,
        y=portfolio_daily[f"EMA{ema2_days}"],
        mode="lines",
        name=f"EMA{ema2_days}",
        line=dict(color="red", width=2)
    ))

    # --- ATH LINE ---
    if show_ath:
        ath_value = portfolio_daily["Total Value"].max()
        fig.add_trace(go.Scatter(
            x=portfolio_daily.index,
            y=[ath_value]*len(portfolio_daily),
            mode="lines",
            name="ATH",
            line=dict(color="red", dash="dash", width=2)
        ))
        st.write(f"Current distance from ATH: {portfolio_daily['Total Value'].iloc[-1] - ath_value:,.2f} $")

    # --- RSI ---
    if show_rsi:
        delta = portfolio_daily["Total Value"].diff()
        gain = delta.clip(lower=0)
        loss = -1 * delta.clip(upper=0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        portfolio_daily["RSI"] = 100 - (100 / (1 + rs))
        fig.add_trace(go.Scatter(
            x=portfolio_daily.index,
            y=portfolio_daily["RSI"],
            name="RSI",
            yaxis="y2",
            line=dict(color="purple")
        ))
        fig.update_layout(
            yaxis2=dict(
                overlaying="y",
                side="right",
                range=[0,100],
                title="RSI"
            )
        )

    # --- TRENDLINE DRAWING ---
    layout_dragmode = "drawline" if enable_trendline else "zoom"
    fig.update_layout(
        xaxis_rangeslider_visible=False,
        yaxis_title="Portfolio Value ($)",
        dragmode=layout_dragmode,
        height=600,
        margin=dict(t=40, b=40)
    )

    # --- Y AXIS FORMATTING (FULL VALUES) ---
    fig.update_yaxes(tickformat=",.0f")  # 12,490 gibi tam değer

    st.plotly_chart(fig, use_container_width=True)
