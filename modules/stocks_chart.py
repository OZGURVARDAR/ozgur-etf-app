import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def show():
    st.subheader("📊 Gerçek Zamanlı Portföy Gelişim Grafiği")

    # --- SETTINGS ---
    chart_type = st.sidebar.selectbox("Grafik Türü", ["Candlestick", "Heiken Ashi", "Line"])
    show_rsi = st.sidebar.checkbox("RSI Göster", value=True)
    
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

    @st.cache_data(ttl=300)
    def load_and_process_data():
        df = pd.read_csv(SHEET_URL)
        df['Date'] = pd.to_datetime(df['Date'])
        # Sadece hisse senetlerini al (CASH hariç)
        trades = df[df["Symbol"] != "CASH"].sort_values('Date').copy()
        return trades

    trades = load_and_process_data()
    symbols = trades["Symbol"].unique().tolist()

    if not symbols:
        st.info("Portföyde hisse bulunamadı.")
        return

    # --- 1. VERİ ÇEKME ---
    first_date = trades['Date'].min()
    with st.spinner('Borsa verileri alınıyor...'):
        # En eski alım tarihinden bugüne kadar olan veriyi çek
        data = yf.download(symbols, start=first_date, interval="1d", group_by='ticker', progress=False)

    # --- 2. DİNAMİK PORTFÖY HESAPLAMA ---
    # Her bir işlem günü için boş bir tablo oluşturuyoruz
    portfolio_history = pd.DataFrame(index=data.index)
    portfolio_history['Market_Value'] = 0.0
    portfolio_history['Total_Cost'] = 0.0

    for current_date in data.index:
        daily_market_value = 0.0
        daily_cost_basis = 0.0
        
        # O tarihe kadar (dahil) yapılmış tüm alımları filtrele
        past_trades = trades[trades['Date'] <= current_date]
        
        # Her hisse için o günkü toplam adedi ve maliyeti hesapla
        for symbol in symbols:
            symbol_trades = past_trades[past_trades['Symbol'] == symbol]
            if not symbol_trades.empty:
                total_qty = symbol_trades['Quantity'].sum()
                total_cost = (symbol_trades['Quantity'] * symbol_trades['Price']).sum()
                
                # O günkü hisse fiyatını bul
                try:
                    price_col = data[symbol]['Close'] if len(symbols) > 1 else data['Close']
                    current_price = price_col.loc[current_date]
                    if pd.isna(current_price): # Eğer o gün veri yoksa bir önceki güne bak
                        current_price = price_col.asof(current_date)
                        
                    daily_market_value += total_qty * current_price
                    daily_cost_basis += total_cost
                except:
                    continue
        
        portfolio_history.loc[current_date, 'Market_Value'] = daily_market_value
        portfolio_history.loc[current_date, 'Total_Cost'] = daily_cost_basis

    # OHLC Verisine Dönüştür (Günlük)
    # Market value üzerinden mumları oluşturuyoruz
    df_plot = portfolio_history['Market_Value'].resample('B').ohlc().dropna()
    df_cost = portfolio_history['Total_Cost'].resample('B').last().ffill()

    # --- 3. GÖRSELLEŞTİRME ---
    rows = 2 if show_rsi else 1
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.05)

    # Mum Grafiği (Piyasa Değeri)
    fig.add_trace(go.Candlestick(
        x=df_plot.index, open=df_plot['open'], high=df_plot['high'], 
        low=df_plot['low'], close=df_plot['close'], name="Portföy Değeri"
    ), row=1, col=1)

    # Dinamik Maliyet Çizgisi (Her alımla beraber basamak gibi yükselir)
    fig.add_trace(go.Scatter(
        x=df_cost.index, y=df_cost, name="Toplam Maliyet", 
        line=dict(color='gray', width=2, dash='dash')
    ), row=1, col=1)

    # RSI Hesaplama
    if show_rsi:
        delta = df_plot["close"].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss
        df_plot["RSI"] = 100 - (100 / (1 + rs))
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot["RSI"], name="RSI", line=dict(color='purple')), row=2, col=1)

    # --- FORMATLAMA (20k yerine 20,000) ---
    fig.update_yaxes(tickformat=",d", title_text="Portföy Değeri ($)", row=1, col=1)
    fig.update_xaxes(type='category', nticks=15)
    
    fig.update_layout(
        height=750, 
        xaxis_rangeslider_visible=False, 
        template="plotly_white",
        margin=dict(l=20, r=20, t=20, b=20),
        legend=dict(orientation="h", y=1.05)
    )
    
    st.plotly_chart(fig, use_container_width=True)
