import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(page_title="Özgür ETF Terminal", layout="wide")
st.title("📊 Özgür ETF - Profesyonel Portföy Terminali")

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
    prices_ohlc = yf.download(symbols, start="2025-11-01", interval="1d")
    
    portfolio_ohlc = pd.DataFrame(index=prices_ohlc.index)
    for col in ['Open', 'High', 'Low', 'Close']:
        portfolio_ohlc[col] = 0.0
        for symbol in symbols:
            symbol_trades = df_trades[df_trades['Symbol'] == symbol].copy()
            symbol_trades = symbol_trades.set_index('Date').reindex(prices_ohlc.index).fillna(0)
            cumulative_quantity = symbol_trades['Quantity'].cumsum()
            portfolio_ohlc[col] += prices_ohlc[col][symbol] * cumulative_quantity

    # Sadece verinin olduğu günleri al
    portfolio_ohlc = portfolio_ohlc[portfolio_ohlc['Close'] > 0].dropna()

    # TARİHLERİ FORMATLI LİSTEYE ÇEVİR (Boşlukları bitirmek için kritik)
    # Bu, x eksenini "tarih" değil "etiket" (label) yapar.
    date_strings = portfolio_ohlc.index.strftime('%Y-%m-%d')

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=date_strings, # Tarih objesi yerine metin listesi kullanıyoruz
        open=portfolio_ohlc['Open'],
        high=portfolio_ohlc['High'],
        low=portfolio_ohlc['Low'],
        close=portfolio_ohlc['Close'],
        increasing_line_color='#089981', decreasing_line_color='#f23645',
        increasing_fillcolor='#089981', decreasing_fillcolor='#f23645',
        name="Portföy Değeri"
    ))

    # --- TAMAMEN BİTİŞİK MUM AYARLARI ---
    fig.update_xaxes(
        type='category', # BU SATIR TÜM BOŞLUKLARI (Hafta sonu + Tatil) SİLER
        gridcolor="#2a2e39",
        nticks=20, # Eksen etiketlerini sadeleştirir
        tickangle=-45
    )

    fig.update_layout(
        template='plotly_dark',
        height=750,
        xaxis_rangeslider_visible=False,
        yaxis=dict(
            side="right",
            gridcolor="#2a2e39",
            tickformat="$,.0f"
        ),
        paper_bgcolor='#131722',
        plot_bgcolor='#131722',
        margin=dict(l=10, r=50, t=30, b=10)
    )

    st.plotly_chart(fig, use_container_width=True)

    # ANALİZ PANELİ
    curr = portfolio_ohlc['Close'].iloc[-1]
    st.metric("Anlık Portföy Değeri", f"${curr:,.2f}")

except Exception as e:
    st.error(f"Hata: {e}")
