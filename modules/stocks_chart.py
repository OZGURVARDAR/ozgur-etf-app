import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def show():
    st.subheader("📈 Portfolio Interactive Chart (Continuous 15-min)")

    # --- SIDEBAR ---
    chart_type = st.sidebar.selectbox("Portfolio Chart Type", ["Candlestick", "Heiken Ashi", "Line"])
    ema1_days = st.sidebar.number_input("EMA 1 (Short)", min_value=1, max_value=200, value=50)
    ema2_days = st.sidebar.number_input("EMA 2 (Long)", min_value=1, max_value=200, value=100)
    show_rsi = st.sidebar.checkbox("Show RSI", value=True)
    enable_trendline = st.sidebar.checkbox("Enable Trendline Drawing", value=False)

    SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

    @st.cache_data(ttl=600)
    def load_sheet_data():
        df = pd.read_csv(SHEET_URL)
        return df[df["Symbol"] != "CASH"].copy()

    df_stocks = load_sheet_data()
    symbols = df_stocks["Symbol"].unique().tolist()

    if not symbols:
        st.info("No stocks in portfolio.")
        return

    # --- DATA FETCHING (60-day limit for 15m) ---
    with st.spinner('Market data is loading...'):
        try:
            # 15 dakikalık veride kopukluk olmaması için 60 gün idealdir
            data = yf.download(symbols, period="60d", interval="15m", group_by='ticker', progress=False)
        except Exception as e:
            st.error(f"Error: {e}")
            return

    if data.empty:
        st.warning("Could not fetch data. Please check your symbols.")
        return

    # --- PORTFOLIO CALCULATION ---
    portfolio_val = pd.Series(0, index=data.index)
    for symbol in symbols:
        try:
            if len(symbols) > 1:
                s_data = data[symbol]['Close']
            else:
                s_data = data['Close']
            
            qty = df_stocks.loc[df_stocks["Symbol"] == symbol, "Quantity"].sum()
            # Fiyatlardaki anlık boşlukları doldurarak ilerle (ffill)
            portfolio_val += s_data.ffill() * qty
        except:
            continue

    # OHLC Verisine dönüştür ve eksik (NaN) satırları temizle
    df_plot = portfolio_val.resample('15T').ohlc().dropna()

    # --- INDICATORS ---
    # EMA Hesaplama (Veri akışı üzerinden)
    df_plot["EMA1"] = df_plot["close"].ewm(span=ema1_days, adjust=False).mean()
    df_plot["EMA2"] = df_plot["close"].ewm(span=ema2_days, adjust=False).mean()

    # RSI (Wilder's Smoothing)
    def calc_rsi(s, n=14):
        delta = s.diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        ema_up = up.ewm(com=n-1, adjust=False).mean()
        ema_down = down.ewm(com=n-1, adjust=False).mean()
        rs = ema_up / ema_down
        return 100 - (100 / (1 + rs))

    if show_rsi:
        df_plot["RSI"] = calc_rsi(df_plot["close"])

    # --- CHARTING ---
    rows = 2 if show_rsi else 1
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.03, row_heights=[0.7, 0.3] if show_rsi else [1])

    # Heiken Ashi veya Candlestick
    if chart_type == "Heiken Ashi":
        df_ha = df_plot.copy()
        df_ha['close'] = (df_plot['open'] + df_plot['high'] + df_plot['low'] + df_plot['close']) / 4
        # HA Open hesaplaması (vektörize edilmiş)
        ha_open = [(df_plot['open'].iloc[0] + df_plot['close'].iloc[0]) / 2]
        for i in range(1, len(df_plot)):
            ha_open.append((ha_open[i-1] + df_ha['close'].iloc[i-1]) / 2)
        df_ha['open'] = ha_open
        df_ha['high'] = df_ha[['open', 'close', 'high']].max(axis=1)
        df_ha['low'] = df_ha[['open', 'close', 'low']].min(axis=1)
        
        fig.add_trace(go.Candlestick(x=df_ha.index, open=df_ha['open'], high=df_ha['high'], 
                                     low=df_ha['low'], close=df_ha['close'], name="Heiken Ashi"), row=1, col=1)
    elif chart_type == "Candlestick":
        fig.add_trace(go.Candlestick(x=df_plot.index, open=df_plot['open'], high=df_plot['high'], 
                                     low=df_plot['low'], close=df_plot['close'], name="Portfolio"), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['close'], name="Portfolio Value", line=dict(color="#2962FF")), row=1, col=1)

    # EMA Lines
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot["EMA1"], name=f"EMA {ema1_days}", line=dict(color="#FF9800", width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot["EMA2"], name=f"EMA {ema2_days}", line=dict(color="#4CAF50", width=1.5)), row=1, col=1)

    if show_rsi:
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot["RSI"], name="RSI", line=dict(color="#7E57C2")), row=2, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="rgba(255,0,0,0.5)", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="rgba(0,255,0,0.5)", row=2, col=1)

    # --- BOŞLUKLARI KALDIRMA (AMERİKAN BORSASI OPTİMİZASYONU) ---
    # Bu ayar geceleri ve hafta sonlarını görselden tamamen siler.
    fig.update_xaxes(
        rangebreaks=[
            dict(bounds=["sat", "mon"]), # Hafta sonlarını kaldır
            dict(bounds=[16, 9.5], pattern="hour"), # 16:00 - 09:30 arası işlem olmayan saatleri kaldır
        ]
    )

    fig.update_layout(
        height=800,
        xaxis_rangeslider_visible=False,
        template="plotly_white",
        dragmode="drawline" if enable_trendline else "zoom",
        margin=dict(l=10, r=10, t=20, b=20)
    )
    
    st.plotly_chart(fig, use_container_width=True)
