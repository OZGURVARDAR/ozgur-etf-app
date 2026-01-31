import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime

# Sayfa Ayarları
st.set_page_config(page_title="Özgür ETF Terminal", layout="wide")
st.title("📊 Özgür ETF - Profesyonel Portföy Terminali")

# 1. VERİ ÇEKME (Canlı Bağlantı)
sheet_id = "1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw"
url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"

@st.cache_data(ttl=600)
def load_data():
    df = pd.read_csv(url)
    df['Date'] = pd.to_datetime(df['Date'])
    # Aynı gün yapılan alımları birleştir
    df = df.groupby(['Date', 'Symbol'])['Quantity'].sum().reset_index()
    return df

try:
    df_trades = load_data()
    symbols = df_trades['Symbol'].unique().tolist()
    
    # Yahoo Finance'den verileri çek (Gün içi dahil)
    prices_ohlc = yf.download(symbols, start="2025-11-01", interval="1d")
    
    # Boş bir portföy OHLC tablosu oluştur
    portfolio_ohlc = pd.DataFrame(index=prices_ohlc.index)
    for col in ['Open', 'High', 'Low', 'Close']:
        portfolio_ohlc[col] = 0.0
        
        # Her bir hisse için kümülatif adetleri hesapla ve fiyata çarp
        for symbol in symbols:
            # Hisse senedinin o tarihe kadar olan toplam adedini bul
            symbol_trades = df_trades[df_trades['Symbol'] == symbol].copy()
            symbol_trades = symbol_trades.set_index('Date').reindex(prices_ohlc.index).fillna(0)
            cumulative_quantity = symbol_trades['Quantity'].cumsum()
            
            # Toplam değeri portföye ekle
            portfolio_ohlc[col] += prices_ohlc[col][symbol] * cumulative_quantity

    # 0 olan (henüz alım yapılmamış) günleri temizle
    portfolio_ohlc = portfolio_ohlc[portfolio_ohlc['Close'] > 0]

    # 3. GÖRSELLEŞTİRME (TradingView Stili)
    fig = go.Figure(data=[go.Candlestick(
        x=portfolio_ohlc.index,
        open=portfolio_ohlc['Open'],
        high=portfolio_ohlc['High'],
        low=portfolio_ohlc['Low'],
        close=portfolio_ohlc['Close'],
        increasing_line_color='#00ff88', decreasing_line_color='#ff3344',
        name="Toplam Portföy"
    )])

    fig.update_layout(
        template='plotly_dark',
        height=700,
        xaxis_rangeslider_visible=False,
        yaxis_title="Portföy Değeri ($)",
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color="white")
    )
    
    # Grafiği çiz
    st.plotly_chart(fig, use_container_width=True)

    # Özet Bilgi Kartları
    col1, col2, col3 = st.columns(3)
    current_val = portfolio_ohlc['Close'].iloc[-1]
    prev_val = portfolio_ohlc['Close'].iloc[-2]
    change = current_val - prev_val
    
    col1.metric("Anlık Portföy Değeri", f"${current_val:,.2f}", f"${change:,.2f}")
    col2.metric("Aktif Hisse Sayısı", len(symbols))
    col3.metric("Son Güncelleme", datetime.now().strftime("%H:%M:%S"))

except Exception as e:
    st.error(f"Bağlantı veya Hesaplama Hatası: {e}")
