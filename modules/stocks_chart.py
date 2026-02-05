import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go

def show():
    # --- AYARLAR ---
    START_NAV = 100.0 # Fonumuzun açılış fiyatı (Baz Puan)
    up_color, down_color = '#26a69a', '#ef5350'

    st.subheader("🛡️ TWR Performance Engine (Satıştan Etkilenmez)")
    st.info("Bu grafik para giriş/çıkışlarını (Nakit Akışı) yok sayar. Sadece stratejinizin başarısını (Birim Fiyat) gösterir.")

    # --- VERİ YÜKLEME ---
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"
    
    @st.cache_data(ttl=60)
    def load_data():
        df = pd.read_csv(SHEET_URL)
        df['Date'] = pd.to_datetime(df['Date']).dt.normalize()
        # Sadece hisse işlemleri
        trades = df[df["Symbol"] != "CASH"].sort_values('Date')
        return trades

    trades = load_data()
    symbols = trades["Symbol"].unique().tolist()
    
    if not symbols:
        st.warning("Henüz hisse işlemi yok.")
        return

    # İlk işlem tarihi
    start_date = trades['Date'].min()

    # --- PİYASA VERİLERİ ---
    with st.spinner('Piyasa verileri işleniyor...'):
        # Tüm geçmiş veriyi çek
        data = yf.download(symbols, start=start_date, interval="1d", group_by='ticker', progress=False)

    # --- UNITIZATION MOTORU (FON MANTIĞI) ---
    # Mantık: Günlük getiriyi hesapla ve zincirleme ekle. 
    # Alım/Satım işlemleri sadece 'holding' miktarını değiştirir, getiriyi bozmaz.
    
    nav_history = []
    current_nav = START_NAV
    
    # Hangi hissede kaç adet var?
    current_holdings = {sym: 0.0 for sym in symbols}
    
    # Tarih Döngüsü
    all_dates = data.index.sort_values()
    
    for i, date in enumerate(all_dates):
        # 1. GÜNLÜK PERFORMANSI HESAPLA (Dünden Bugüne)
        # Formül: (Bugünkü Kapanış Değeri) / (Dünkü Kapanış Değeri)
        
        portfolio_val_start = 0.0 # Gün başı değeri (Dünkü fiyatlarla)
        portfolio_val_end = 0.0   # Gün sonu değeri (Bugünkü fiyatlarla)
        
        has_assets = False
        
        for sym, qty in current_holdings.items():
            if qty != 0: # Elimizde varsa
                has_assets = True
                try:
                    s_data = data[sym] if len(symbols) > 1 else data
                    
                    # Bugünün verileri
                    price_open = s_data['Open'].loc[date]
                    price_high = s_data['High'].loc[date]
                    price_low = s_data['Low'].loc[date]
                    price_close = s_data['Close'].loc[date]
                    
                    # Dünün kapanış fiyatı (Referans)
                    if i > 0:
                        prev_date = all_dates[i-1]
                        price_prev = s_data['Close'].loc[prev_date]
                    else:
                        price_prev = price_open # İlk günse Open baz al

                    # Değerleme
                    portfolio_val_start += qty * price_prev
                    
                    # Mum Oluşturma (Sanal Fon Mumu)
                    # Burada sadece kapanışı değil, gün içi hareketi de NAV'a yansıtıyoruz
                    # Ancak basitlik ve hata önleme için 'Close to Close' getiriyi esas alıp
                    # High/Low'u oransal türeteceğiz.
                    portfolio_val_end += qty * price_close
                    
                except: continue
        
        # 2. NAV GÜNCELLEME (Eğer elimizde hisse varsa)
        if has_assets and portfolio_val_start > 0:
            daily_return = portfolio_val_end / portfolio_val_start
            
            # Gün içi oynaklığı hesaplamak için basit oranlar
            # (Bu kısım gerçek High/Low verisini simüle eder)
            day_open_val = 0
            day_high_val = 0
            day_low_val = 0
            
            for sym, qty in current_holdings.items():
                if qty != 0:
                    try:
                        s = data[sym].loc[date] if len(symbols)>1 else data.loc[date]
                        day_open_val += qty * s['Open']
                        day_high_val += qty * s['High']
                        day_low_val += qty * s['Low']
                    except: pass
            
            # NAV Mumlarını Hesapla
            # Mantık: NAV sadece performansa göre değişir.
            # Bugün portföy %2 arttıysa, NAV da %2 artar.
            nav_open = current_nav * (day_open_val / portfolio_val_start)
            nav_high = current_nav * (day_high_val / portfolio_val_start)
            nav_low = current_nav * (day_low_val / portfolio_val_start)
            nav_close = current_nav * daily_return
            
            nav_history.append({
                'Date': date, 
                'Open': nav_open, 'High': nav_high, 'Low': nav_low, 'Close': nav_close
            })
            
            current_nav = nav_close # Yeni baz fiyat
            
        elif not has_assets:
            # Elimizde hiç hisse yoksa (Nakit), NAV sabit kalır (Risk-free rate 0 kabul ettik)
            nav_history.append({
                'Date': date, 
                'Open': current_nav, 'High': current_nav, 'Low': current_nav, 'Close': current_nav
            })

        # 3. İŞLEMLERİ UYGULA (Yarın için hazırlık)
        # Alım/Satımlar performansı etkilemez, sadece 'current_holdings' miktarını değiştirir.
        todays_trades = trades[trades['Date'] == date]
        for _, row in todays_trades.iterrows():
            sym = row['Symbol']
            qty = row['Quantity'] # Satışlar negatif olduğu için çıkarma işlemi yapar
            current_holdings[sym] = current_holdings.get(sym, 0) + qty

    # --- GRAFİK HAZIRLIK ---
    df_nav = pd.DataFrame(nav_history)
    df_nav['Date_Str'] = df_nav['Date'].dt.strftime('%d %b %y')

    # --- DASHBOARD ---
    last_p = df_nav['Close'].iloc[-1]
    prev_p = df_nav['Close'].iloc[-2]
    diff = last_p - prev_p
    diff_pct = (diff / prev_p) * 100

    col1, col2 = st.columns([1,2])
    col1.metric("Strateji Puanı (Endeks)", f"{last_p:.2f}", f"{diff_pct:+.2f}%")
    col2.caption("Başlangıç Puanı: 100.00 | Bu değer portföyünüzün toplam dolar değerini değil, başarısını gösterir.")

    # --- ÇİZİM ---
    fig = go.Figure(data=[go.Candlestick(
        x=df_nav['Date_Str'],
        open=df_nav['Open'], high=df_nav['High'], low=df_nav['Low'], close=df_nav['Close'],
        increasing_line_color=up_color, decreasing_line_color=down_color
    )])

    fig.update_layout(
        height=600, template="plotly_white",
        title="Portfolio Performance Index (Net Asset Value)",
        yaxis_title="NAV Price (Base 100)",
        xaxis_type='category',
        xaxis_rangeslider_visible=False
    )
    
    st.plotly_chart(fig, use_container_width=True)
