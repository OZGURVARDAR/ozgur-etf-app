import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def show():
    st.subheader("📈 Portfolio Daily OHLC Chart")

    # --- SIDEBAR ---
    chart_type = st.sidebar.selectbox("Portfolio Chart Type", ["Candlestick", "Heiken Ashi", "Line"])
    ema1_days = st.sidebar.number_input("EMA 1 (Short)", min_value=1, max_value=200, value=20) # Günlük için 20 idealdir
    ema2_days = st.sidebar.number_input("EMA 2 (Long)", min_value=1, max_value=200, value=50)  # Günlük için 50 idealdir
    show_rsi = st.sidebar.checkbox("Show RSI", value=True)

    SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

    @st.cache_data(ttl=600)
    def load_data():
        df = pd.read_csv(SHEET_URL)
        return df[df["Symbol"] != "CASH"].copy()

    df_stocks = load_data()
    symbols = df_stocks["Symbol"].unique().tolist()

    if not symbols:
        st.info("No stocks found in portfolio.")
        return

    # --- DATA FETCHING ---
    with st.spinner('Günlük portföy verileri hazırlanıyor...'):
        try:
            # Günlük mumlarda gün içi volatiliteyi görmek için 15dk veri çekip günlük resample yapacağız
            # 15dk veri sınırı olan 59 günü kullanıyoruz. 
            data = yf.download(symbols, period="59d", interval="15m", group_by='ticker', progress=False)
        except Exception as e:
            st.error(f"Veri çekme hatası: {e}")
            return

    # --- PORTFOLIO CALCULATION ---
    portfolio_val = pd.Series(0.0, index=data.index)
    for symbol in symbols:
        try:
            close_s = data[symbol]['Close'] if len(symbols) > 1 else data['Close']
            qty = df_stocks.loc[df_stocks["Symbol"] == symbol, "Quantity"].sum()
            portfolio_val += close_s.ffill().fillna(0) * qty
        except: continue

    # --- RESAMPLE TO DAILY OHLC ---
    # 'B' iş günlerini ifade eder, hafta sonlarını otomatik gruplar
    df_daily = portfolio_val.resample('B').ohlc().dropna()

    # --- INDICATORS (GÜNLÜK BAZDA) ---
    df_daily["EMA1"] = df_daily["close"].ewm(span=ema1_days, adjust=False).mean()
    df_daily["EMA2"] = df_daily["close"].ewm(span=ema2_days, adjust=False).mean()

    if show_rsi:
        delta = df_daily["close"].diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        df_daily["RSI"] = 100 - (100 / (1 + (gain/loss)))

    # X ekseni etiketi (Sadece Tarih)
    df_daily['date_label'] = df_daily.index.strftime('%Y-%m-%d')

    # --- CHARTING ---
    rows = 2 if show_rsi else 1
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3] if show_rsi else [1])

    if chart_type == "Candlestick":
        fig.add_trace(go.Candlestick(x=df_daily['date_label'], open=df_daily['open'], high=df_daily['high'], 
                                     low=df_daily['low'], close=df_daily['close'], name="Daily Portfolio"), row=1, col=1)
    elif chart_type == "Heiken Ashi":
        ha_c = (df_daily['open'] + df_daily['high'] + df_daily['low'] + df_daily['close']) / 4
        ha_o = (df_daily['open'].shift(1) + df_daily['close'].shift(1)) / 2
        ha_o.iloc[0] = df_daily['open'].iloc[0]
        fig.add_trace(go.Candlestick(x=df_daily['date_label'], open=ha_o, high=df_daily['high'], 
                                     low=df_daily['low'], close=ha_c, name="HA Daily"), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(x=df_daily['date_label'], y=df_daily['close'], name="Close Price", line=dict(color='#2962FF')), row=1, col=1)

    # Göstergeler
    fig.add_trace(go.Scatter(x=df_daily['date_label'], y=df_daily["EMA1"], name=f"EMA {ema1_days}", line=dict(color='orange')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_daily['date_label'], y=df_daily["EMA2"], name=f"EMA {ema2_days}", line=dict(color='blue')), row=1, col=1)

    if show_rsi:
        fig.add_trace(go.Scatter(x=df_daily['date_label'], y=df_daily["RSI"], name="RSI", line=dict(color='purple')), row=2, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

    # --- FORMATTING ---
    fig.update_xaxes(type='category', nticks=15) # Günlük görünümde boşluksuz yapı
    fig.update_layout(height=700, xaxis_rangeslider_visible=False, template="plotly_white")
    
    st.plotly_chart(fig, use_container_width=True)
