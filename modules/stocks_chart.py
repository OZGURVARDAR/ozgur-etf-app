import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def show():
    # --- CSS ile TradingView Benzeri Stil ---
    st.markdown("""
        <style>
        .price-delta-up { color: #00897b; font-size: 20px; font-weight: bold; }
        .price-delta-down { color: #ff5252; font-size: 20px; font-weight: bold; }
        .price-main { font-size: 32px; font-weight: bold; }
        </style>
    """, unsafe_allow_html=True)

    SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

    @st.cache_data(ttl=300)
    def load_data():
        df = pd.read_csv(SHEET_URL)
        df['Date'] = pd.to_datetime(df['Date']).dt.normalize()
        return df[df["Symbol"] != "CASH"].sort_values('Date')

    trades = load_data()
    symbols = trades["Symbol"].unique().tolist()
    first_date = trades['Date'].min()

    with st.spinner('Fiyatlar senkronize ediliyor...'):
        data = yf.download(symbols, start=first_date, interval="1d", group_by='ticker', progress=False)

    # --- PORTFÖY DEĞERİ HESAPLAMA ---
    daily_vals = []
    for date in data.index:
        current_mkt_val = 0
        past_trades = trades[trades['Date'] <= date]
        for sym in symbols:
            s_trades = past_trades[past_trades['Symbol'] == sym]
            if not s_trades.empty:
                qty = s_trades['Quantity'].sum()
                try:
                    price_col = data[sym]['Close'] if len(symbols) > 1 else data['Close']
                    price = price_col.asof(date)
                    current_mkt_val += qty * price
                except: continue
        if current_mkt_val > 0:
            daily_vals.append({'Date': date, 'Value': current_mkt_val})

    df_plot = pd.DataFrame(daily_vals).set_index('Date')
    df_ohlc = df_plot['Value'].resample('B').ohlc().dropna()

    # --- SON VERİLERİ AL (TradingView Alt Bilgi Paneli İçin) ---
    current_val = df_ohlc['close'].iloc[-1]
    prev_val = df_ohlc['close'].iloc[-2]
    delta_val = current_val - prev_val
    delta_pct = (delta_val / prev_val) * 100
    color_class = "price-delta-up" if delta_val >= 0 else "price-delta-down"
    delta_sign = "+" if delta_val >= 0 else ""

    # --- ÜST BİLGİ PANELİ ---
    st.subheader("📊 Portfolio Real-Time Terminal")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown(f'<div class="price-main">{current_val:,.2f} <span style="font-size:18px; color:gray;">USD</span></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="{color_class}">{delta_sign}{delta_val:,.2f} ({delta_sign}{delta_pct:.2f}%) <span style="font-size:14px; color:gray;">Today</span></div>', unsafe_allow_html=True)

    # --- GRAFİK ---
    chart_mode = st.sidebar.selectbox("Grafik Türü", ["Candlestick", "Heiken Ashi", "Line"])
    x_axis = df_ohlc.index.strftime('%d %b %y')

    fig = go.Figure()

    if chart_mode == "Candlestick":
        fig.add_trace(go.Candlestick(x=x_axis, open=df_ohlc['open'], high=df_ohlc['high'], low=df_ohlc['low'], close=df_ohlc['close'], name="Value"))
    elif chart_mode == "Heiken Ashi":
        ha_c = (df_ohlc['open'] + df_ohlc['high'] + df_ohlc['low'] + df_ohlc['close']) / 4
        ha_o = (df_ohlc['open'].shift(1) + df_ohlc['close'].shift(1)) / 2
        ha_o.iloc[0] = df_ohlc['open'].iloc[0]
        fig.add_trace(go.Candlestick(x=x_axis, open=ha_o, high=df_ohlc['high'], low=df_ohlc['low'], close=ha_c, name="HA Value"))
    else:
        fig.add_trace(go.Scatter(x=x_axis, y=df_ohlc['close'], line=dict(color='#2962FF', width=3), fill='tozeroy', name="Value"))

    # --- FORMATLAMA ---
    fig.update_layout(
        height=600,
        template="plotly_white",
        xaxis_rangeslider_visible=False,
        yaxis=dict(
            side="right", # TradingView gibi fiyat ekseni sağda
            title="Portfolio Value ($)",
            tickformat=",.0f", # 20,000 şeklinde gösterim
            gridcolor="#f0f0f0"
        ),
        xaxis=dict(type='category', nticks=12, gridcolor="#f0f0f0"),
        margin=dict(l=0, r=50, t=10, b=10)
    )

    st.plotly_chart(fig, use_container_width=True)
