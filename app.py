import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="Özgür ETF Terminal", layout="wide")
st.title("📊 Özgür ETF - Profesyonel Portföy Terminali")

# 1. VERİ ÇEKME
sheet_id = "1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw"
url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"

@st.cache_data(ttl=300)
def load_data():
    df = pd.read_csv(url)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.groupby(['Date', 'Symbol'])['Quantity'].sum().reset_index()
    return df

try:
    df_trades = load_data()
    symbols = df_trades['Symbol'].unique().tolist()
    # Veri setini başlangıçtan itibaren geniş çekiyoruz
    prices_ohlc = yf.download(symbols, start="2025-11-01", interval="1d")
    
    # HESAPLAMA (Kümülatif)
    portfolio_ohlc = pd.DataFrame(index=prices_ohlc.index)
    for col in ['Open', 'High', 'Low', 'Close']:
        portfolio_ohlc[col] = 0.0
        for symbol in symbols:
            symbol_trades = df_trades[df_trades['Symbol'] == symbol].copy()
            symbol_trades = symbol_trades.set_index('Date').reindex(prices_ohlc.index).fillna(0)
            cumulative_quantity = symbol_trades['Quantity'].cumsum()
            portfolio_ohlc[col] += prices_ohlc[col][symbol] * cumulative_quantity

    portfolio_ohlc = portfolio_ohlc[portfolio_ohlc['Close'] > 0]

    # 2. ZAMAN ARALIĞI SEÇİCİ (TradingView Stili Butonlar)
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=portfolio_ohlc.index,
        open=portfolio_ohlc['Open'],
        high=portfolio_ohlc['High'],
        low=portfolio_ohlc['Low'],
        close=portfolio_ohlc['Close'],
        increasing_line_color='#089981', decreasing_line_color='#f23645',
        increasing_fillcolor='#089981', decreasing_fillcolor='#f23645',
        name="Portföy Değeri"
    ))

    # TradingView Benzeri Zaman Butonları Ayarı
    fig.update_xaxes(
        rangeselector=dict(
            buttons=list([
                dict(count=5, label="5G", step="day", stepmode="backward"),
                dict(count=1, label="1A", step="month", stepmode="backward"),
                dict(count=3, label="3A", step="month", stepmode="backward"),
                dict(count=6, label="6A", step="month", stepmode="backward"),
                dict(count=1, label="YTD", step="year", stepmode="todate"),
                dict(count=1, label="1Y", step="year", stepmode="backward"),
                dict(step="all", label="Tümü")
            ]),
            bgcolor="#1e222d", activecolor="#2962ff", font=dict(color="white")
        ),
        gridcolor="#2a2e39"
    )

    fig.update_layout(
        template='plotly_dark',
        height=750,
        xaxis_rangeslider_visible=False, # Daha temiz görünüm için
        dragmode='pan', # Mouse ile kaydırma aktif
        yaxis=dict(
            side="right", # Fiyat skalası sağda (TradingView gibi)
            fixedrange=False, # Skalayı tutup çekme aktif!
            gridcolor="#2a2e39"
        ),
        paper_bgcolor='#131722',
        plot_bgcolor='#131722',
        margin=dict(l=10, r=10, t=30, b=10)
    )

    st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})

    # ANALİZ PANELİ
    c1, c2, c3 = st.columns(3)
    curr = portfolio_ohlc['Close'].iloc[-1]
    change_pct = ((curr / portfolio_ohlc['Close'].iloc[-2]) - 1) * 100
    c1.metric("Anlık Değer", f"${curr:,.2f}", f"{change_pct:+.2f}%")
    c2.metric("Toplam Hisse", len(symbols))
    c3.info(f"Son Veri: {portfolio_ohlc.index[-1].strftime('%d.%m.%Y')}")

except Exception as e:
    st.error(f"Hata: {e}")
