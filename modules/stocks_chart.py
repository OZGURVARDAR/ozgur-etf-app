import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

def show():
    st.subheader("📈 Portfolio Interactive Chart (15-min Intra-day)")

    # --- SIDEBAR SETTINGS ---
    chart_type = st.sidebar.selectbox("Portfolio Chart Type", ["Candlestick", "Line", "Heiken Ashi"])
    ema1_days = st.sidebar.number_input("EMA 1 (Short)", min_value=1, max_value=200, value=50)
    ema2_days = st.sidebar.number_input("EMA 2 (Long)", min_value=1, max_value=200, value=100)
    show_rsi = st.sidebar.checkbox("Show RSI", value=True)
    enable_trendline = st.sidebar.checkbox("Enable Trendline Drawing", value=False)

    # --- GOOGLE SHEETS CSV LINK ---
    SHEET_URL = (
        "https://docs.google.com/spreadsheets/d/"
        "1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"
    )

    # --- LOAD PORTFOLIO DATA ---
    @st.cache_data(ttl=600)  # 10 dakikada bir veriyi yeniler, performansı artırır
    def load_data():
        df_sheets = pd.read_csv(SHEET_URL)
        df_stocks = df_sheets[df_sheets["Symbol"] != "CASH"].copy()
        return df_stocks

    df_stocks = load_data()
    symbols = df_stocks["Symbol"].unique().tolist()

    if not symbols:
        st.info("No stocks in portfolio.")
        return

    # --- FETCH 15-MIN DATA ---
    # 6 ay boyunca 15dk'lık veri çekiyoruz.
    # Not: yfinance bazen 15dk veri için 60 gün sınırı koyabilir, hata alırsan "2mo" yapabilirsin.
    with st.spinner('Fetching market data...'):
        data = yf.download(symbols, period="6mo", interval="15m", progress=False)
    
    if data.empty:
        st.error("Data could not be fetched from Yahoo Finance.")
        return

    # MultiIndex yönetimi (Tek sembol vs Çok sembol)
    close_prices = data['Close']
    if isinstance(close_prices, pd.Series):
        close_prices = close_prices.to_frame(name=symbols[0])

    # --- CALCULATE PORTFOLIO OHLC (15-MIN) ---
    # Portföy değerini her 15 dakikalık bar için hesaplıyoruz
    portfolio_15m = pd.DataFrame(index=close_prices.index)
    portfolio_15m["Value"] = 0
    for symbol in symbols:
        if symbol in close_prices.columns:
            qty = df_stocks.loc[df_stocks["Symbol"] == symbol, "Quantity"].sum()
            portfolio_15m["Value"] += close_prices[symbol] * qty

    # 15 dakikalık veriden OHLC oluşturma
    # Günlük istersen 'B' (iş günü), gün içi 15dk kalsın dersen resample yapmadan devam edebilirsin.
    # Ama "mum" grafik en güzel 1 saatlik veya günlükte görünür. 
    # Burada 15 dakikalık barları koruyoruz:
    df_plot = portfolio_15m["Value"].resample('15T').ohlc().dropna()

    # --- INDICATORS ---
    # EMA (Kapanış fiyatı üzerinden)
    df_plot[f"EMA{ema1_days}"] = df_plot["close"].ewm(span=ema1_days, adjust=False).mean()
    df_plot[f"EMA{ema2_days}"] = df_plot["close"].ewm(span=ema2_days, adjust=False).mean()

    # RSI (Wilder's Smoothing - Daha doğru hesaplama)
    def calculate_rsi(series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0))
        loss = (-delta.where(delta < 0, 0))
        avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    if show_rsi:
        df_plot["RSI"] = calculate_rsi(df_plot["close"])

    # --- PLOTLY CHART ---
    rows = 2 if show_rsi else 1
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=[0.7, 0.3] if show_rsi else [1])

    # Chart Type Logic
    if chart_type == "Candlestick":
        fig.add_trace(go.Candlestick(
            x=df_plot.index, open=df_plot['open'], high=df_plot['high'],
            low=df_plot['low'], close=df_plot['close'], name="Portfolio"
        ), row=1, col=1)
    elif chart_type == "Heiken Ashi":
        ha_close = (df_plot['open'] + df_plot['high'] + df_plot['low'] + df_plot['close']) / 4
        ha_open = (df_plot['open'].shift(1) + df_plot['close'].shift(1)) / 2
        ha_open.iloc[0] = df_plot['open'].iloc[0]
        ha_high = df_plot[['high', 'open', 'close']].max(axis=1)
        ha_low = df_plot[['low', 'open', 'close']].min(axis=1)
        fig.add_trace(go.Candlestick(
            x=df_plot.index, open=ha_open, high=ha_high, low=ha_low, close=ha_close, name="Heiken Ashi"
        ), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['close'], name="Value", line=dict(color="#1f77b4")), row=1, col=1)

    # Moving Averages
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot[f"EMA{ema1_days}"], name=f"EMA {ema1_days}", line=dict(width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot[f"EMA{ema2_days}"], name=f"EMA {ema2_days}", line=dict(width=1.5)), row=1, col=1)

    # RSI
    if show_rsi:
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot["RSI"], name="RSI", line=dict(color="purple")), row=2, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

    # --- BOŞLUKLARI KALDIRMA (AMERİKAN BORSASI SAATLERİ) ---
    # Hafta sonlarını (Cumartesi-Pazar) ve işlem saatleri dışını (16:00 - 09:30) gizler
    fig.update_xaxes(
        rangebreaks=[
            dict(bounds=["sat", "mon"]), # Cumartesi sabahından Pazartesi sabahına kadar kapat
            dict(bounds=[16, 9.5], pattern="hour"), # Akşam 16:00'dan sabah 09:30'a kadar kapat
            # Not: Resmi tatilleri (Noel, 1 Ocak vb.) yfinance verisi zaten boş getirdiği için 
            # yukarıdaki saat kuralı onları da büyük oranda kapsar.
        ]
    )

    fig.update_layout(
        height=800,
        xaxis_rangeslider_visible=False,
        dragmode="drawline" if enable_trendline else "zoom",
        template="plotly_white",
        margin=dict(l=50, r=50, t=30, b=30)
    )

    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    show()
