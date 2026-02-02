import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go

def show():
    st.subheader("🛡️ Personal Portfolio ETF (NAV Performance)")

    SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

    @st.cache_data(ttl=300)
    def load_clean_data():
        df = pd.read_csv(SHEET_URL)
        df['Date'] = pd.to_datetime(df['Date'])
        return df.sort_values('Date')

    df_all = load_clean_data()
    trades = df_all[df_all["Symbol"] != "CASH"].copy()
    symbols = trades["Symbol"].unique().tolist()

    if not symbols:
        st.info("Portföy verisi bulunamadı.")
        return

    # --- DATA FETCHING ---
    first_date = trades['Date'].min()
    with st.spinner('ETF Verileri Hesaplanıyor...'):
        # Tüm hisselerin günlük verilerini çek
        data = yf.download(symbols, start=first_date, interval="1d", group_by='ticker', progress=False)

    # --- NAV (Birim Değer) HESAPLAMA ---
    # Başlangıçta 100 birim paramız olduğunu varsayıyoruz (ETF mantığı)
    nav_df = pd.DataFrame(index=data.index)
    nav_df['Total_Market_Value'] = 0.0
    nav_df['Daily_NAV'] = 100.0 # Başlangıç fiyatı: 100

    current_holdings = {sym: 0 for sym in symbols}
    
    # Her gün için hesapla
    for i, current_date in enumerate(data.index):
        # 1. O günkü alım-satım işlemlerini güncelle
        todays_trades = trades[trades['Date'].dt.date == current_date.date()]
        for _, row in todays_trades.iterrows():
            current_holdings[row['Symbol']] += row['Quantity']
        
        # 2. Portföyün o günkü toplam piyasa değerini bul
        market_val = 0.0
        for sym, qty in current_holdings.items():
            if qty > 0:
                try:
                    price = data[sym]['Close'].loc[current_date] if len(symbols) > 1 else data['Close'].loc[current_date]
                    if pd.isna(price): 
                        price = data[sym]['Close'].asof(current_date) if len(symbols) > 1 else data['Close'].asof(current_date)
                    market_val += qty * price
                except: continue
        
        nav_df.loc[current_date, 'Total_Market_Value'] = market_val
        
        # 3. Birim Değer (Performance) Hesaplama
        # İlk gün fiyat 100, sonraki günler piyasa değerindeki % değişime göre artar/azalır
        if i > 0:
            prev_date = data.index[i-1]
            prev_val = nav_df.loc[prev_date, 'Total_Market_Value']
            
            # Eğer yeni alım yapıldıysa, alım miktarını değişimden arındır (ETF mantığı)
            # Bu kısım fiyat hareketini alım hareketinden izole eder
            if prev_val > 0:
                # Günlük getiri oranı = (Bugünkü Değer - Yeni Alımlar) / Önceki Değer
                new_investment = (todays_trades['Quantity'] * todays_trades['Price']).sum()
                daily_return = (market_val - new_investment) / prev_val
                nav_df.loc[current_date, 'Daily_NAV'] = nav_df.loc[prev_date, 'Daily_NAV'] * daily_return
            else:
                nav_df.loc[current_date, 'Daily_NAV'] = 100.0

    # Mum Grafiği Oluştur (NAV üzerinden)
    df_ohlc = nav_df['Daily_NAV'].resample('B').ohlc().dropna()

    # --- PLOTLY ---
    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df_ohlc.index,
        open=df_ohlc['open'], high=df_ohlc['high'],
        low=df_ohlc['low'], close=df_ohlc['close'],
        name="Portfolio NAV"
    ))

    # Y-Ekseni Formatı
    fig.update_yaxes(title_text="ETF Birim Fiyatı (Baz: 100)", tickformat=".2f")
    fig.update_xaxes(type='category', nticks=15)
    
    fig.update_layout(
        height=600,
        title="Kişisel Portföy Performans Grafiği (ETF Style)",
        xaxis_rangeslider_visible=False,
        template="plotly_white",
        margin=dict(l=20, r=20, t=50, b=20)
    )

    st.plotly_chart(fig, use_container_width=True)
    
    # Bilgi Paneli
    st.info("💡 Bu grafik portföyünüzü bir ETF gibi takip eder. Yeni nakit girişleri (alım) grafiği yukarı zıplatmaz, sadece hisselerinizin performansını gösterir.")
