import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime

def show():
    # --- TRADINGVIEW RENK VE STİL ---
    up_color, down_color = '#26a69a', '#ef5350'
    
    st.subheader("🚀 Versiyon 2: Moving Daily Candle Terminal")

    # --- SIDEBAR: KONTROL PANELİ ---
    chart_mode = st.sidebar.selectbox("Grafik Türü", ["Candlestick", "Heiken Ashi", "Line"])
    refresh_rate = st.sidebar.slider("Yenileme Hızı (Dakika)", 5, 60, 15)
    
    # Otomatik Yenileme Mekanizması
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = datetime.now()
    
    st.sidebar.info(f"Son Güncelleme: {st.session_state.last_refresh.strftime('%H:%M:%S')}")

    SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

    @st.cache_data(ttl=60) # Veriyi kısa süreli cache'le
    def load_portfolio():
        df = pd.read_csv(SHEET_URL)
        df['Date'] = pd.to_datetime(df['Date']).dt.normalize()
        trades = df[df["Symbol"] != "CASH"].sort_values('Date')
        return trades, trades['Date'].min(), trades['Symbol'].unique().tolist()

    trades, first_date, symbols = load_portfolio()

    # --- CANLI VERİ ÇEKME ---
    # Not: yf.download(interval="1d") borsa açıkken "canlı" mumu da getirir.
    with st.spinner('Piyasa verileri anlık olarak çekiliyor...'):
        # Periodu max tutuyoruz ama başlangıcı ilk işlemine sabitliyoruz
        data = yf.download(symbols, start=first_date, interval="1d", group_by='ticker', progress=False)

    # --- MOVING OHLC HESAPLAMA ---
    ohlc_records = []
    for date in data.index:
        past_trades = trades[trades['Date'] <= date]
        if past_trades.empty: continue

        o_val = h_val = l_val = c_val = 0
        for sym in symbols:
            qty = past_trades[past_trades['Symbol'] == sym]['Quantity'].sum()
            if qty > 0:
                try:
                    s = data[sym].loc[date] if len(symbols) > 1 else data.loc[date]
                    o_val += qty * s['Open']
                    h_val += qty * s['High']
                    l_val += qty * s['Low']
                    c_val += qty * s['Close']
                except: continue
        
        if c_val > 0:
            ohlc_records.append({'Date': date, 'Open': o_val, 'High': h_val, 'Low': l_val, 'Close': c_val})

    df = pd.DataFrame(ohlc_records)
    df['Date_Str'] = df['Date'].dt.strftime('%d %b %y')

    # --- CANLI DASHBOARD ---
    current_p = df['Close'].iloc[-1]
    prev_p = df['Close'].iloc[-2]
    diff = current_p - prev_p
    pct = (diff / prev_p) * 100
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.metric("Portföy Değeri", f"${current_p:,.2f}", f"{pct:+.2f}%")
    with col2:
        status = "Borsa Açık - Canlı Mum Aktif" if datetime.now().hour < 23 else "Borsa Kapalı - Veri Sabit"
        st.write(f"ℹ️ **Durum:** {status}")

    # --- GRAFİK ---
    fig = go.Figure()
    
    if chart_mode == "Candlestick":
        fig.add_trace(go.Candlestick(
            x=df['Date_Str'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
            increasing_line_color=up_color, decreasing_line_color=down_color,
            increasing_fillcolor=up_color, decreasing_fillcolor=down_color, name="Live Portfolio"
        ))
    elif chart_mode == "Heiken Ashi":
        # Heiken Ashi Hesaplama (Canlı veriyle beraber güncellenir)
        ha_c = (df['Open'] + df['High'] + df['Low'] + df['Close']) / 4
        ha_o = (df['Open'].shift(1) + df['Close'].shift(1)) / 2
        ha_o.iloc[0] = df['Open'].iloc[0]
        fig.add_trace(go.Candlestick(
            x=df['Date_Str'], open=ha_o, high=df['High'], low=df['Low'], close=ha_c,
            increasing_line_color=up_color, decreasing_line_color=down_color, name="HA Live"
        ))
    else:
        fig.add_trace(go.Scatter(x=df['Date_Str'], y=df['Close'], line=dict(color='#2962FF', width=3), name="Value"))

    fig.update_layout(
        height=700, template="plotly_white",
        yaxis=dict(side="right", tickformat=",.0f", tickprefix="$", gridcolor="#f0f0f0"),
        xaxis=dict(type='category', nticks=15, gridcolor="#f0f0f0"),
        xaxis_rangeslider_visible=False,
        margin=dict(l=0, r=50, t=10, b=10),
        hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True)

    # Otomatik yenileme için küçük bir ipucu:
    # Gerçek canlı yenileme için st_autorefresh kütüphanesi gerekebilir.
    # Ancak Streamlit'te sayfada herhangi bir butona basıldığında veya 
    # tarayıcı sekmesi aktifleştiğinde yf.download en güncel "yürüyen" mumu çekecektir.
