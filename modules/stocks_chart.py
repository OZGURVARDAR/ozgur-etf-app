import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def show():
    st.subheader("📈 Portfolio Interactive Chart (15-min Intra-day)")

    # --- SIDEBAR ---
    chart_type = st.sidebar.selectbox("Portfolio Chart Type", ["Candlestick", "Line", "Heiken Ashi"], index=0)
    ema1_days = st.sidebar.number_input("EMA 1 (Short)", min_value=1, max_value=200, value=50)
    ema2_days = st.sidebar.number_input("EMA 2 (Long)", min_value=1, max_value=200, value=100)
    show_rsi = st.sidebar.checkbox("Show RSI", value=True)
    enable_trendline = st.sidebar.checkbox("Enable Trendline Drawing", value=False)

    SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

    # --- LOAD DATA ---
    @st.cache_data(ttl=600)
    def load_sheet_data():
        df = pd.read_csv(SHEET_URL)
        return df[df["Symbol"] != "CASH"].copy()

    df_stocks = load_sheet_data()
    symbols = df_stocks["Symbol"].unique().tolist()

    if not symbols:
        st.info("No stocks in portfolio.")
        return

    # --- FETCH DATA (60-day limit for 15m interval) ---
    with st.spinner(f'Fetching data for {len(symbols)} symbols...'):
        try:
            # period="60d" 15dk'lık veri için en stabil süredir.
            data = yf.download(symbols, period="60d", interval="15m", group_by='ticker', progress=False)
        except Exception as e:
            st.error(f"Yahoo Finance connection error: {e}")
            return

    if data.empty:
        st.error("No data returned from Yahoo Finance. Try reducing the period or check symbols.")
        return

    # --- CALCULATE PORTFOLIO VALUE ---
    # Multi-index veriyi işle
    portfolio_val = pd.Series(0, index=data.index)
    
    for symbol in symbols:
        try:
            # Eğer birden fazla sembol varsa data[symbol] bir DataFrame'dir
            if len(symbols) > 1:
                close_s = data[symbol]['Close']
            else:
                close_s = data['Close']
            
            qty = df_stocks.loc[df_stocks["Symbol"] == symbol, "Quantity"].sum()
            portfolio_val += close_s.fillna(method='ffill') * qty
        except Exception:
            continue

    # OHLC oluşturma
    df_plot = portfolio_val.resample('15T').ohlc().dropna()

    # Göstergeler
    df_plot[f"EMA1"] = df_plot["close"].ewm(span=ema1_days).mean()
    df_plot[f"EMA2"] = df_plot["close"].ewm(span=ema2_days).mean()

    # RSI Hesabı
    def get_rsi(series, window=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/window).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/window).mean()
        return 100 - (100 / (1 + gain/loss))

    if show_rsi:
        df_plot["RSI"] = get_rsi(df_plot["close"])

    # --- PLOTLY ---
    rows = 2 if show_rsi else 1
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.05)

    if chart_type == "Candlestick":
        fig.add_trace(go.Candlestick(x=df_plot.index, open=df_plot['open'], high=df_plot['high'], low=df_plot['low'], close=df_plot['close'], name="Portfolio"), row=1, col=1)
    elif chart_type == "Heiken Ashi":
        # HA hesaplama mantığı...
        ha_close = (df_plot['open'] + df_plot['high'] + df_plot['low'] + df_plot['close']) / 4
        fig.add_trace(go.Candlestick(x=df_plot.index, open=df_plot['open'], high=df_plot['high'], low=df_plot['low'], close=ha_close, name="HA"), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['close'], name="Price"), row=1, col=1)

    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot["EMA1"], name=f"EMA {ema1_days}"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot["EMA2"], name=f"EMA {ema2_days}"), row=1, col=1)

    if show_rsi:
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot["RSI"], name="RSI", line=dict(color="purple")), row=2, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

    # --- BOŞLUKLARI KALDIRMA ---
    fig.update_xaxes(
        rangebreaks=[
            dict(bounds=["sat", "mon"]), 
            dict(bounds=[16, 9.5], pattern="hour")
        ]
    )

    fig.update_layout(height=700, xaxis_rangeslider_visible=False, dragmode="drawline" if enable_trendline else "zoom")
    st.plotly_chart(fig, use_container_width=True)
