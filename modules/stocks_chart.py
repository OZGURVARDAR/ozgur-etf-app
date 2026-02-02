import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def show():
    st.subheader("📈 Portfolio Interactive Chart")

    # --- SIDEBAR SETTINGS ---
    chart_type = st.sidebar.selectbox("Portfolio Chart Type", ["Line", "Candlestick", "Heiken Ashi"])
    ema1_days = st.sidebar.number_input("EMA 1 (days)", min_value=1, max_value=200, value=50)
    ema2_days = st.sidebar.number_input("EMA 2 (days)", min_value=1, max_value=200, value=100)
    show_rsi = st.sidebar.checkbox("Show RSI", value=False)
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

    # --- EMA LINES ---
    portfolio_daily[f"EMA{ema1_days}"] = portfolio_daily["Total Value"].ewm(span=ema1_days, adjust=False).mean()
    portfolio_daily[f"EMA{ema2_days}"] = portfolio_daily["Total Value"].ewm(span=ema2_days, adjust=False).mean()

    # --- CREATE SUBPLOTS ---
    rows = 2 if show_rsi else 1
    fig = make_subplots(
        rows=rows, cols=1, shared_xaxes=True,
        vertical_spacing=0.08, row_heights=[0.7]+[0.3]*(rows-1)
    )

    # --- PORTFOLIO VALUE ---
    if chart_type == "Line":
        fig.add_trace(go.Scatter(
            x=portfolio_daily.index,
            y=portfolio_daily["Total Value"],
            mode="lines",
            name="Portfolio Value",
            line=dict(color="blue", width=2)
        ), row=1, col=1)
    elif chart_type == "Candlestick":
        # Günlük Open/High/Low/Close (proxy: open=önceki gün close)
        open_val = portfolio_daily["Total Value"].shift(1).fillna(portfolio_daily["Total Value"].iloc[0])
        high_val = pd.concat([portfolio_daily["Total Value"], open_val], axis=1).max(axis=1)
        low_val = pd.concat([portfolio_daily["Total Value"], open_val], axis=1).min(axis=1)
        close_val = portfolio_daily["Total Value"]

        fig.add_trace(go.Candlestick(
            x=portfolio_daily.index,
            open=open_val,
            high=high_val,
            low=low_val,
            close=close_val,
            name="Portfolio Value"
        ), row=1, col=1)
    elif chart_type == "Heiken Ashi":
        df_ha = portfolio_daily.copy()
        df_ha["HA_Close"] = (df_ha["Total Value"] + df_ha["Total Value"].shift(1).fillna(df_ha["Total Value"].iloc[0])) / 2
        df_ha["HA_Open"] = (df_ha["Total Value"].shift(1).fillna(df_ha["Total Value"].iloc[0]) +
                            df_ha["Total Value"].shift(2).fillna(df_ha["Total Value"].iloc[0])) / 2
        df_ha["HA_High"] = df_ha[["HA_Open", "HA_Close", "Total Value"]].max(axis=1)
        df_ha["HA_Low"] = df_ha[["HA_Open", "HA_Close", "Total Value"]].min(axis=1)

        fig.add_trace(go.Candlestick(
            x=df_ha.index,
            open=df_ha["HA_Open"],
            high=df_ha["HA_High"],
            low=df_ha["HA_Low"],
            close=df_ha["HA_Close"],
            name="Portfolio Value (Heiken Ashi)"
        ), row=1, col=1)

    # --- EMA LINES ---
    fig.add_trace(go.Scatter(
        x=portfolio_daily.index,
        y=portfolio_daily[f"EMA{ema1_days}"],
        mode="lines",
        name=f"EMA{ema1_days}",
        line=dict(color="green", width=2)
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=portfolio_daily.index,
        y=portfolio_daily[f"EMA{ema2_days}"],
        mode="lines",
        name=f"EMA{ema2_days}",
        line=dict(color="red", width=2)
    ), row=1, col=1)

    # --- RSI ALT PANEL ---
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
            line=dict(color="purple")
        ), row=2, col=1)

    # --- TRENDLINE DRAWING (Kalınlık azaltıldı, silme manuel) ---
    layout_dragmode = "drawline" if enable_trendline else "zoom"
    fig.update_layout(
        xaxis_rangeslider_visible=False,
        yaxis_title="Portfolio Value ($)",
        dragmode=layout_dragmode,
        height=600,
        margin=dict(t=40, b=40)
    )

    # --- Y AXIS FULL VALUES ---
    fig.update_yaxes(tickformat=",.0f")  # 12,490 gibi tam değer

    # --- X AXIS: Tarih, yatay ve okunabilir ---
    fig.update_xaxes(tickangle=0, tickformat="%Y-%m-%d")  # Dik yazıları yatay yaptı

    st.plotly_chart(fig, use_container_width=True)
