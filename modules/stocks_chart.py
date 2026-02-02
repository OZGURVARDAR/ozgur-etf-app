import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def show():
    st.subheader("📈 Portfolio Interactive Chart (15-min Intra-day, TradingView-like)")

    # --- SIDEBAR SETTINGS ---
    chart_type = st.sidebar.selectbox("Portfolio Chart Type", ["Line", "Candlestick", "Heiken Ashi"])
    ema1_days = st.sidebar.number_input("EMA 1 (days)", min_value=1, max_value=200, value=50)
    ema2_days = st.sidebar.number_input("EMA 2 (days)", min_value=1, max_value=200, value=100)
    show_rsi = st.sidebar.checkbox("Show RSI", value=False)
    enable_trendline = st.sidebar.checkbox("Enable Trendline Drawing", value=False)

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

    # --- FETCH INTRA-DAY DATA (15m) ---
    intraday = yf.download(symbols, period="6mo", interval="15m", progress=False)["Close"]
    if isinstance(intraday, pd.Series):
        intraday = intraday.to_frame()

    # --- CALCULATE INTRA-DAY PORTFOLIO VALUE ---
    portfolio_intraday = pd.DataFrame(index=intraday.index)
    portfolio_intraday["Total Value"] = 0
    for symbol in symbols:
        if symbol in intraday.columns:
            quantity = df.loc[df["Symbol"] == symbol, "Quantity"].sum()
            portfolio_intraday["Total Value"] += intraday[symbol] * quantity

    # --- CHECK IF DATA EXISTS ---
    if portfolio_intraday.empty or portfolio_intraday["Total Value"].isna().all():
        st.warning("Portfolio intra-day data could not be retrieved. Please try again later.")
        return

    start = portfolio_intraday.index.min()
    end = portfolio_intraday.index.max()
    if pd.isna(start) or pd.isna(end):
        st.warning("Portfolio intra-day data has invalid date range.")
        return

    # --- FILL MISSING MINUTES ---
    all_minutes = pd.date_range(start=start, end=end, freq="15T")
    portfolio_intraday = portfolio_intraday.reindex(all_minutes).ffill()

    # --- DAILY OHLC FOR CANDLESTICK (RESAMPLE TO 1D) ---
    daily = portfolio_intraday["Total Value"].resample('B').ohlc()
    daily.columns = [col.capitalize() for col in daily.columns]  # Open, High, Low, Close

    # --- EMA LINES ---
    daily[f"EMA{ema1_days}"] = daily["Close"].ewm(span=ema1_days, adjust=False).mean()
    daily[f"EMA{ema2_days}"] = daily["Close"].ewm(span=ema2_days, adjust=False).mean()

    # --- CREATE SUBPLOTS ---
    rows = 2 if show_rsi else 1
    fig = make_subplots(
        rows=rows, cols=1, shared_xaxes=True,
        vertical_spacing=0.08, row_heights=[0.7]+[0.3]*(rows-1)
    )

    # --- PORTFOLIO VALUE ---
    if chart_type == "Line":
        fig.add_trace(go.Scatter(
            x=daily.index,
            y=daily["Close"],
            mode="lines",
            name="Portfolio Value",
            line=dict(color="blue", width=2)
        ), row=1, col=1)
    elif chart_type == "Candlestick":
        fig.add_trace(go.Candlestick(
            x=daily.index,
            open=daily["Open"],
            high=daily["High"],
            low=daily["Low"],
            close=daily["Close"],
            name="Portfolio Value"
        ), row=1, col=1)
    elif chart_type == "Heiken Ashi":
        df_ha = daily.copy()
        df_ha["HA_Close"] = (df_ha["Open"] + df_ha["High"] + df_ha["Low"] + df_ha["Close"]) / 4
        df_ha["HA_Open"] = ((df_ha["Open"].shift(1).fillna(df_ha["Open"].iloc[0]) +
                             df_ha["Close"].shift(1).fillna(df_ha["Close"].iloc[0])) / 2)
        df_ha["HA_High"] = df_ha[["HA_Open", "HA_Close", "High"]].max(axis=1)
        df_ha["HA_Low"] = df_ha[["HA_Open", "HA_Close", "Low"]].min(axis=1)

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
        x=daily.index,
        y=daily[f"EMA{ema1_days}"],
        mode="lines",
        name=f"EMA{ema1_days}",
        line=dict(color="green", width=2)
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=daily.index,
        y=daily[f"EMA{ema2_days}"],
        mode="lines",
        name=f"EMA{ema2_days}",
        line=dict(color="red", width=2)
    ), row=1, col=1)

    # --- RSI PANEL ---
    if show_rsi:
        delta = daily["Close"].diff()
        gain = delta.clip(lower=0)
        loss = -1 * delta.clip(upper=0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        daily["RSI"] = 100 - (100 / (1 + rs))
        fig.add_trace(go.Scatter(
            x=daily.index,
            y=daily["RSI"],
            name="RSI",
            line=dict(color="purple")
        ), row=2, col=1)

    # --- LAYOUT ---
    layout_dragmode = "drawline" if enable_trendline else "zoom"
    fig.update_layout(
        xaxis_rangeslider_visible=False,
        yaxis_title="Portfolio Value ($)",
        dragmode=layout_dragmode,
        height=600,
        margin=dict(t=40, b=40)
    )
    fig.update_yaxes(tickformat=",.0f")
    fig.update_xaxes(tickangle=0, tickformat="%Y-%m-%d")

    st.plotly_chart(fig, use_container_width=True)
