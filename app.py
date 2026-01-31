import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime

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
    # Verileri çek
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

    # Sadece verinin olduğu günleri al ve boşlukları temizle
    portfolio_ohlc = portfolio_ohlc[portfolio_ohlc['Close'] > 0].dropna()
    date_strings = portfolio_ohlc.index.strftime('%Y-%m-%d')

    # 2. GRAFİK OLUŞTURMA
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=date_strings,
        open=portfolio_ohlc['Open'],
        high=portfolio_ohlc['High'],
        low=portfolio_ohlc['Low'],
        close=portfolio_ohlc['Close'],
        increasing_line_color='#089981', decreasing_line_color='#f23645',
        increasing_fillcolor='#089981', decreasing_fillcolor='#f23645',
        name="Portföy"
    ))

    # --- ZAMAN BUTONLARINI YENİDEN AKTİFLEŞTİRME ---
    # Kategori tipinde butonların çalışması için 'backward' yerine veri sayısı üzerinden gidiyoruz
    fig.update_xaxes(
        type='category',
        gridcolor="#2a2e39",
        tickangle=-45,
        rangeslider_visible=False,
        rangeselector=dict(
            buttons=list([
                dict(count=5, label="5G", step="all", stepmode="backward"),
                dict(count=22, label="1A", step="all", stepmode="backward"),
                dict(count=66, label="3A", step="all", stepmode="backward"),
                dict(count=132, label="6A", step="all", stepmode="backward"),
                dict(step="all", label="Tümü")
            ]),
            bgcolor="#1e222d", activecolor="#2962ff", font=dict(color="white")
        )
    )

    fig.update_layout(
        template='plotly_dark',
        height=750,
        yaxis=dict(side="right", gridcolor="#2a2e39", tickformat="$,.0f"),
        paper_bgcolor='#131722',
        plot_bgcolor='#131722',
        margin=dict(l=10, r=50, t=50, b=10)
    )

    st.plotly_chart(fig, use_container_width=True)

    # 3. İSTATİSTİK PANELİ (Veri kaybı olmadığını buradan kontrol edebilirsin)
    c1, c2, c3, c4 = st.columns(4)
    curr = portfolio_ohlc['Close'].iloc[-1]
    prev = portfolio_ohlc['Close'].iloc[-2]
    change_val = curr - prev
    change_pct = (change_val / prev) * 100
    
    c1.metric("Anlık Portföy Değeri", f"${curr:,.2f}", f"{change_pct:+.2f}%")
    c2.metric("Günlük Değişim", f"${change_val:,.2f}")
    c3.metric("Toplam Pozisyon", len(symbols))
    c4.metric("Veri Günü Sayısı", len(portfolio_ohlc))

except Exception as e:
    st.error(f"Hata: {e}")
