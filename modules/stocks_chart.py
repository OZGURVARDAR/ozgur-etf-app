import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime

def show():
    # --- TRADINGVIEW STİL ---
    up_color, down_color = '#26a69a', '#ef5350'
    
    st.subheader("🛡️ Professional TWR Portfolio Terminal")
    st.info("Bu grafik para giriş/çıkışlarından etkilenmez, sadece strateji performansını (NAV) gösterir.")

    # --- SIDEBAR ---
    chart_mode = st.sidebar.selectbox("Grafik Türü", ["Candlestick", "Heiken Ashi", "Line"])

    SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

    @st.cache_data(ttl=60)
    def load_portfolio():
        df = pd.read_csv(SHEET_URL)
        df['Date'] = pd.to_datetime(df['Date']).dt.normalize()
        # Sadece hisse işlemlerini al
        trades = df[df["Symbol"] != "CASH"].sort_values('Date')
        return trades, trades['Date'].min(), trades['Symbol'].unique().tolist()

    trades, first_date, symbols = load_portfolio()

    # --- VERİ ÇEKME (CANLI & GEÇMİŞ) ---
    with st.spinner('Piyasa verileri ve NAV hesaplanıyor...'):
        # Tüm geçmiş + canlı veri için 'max' ve '1d' kullanıyoruz
        data = yf.download(symbols, start=first_date, interval="1d", group_by='ticker', progress=False)

    # --- TWR (TIME-WEIGHTED RETURN) HESAPLAMA MOTORU ---
    # Bu bölüm, para giriş/çıkışlarını (Cash Flow) performanstan izole eder.
    
    nav_series = [] # Endeks (Başlangıç 1.0)
    current_nav = 1.0
    
    # Hangi gün elimizde ne vardı?
    # holdings = {'NVDA': 10, 'TSLA': 5} gibi
    current_holdings = {sym: 0.0 for sym in symbols}
    
    # Gerçek Portföy Değeri (Son ölçekleme için)
    final_real_equity = 0.0

    # Tarihleri sıralı dön
    all_dates = data.index.sort_values()
    
    for i, date in enumerate(all_dates):
        # 1. ÖNCE PERFORMANS HESAPLA (Dünkü portföy bugün ne yaptı?)
        # Eğer ilk gün değilse ve elimizde hisse varsa hesapla
        daily_return = 0.0
        
        # Dünün kapanış fiyatlarıyla portföy değeri (Maliyet bazı)
        val_yesterday = 0.0
        # Bugünün fiyatlarıyla portföy değeri (Değerleme)
        val_today_open = 0.0
        val_today_high = 0.0
        val_today_low = 0.0
        val_today_close = 0.0
        
        has_holdings = False
        
        for sym, qty in current_holdings.items():
            if qty != 0: # Eksi bakiye (short) veya artı bakiye
                has_holdings = True
                try:
                    # Sembol verisi
                    s_data = data[sym] if len(symbols) > 1 else data
                    
                    # Dünkü Kapanış (veya alım günü maliyet)
                    # Not: Yahoo Finance dataframe'inde bir önceki satırı bulmak karmaşıktır,
                    # bu yüzden "Open" fiyatını referans almak yerine 
                    # "Daily % Change" mantığını kullanacağız.
                    
                    # Basitleştirilmiş TWR:
                    # Bugünün değerini dünkü kapanış fiyatına oranla değil,
                    # Bugünün Open/High/Low/Close değerlerini ağırlıklandır.
                    
                    price_open = s_data['Open'].loc[date]
                    price_high = s_data['High'].loc[date]
                    price_low = s_data['Low'].loc[date]
                    price_close = s_data['Close'].loc[date]
                    
                    # Dünkü kapanış fiyatı (Return hesaplamak için)
                    # Eğer i=0 ise (ilk gün), Open fiyatını baz al
                    if i > 0:
                        prev_date = all_dates[i-1]
                        price_prev = s_data['Close'].loc[prev_date]
                    else:
                        price_prev = s_data['Open'].loc[date] 

                    val_yesterday += qty * price_prev
                    val_today_open += qty * price_open
                    val_today_high += qty * price_high
                    val_today_low += qty * price_low
                    val_today_close += qty * price_close
                    
                except: continue

        # Günlük Performansı Endekse İşle
        # Formül: (Bugünkü Değer / Dünkü Değer)
        if has_holdings and val_yesterday != 0:
            # Günlük değişim çarpanları
            r_open = val_today_open / val_yesterday
            r_high = val_today_high / val_yesterday
            r_low = val_today_low / val_yesterday
            r_close = val_today_close / val_yesterday
            
            # Mumları NAV üzerine inşa et
            nav_open = current_nav * r_open
            nav_high = current_nav * r_high
            nav_low = current_nav * r_low
            nav_close = current_nav * r_close
            
            # Kapanış NAV'ını güncelle
            current_nav = nav_close
            
            nav_series.append({
                'Date': date, 'Open': nav_open, 'High': nav_high, 
                'Low': nav_low, 'Close': nav_close
            })
        elif i == 0:
            # İlk gün başlangıç
            nav_series.append({'Date': date, 'Open': 1.0, 'High': 1.0, 'Low': 1.0, 'Close': 1.0})

        # 2. SONRA İŞLEMLERİ EKLE (Gelecek gün için portföyü güncelle)
        # Bugün yapılan alım/satımlar yarının performansını etkiler, bugünü değil.
        todays_trades = trades[trades['Date'] == date]
        for _, row in todays_trades.iterrows():
            current_holdings[row['Symbol']] += row['Quantity']

    # --- SON DÜZELTME: FİYAT EŞLEME (SCALING) ---
    # Hesapladığımız şey 1.0 ile başlayan soyut bir endeksti.
    # Bunu gerçek paraya çevirmek için:
    # Son Gerçek Değer = (Son Gün Hisseleri * Son Gün Fiyatları)
    
    # 1. Şu anki gerçek portföy değerini hesapla
    real_market_value = 0.0
    last_date = all_dates[-1]
    for sym, qty in current_holdings.items():
        if qty != 0:
            try:
                s_data = data[sym] if len(symbols) > 1 else data
                last_price = s_data['Close'].iloc[-1] # En güncel fiyat
                real_market_value += qty * last_price
            except: continue
            
    # 2. Ölçekleme Çarpanı (Scalar)
    if nav_series:
        last_nav_index = nav_series[-1]['Close']
        if last_nav_index != 0:
            scalar = real_market_value / last_nav_index
        else:
            scalar = 0
            
        # Tüm seriyi bu çarpanla çarp (Back-Adjusted Price)
        df_nav = pd.DataFrame(nav_series)
        df_nav['Open'] *= scalar
        df_nav['High'] *= scalar
        df_nav['Low'] *= scalar
        df_nav['Close'] *= scalar
        df_nav['Date_Str'] = df_nav['Date'].dt.strftime('%d %b %y')
    else:
        st.warning("Görüntülenecek veri yok.")
        return

    # --- DASHBOARD & METRİKLER ---
    final_val = df_nav['Close'].iloc[-1]
    prev_val = df_nav['Close'].iloc[-2] if len(df_nav) > 1 else final_val
    delta = final_val - prev_val
    delta_pct = (delta / prev_val) * 100

    col1, col2 = st.columns([1, 2])
    with col1:
        st.metric("Model Portföy Değeri", f"${final_val:,.2f}", f"{delta_pct:+.2f}%")
    with col2:
        st.caption("ℹ️ Bu grafik, alım/satımlardan (para giriş/çıkışı) etkilenmez. "
                   "Bugünkü portföy büyüklüğünüzün ($) geçmiş performansını simüle eder.")

    # --- GRAFİK ---
    fig = go.Figure()

    if chart_mode == "Candlestick":
        fig.add_trace(go.Candlestick(
            x=df_nav['Date_Str'], open=df_nav['Open'], high=df_nav['High'], low=df_nav['Low'], close=df_nav['Close'],
            increasing_line_color=up_color, decreasing_line_color=down_color,
            increasing_fillcolor=up_color, decreasing_fillcolor=down_color, name="NAV"
        ))
    elif chart_mode == "Heiken Ashi":
        ha_c = (df_nav['Open'] + df_nav['High'] + df_nav['Low'] + df_nav['Close']) / 4
        ha_o = (df_nav['Open'].shift(1) + df_nav['Close'].shift(1)) / 2
        ha_o.iloc[0] = df_nav['Open'].iloc[0]
        fig.add_trace(go.Candlestick(
            x=df_nav['Date_Str'], open=ha_o, high=df_nav['High'], low=df_nav['Low'], close=ha_c,
            increasing_line_color=up_color, decreasing_line_color=down_color, name="HA NAV"
        ))
    else:
        fig.add_trace(go.Scatter(x=df_nav['Date_Str'], y=df_nav['Close'], line=dict(color='#2962FF', width=3), name="NAV Line"))

    fig.update_layout(
        height=700, template="plotly_white",
        yaxis=dict(side="right", tickformat=",.0f", tickprefix="$", gridcolor="#f0f0f0", title="Düzeltilmiş Değer ($)"),
        xaxis=dict(type='category', nticks=15, gridcolor="#f0f0f0"),
        xaxis_rangeslider_visible=False,
        margin=dict(l=0, r=50, t=10, b=10),
        hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True)
