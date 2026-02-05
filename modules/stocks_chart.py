import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime
import pytz

def show():
    # --- AYARLAR ---
    up_color, down_color = '#26a69a', '#ef5350'
    st.subheader("🚀 V3: Ultimate TWR Portfolio Terminal")
    
    # Sağ üst köşeye son güncelleme saati (ABD ve TSİ)
    tz_ny = pytz.timezone('America/New_York')
    tz_tr = pytz.timezone('Europe/Istanbul')
    now_ny = datetime.now(tz_ny).strftime('%H:%M')
    now_tr = datetime.now(tz_tr).strftime('%H:%M')
    
    col_info, col_btn = st.columns([3, 1])
    with col_info:
        st.caption(f"ℹ️ **Durum:** Bu grafik para giriş/çıkışlarını (Alım/Satım) yok sayar. Sadece strateji başarısını izler. | 🇺🇸 NY: {now_ny} | 🇹🇷 TR: {now_tr}")
    with col_btn:
        # Canlı veriyi tazelemek için buton
        if st.button("🔄 Verileri Güncelle"):
            st.cache_data.clear() # Cache'i temizle ki taze veri gelsin

    # --- GOOGLE SHEETS VERİSİ ---
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

    @st.cache_data(ttl=60) # 60 saniyelik cache (Canlı veri için kısa tutuldu)
    def load_portfolio():
        df = pd.read_csv(SHEET_URL)
        df['Date'] = pd.to_datetime(df['Date']).dt.normalize()
        # Sadece hisse işlemleri (Nakit yok)
        trades = df[df["Symbol"] != "CASH"].sort_values('Date')
        return trades, trades['Date'].min(), trades['Symbol'].unique().tolist()

    trades, first_date, symbols = load_portfolio()

    # --- CANLI PİYASA VERİSİ ---
    with st.spinner('Borsa verileri alınıyor (Canlı)...'):
        # period='max' ve interval='1d' borsa açıkken bugünün "yürüyen" mumunu da getirir.
        data = yf.download(symbols, start=first_date, interval="1d", group_by='ticker', progress=False)
        
        # Veri temizliği: Hafta sonları veya tatillerden gelen NaN satırlarını temizle
        # Ancak en son satırı (bugünü) korumaya dikkat et.
        data = data.dropna(how='all') 

    # --- TWR MOTORU (ALIM/SATIM ETKİSİZLEŞTİRME) ---
    
    nav_series = []
    current_nav = 1.0 # Endeks başlangıcı
    
    # Hangi hissede kaç adet var?
    current_holdings = {sym: 0.0 for sym in symbols}
    
    # Tarih listesi
    all_dates = data.index.sort_values()
    
    # DÖNGÜ
    for i, date in enumerate(all_dates):
        # 1. ÖNCE PERFORMANS (Dünkü portföy bugün ne yaptı?)
        # Alım/Satım yapmadan ÖNCEKİ portföyün değer değişimi hesaplanır.
        
        val_start = 0.0 # Gün başı değeri (Dünkü portföy, Dünkü fiyat)
        val_end = 0.0   # Gün sonu değeri (Dünkü portföy, Bugünkü fiyat)
        
        # Gün içi hareket simülasyonu (OHLC Mumu için)
        val_high = 0.0
        val_low = 0.0
        val_open = 0.0
        
        has_assets = False
        
        for sym, qty in current_holdings.items():
            if qty != 0:
                has_assets = True
                try:
                    s_data = data[sym] if len(symbols) > 1 else data
                    
                    # Bugünün Fiyatları
                    p_close = s_data['Close'].loc[date]
                    p_open = s_data['Open'].loc[date]
                    p_high = s_data['High'].loc[date]
                    p_low = s_data['Low'].loc[date]
                    
                    # Dünün Fiyatı (Referans)
                    if i > 0:
                        p_prev = s_data['Close'].loc[all_dates[i-1]]
                    else:
                        p_prev = p_open # İlk gün açılış fiyatı
                    
                    # Hesaplama (Alım/Satım öncesi mevcut varlıklarla)
                    val_start += qty * p_prev
                    val_end += qty * p_close
                    
                    val_open += qty * p_open
                    val_high += qty * p_high
                    val_low += qty * p_low
                    
                except: continue
        
        # 2. NAV GÜNCELLEME
        if has_assets and val_start > 0:
            # Günlük Getiri Çarpanı
            daily_return = val_end / val_start
            
            # Mum fitillerini oransal hesapla
            nav_open = current_nav * (val_open / val_start)
            nav_high = current_nav * (val_high / val_start)
            nav_low = current_nav * (val_low / val_start)
            nav_close = current_nav * daily_return
            
            nav_series.append({
                'Date': date, 'Open': nav_open, 'High': nav_high, 
                'Low': nav_low, 'Close': nav_close
            })
            current_nav = nav_close # Yeni baz
            
        elif not has_assets:
            # Varlık yoksa NAV sabit (Yatay çizgi)
            nav_series.append({
                'Date': date, 'Open': current_nav, 'High': current_nav, 
                'Low': current_nav, 'Close': current_nav
            })
            
        # 3. ŞİMDİ ALIM/SATIMLARI İŞLE (Yarına hazırlık)
        # Bu işlem NAV'ı etkilemez, sadece yarınki 'qty' miktarını değiştirir.
        todays_trades = trades[trades['Date'] == date]
        for _, row in todays_trades.iterrows():
            sym = row['Symbol']
            qty = row['Quantity']
            current_holdings[sym] = current_holdings.get(sym, 0) + qty

    # --- ÖLÇEKLEME (SCALING) ---
    # Endeksi (NAV) Gerçek Dolara Çevirme
    
    # 1. Şu anki portföyün gerçek piyasa değerini bul
    current_market_value = 0.0
    # En son geçerli fiyatları al (Bugün)
    last_idx = all_dates[-1]
    
    for sym, qty in current_holdings.items():
        if qty != 0:
            try:
                s_data = data[sym] if len(symbols) > 1 else data
                last_price = s_data['Close'].iloc[-1]
                current_market_value += qty * last_price
            except: pass
            
    # 2. Ölçekleme Katsayısı
    if nav_series and nav_series[-1]['Close'] > 0:
        scalar = current_market_value / nav_series[-1]['Close']
    else:
        scalar = 1.0

    df_nav = pd.DataFrame(nav_series)
    # Tüm NAV serisini gerçek dolar değerine ölçekle
    df_nav['Open'] *= scalar
    df_nav['High'] *= scalar
    df_nav['Low'] *= scalar
    df_nav['Close'] *= scalar
    df_nav['Date_Str'] = df_nav['Date'].dt.strftime('%d %b %y')

    # --- DASHBOARD ---
    # Son günün mumu
    last_c = df_nav['Close'].iloc[-1]
    prev_c = df_nav['Close'].iloc[-2] if len(df_nav) > 1 else last_c
    
    diff = last_c - prev_c
    diff_pct = (diff / prev_c) * 100
    
    st.metric("TWR Portföy Değeri (Düzeltilmiş)", f"${last_c:,.2f}", f"{diff_pct:+.2f}%")

    # --- GRAFİK ---
    fig = go.Figure(data=[go.Candlestick(
        x=df_nav['Date_Str'],
        open=df_nav['Open'], high=df_nav['High'], low=df_nav['Low'], close=df_nav['Close'],
        increasing_line_color=up_color, decreasing_line_color=down_color, name="Portfolio"
    )])

    # Canlı Mum Efekti için son muma özel not
    if now_ny < "16:00": # Piyasa açıksa
        fig.layout.title = "🟢 PİYASA AÇIK - Canlı Fiyatlama"
    else:
        fig.layout.title = "🔴 PİYASA KAPALI - Son Kapanış"

    fig.update_layout(
        height=650, template="plotly_white",
        yaxis=dict(side="right", tickformat=",.0f", tickprefix="$", gridcolor="#f0f0f0"),
        xaxis=dict(type='category', nticks=10, gridcolor="#f0f0f0"),
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        margin=dict(l=0, r=50, t=30, b=10)
    )

    st.plotly_chart(fig, use_container_width=True)
