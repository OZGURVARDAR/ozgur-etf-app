import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go

st.set_page_config(page_title="Özgür ETF Terminal", layout="wide")
st.title("📊 Özgür ETF - Canlı Portföy Terminali")

# 1. VERİ ÇEKME (Google Sheets Canlı Bağlantı)
# Buradaki 'DOSYA_ID_BURAYA' kısmına kendi Sheets ID'ni yapıştır
sheet_id = "DOSYA_ID_BURAYA"
sheet_name = "Sheet1" # Sayfa adın farklıysa düzelt (Örn: Sayfa1)
url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"

@st.cache_data(ttl=600) # Veriyi 10 dakikada bir tazeler
def load_data():
    df = pd.read_csv(url)
    df['Date'] = pd.to_datetime(df['Date'])
    return df

df_trades = load_data()

# 2. HESAPLAMA VE GRAFİK (Mevcut mantık devam ediyor)
symbols = df_trades['Symbol'].unique().tolist()
prices_ohlc = yf.download(symbols, start="2025-11-01", interval="1d")

portfolio_ohlc = pd.DataFrame(index=prices_ohlc.index)
for col in ['Open', 'High', 'Low', 'Close']:
    portfolio_ohlc[col] = 0.0
    for _, trade in df_trades.iterrows():
        portfolio_ohlc.loc[trade['Date']:, col] += prices_ohlc[col][trade['Symbol']] * trade['Quantity']

# 3. GÖRSELLEŞTİRME
fig = go.Figure(data=[go.Candlestick(
    x=portfolio_ohlc.index,
    open=portfolio_ohlc['Open'],
    high=portfolio_ohlc['High'],
    low=portfolio_ohlc['Low'],
    close=portfolio_ohlc['Close']
)])

fig.update_layout(template='plotly_dark', height=700, xaxis_rangeslider_visible=True)
st.plotly_chart(fig, use_container_width=True)

st.success(f"Son Güncelleme: {pd.Timestamp.now().strftime('%H:%M:%S')} - Veriler Google Sheets'ten canlı akıyor.")
