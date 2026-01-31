import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go

# Sayfa Ayarları
st.set_page_config(page_title="Özgür ETF Terminal", layout="wide")
st.title("📊 Özgür ETF - Canlı Portföy Terminali")

# 1. VERİ ÇEKME (Senin ID'n Tanımlandı)
sheet_id = "1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw"
# En garanti bağlantı formatı:
url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"

@st.cache_data(ttl=600)
def load_data():
    # Sütun isimlerini Sheets'teki gibi (Date, Symbol, Quantity) okur
    df = pd.read_csv(url)
    df['Date'] = pd.to_datetime(df['Date'])
    return df

try:
    df_trades = load_data()

    # 2. HESAPLAMA
    symbols = df_trades['Symbol'].unique().tolist()
    # Gün içi hareketler için veriyi çekiyoruz
    prices_ohlc = yf.download(symbols, start="2025-11-01", interval="1d")

    portfolio_ohlc = pd.DataFrame(index=prices_ohlc.index)
    for col in ['Open', 'High', 'Low', 'Close']:
        portfolio_ohlc[col] = 0.0
        for _, trade in df_trades.iterrows():
            # Satın alma tarihinden itibaren portföye ekle
            portfolio_ohlc.loc[trade['Date']:, col] += prices_ohlc[col][trade['Symbol']] * trade['Quantity']

    # 3. GÖRSELLEŞTİRME (Mum Grafiği)
    st.subheader("Portföy Günlük Mum Grafiği (OHLC)")
    fig = go.Figure(data=[go.Candlestick(
        x=portfolio_ohlc.index,
        open=portfolio_ohlc['Open'],
        high=portfolio_ohlc['High'],
        low=portfolio_ohlc['Low'],
        close=portfolio_ohlc['Close'],
        name="Özgür ETF"
    )])

    fig.update_layout(
        template='plotly_dark', 
        height=700, 
        xaxis_rangeslider_visible=True,
        yaxis_title="Toplam Portföy Değeri ($)"
    )
    st.plotly_chart(fig, use_container_width=True)

    st.success(f"✅ Bağlantı Başarılı! Son Güncelleme: {pd.Timestamp.now().strftime('%H:%M:%S')}")
    st.info("Bilgi: Veriler 10 dakikada bir otomatik tazelenir. Anlık görmek için sayfayı yenileyebilirsiniz.")

except Exception as e:
    st.error(f"⚠️ Bir hata oluştu: {e}")
    st.warning("Lütfen Google Sheets dosyanızın 'Bağlantıya sahip olan herkes' erişimine açık olduğundan emin olun.")
