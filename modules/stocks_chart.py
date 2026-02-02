import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go

def show():
    st.subheader("📊 Portfolio Performance Index (100 Base)")

    # --- SIDEBAR ---
    chart_mode = st.sidebar.selectbox("Grafik Türü", ["Line", "Candlestick", "Heiken Ashi"])
    
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

    @st.cache_data(ttl=300)
    def get_data():
        df = pd.read_csv(SHEET_URL)
        df['Date'] = pd.to_datetime(df['Date']).dt.normalize()
        # Sadece hisseleri al
        trades = df[df["Symbol"] != "CASH"].sort_values('Date').copy()
        return trades

    trades = get_data()
    symbols = trades["Symbol"].unique().tolist()
    # İlk gerçek alım tarihi: 18.11.2025
    start_date = trades['Date'].min()

    # --- VERİ ÇEKME ---
    with st.spinner('Piyasa verileri senkronize ediliyor...'):
        data = yf.download(symbols, start=start_date, interval="1d", group_by='ticker', progress=False)

    # --- PORTFÖYÜN GÜNLÜK DEĞERİ ---
    daily_summary = []
    
    # Yahoo'dan gelen tüm işlem günlerini tara
    for current_date in data.index:
        # O tarihe kadar elimizde olan hisseleri ve toplam maliyeti bul
        current_trades = trades[trades['Date'] <= current_date]
        
        total_market_value = 0.0
        total_invested_capital = 0.0 # O güne kadar yatırılan toplam ana para
        
        for sym in symbols:
            s_trades = current_trades[current_trades['Symbol'] == sym]
            if not s_trades.empty:
                qty = s_trades['Quantity'].sum()
                cost = (s_trades['Quantity'] * s_trades['Price']).sum()
                
                try:
                    price_col = data[sym]['Close'] if len(symbols) > 1 else data['Close']
                    current_price = price_col.asof(current_date) # O gün fiyat yoksa son fiyatı al
                    
                    total_market_value += qty * current_price
                    total_invested_capital += cost
                except: continue
        
        if total_invested_capital > 0:
            # Kar/Zarar Oranı üzerinden Endeksle
            # (Piyasa Değeri / Maliyet) * 100
            # Bu formül direkt olarak %11.04 kârı -> 111.04 Endeks puanı yapar.
            nav_index = (total_market_value / total_invested_capital) * 100
            daily_summary.append({'Date': current_date, 'NAV': nav_index})

    df_nav = pd.DataFrame(daily_summary).set_index('Date')
    # Günlük mumlara çevir
    df_ohlc = df_nav['NAV'].resample('B').ohlc().dropna()

    # --- GÖRSELLEŞTİRME ---
    fig = go.Figure()
    x_axis = df_ohlc.index.strftime('%d %b %y')

    if chart_mode == "Line":
        fig.add_trace(go.Scatter(x=x_axis, y=df_ohlc['close'], line=dict(color='#00E676', width=3), name="Portfolio Performance"))
    else:
        fig.add_trace(go.Candlestick(x=x_axis, open=df_ohlc['open'], high=df_ohlc['high'], low=df_ohlc['low'], close=df_ohlc['close'], name="Portfolio NAV"))

    # Y-Ekseni Ayarı: 19k-20k yerine gerçek rakamları göster
    fig.update_yaxes(title_text="Performance Index (Base 100)", tickformat=".2f")
    fig.update_xaxes(type='category', nticks=15)
    
    fig.update_layout(
        height=600,
        template="plotly_dark", # TradingView tarzı koyu tema
        xaxis_rangeslider_visible=False,
        margin=dict(l=50, r=20, t=20, b=20)
    )

    st.plotly_chart(fig, use_container_width=True)

    # Özet Metrikler
    last_val = df_ohlc['close'].iloc[-1]
    st.metric("Güncel Portföy Başarısı", f"{last_val:.2f} Puan", f"%{last_val-100:.2f} Toplam Getiri")
