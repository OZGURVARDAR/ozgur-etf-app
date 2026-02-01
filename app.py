import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(page_title="Özgür ETF Terminal", layout="wide")

# --- SOL PANEL (AYARLAR) ---
st.sidebar.header("🛠 Grafik Ayarları")
show_ema20 = st.sidebar.checkbox("EMA 20 Göster", value=True)
ema20_val = st.sidebar.number_input("EMA 1 Periyot", value=20, min_value=1)

show_ema_custom = st.sidebar.checkbox("Custom EMA Göster", value=True)
ema_custom_val = st.sidebar.number_input("EMA 2 Periyot (Örn: 50 veya 100)", value=50, min_value=1)

st.title("📊 Özgür ETF - Teknik Analiz Terminali")

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
    prices_ohlc = yf.download(symbols, start="2025-11-01", interval="1d")
    
    # HESAPLAMA
    portfolio_ohlc = pd.DataFrame(index=prices_ohlc.index)
    for col in ['Open', 'High', 'Low', 'Close']:
        portfolio_ohlc[col] = 0.0
        for symbol in symbols:
            symbol_trades = df_trades[df_trades['Symbol'] == symbol].copy()
            symbol_trades = symbol_trades.set_index('Date').reindex(prices_ohlc.index).fillna(0)
            cumulative_quantity = symbol_trades['Quantity'].cumsum()
            portfolio_ohlc[col] += prices_ohlc[col][symbol] * cumulative_quantity

    portfolio_ohlc = portfolio_ohlc[portfolio_ohlc['Close'] > 0].dropna()

    # EMA HESAPLAMALARI
    portfolio_ohlc['EMA20'] = portfolio_ohlc['Close'].ewm(span=ema20_val, adjust=False).mean()
    portfolio_ohlc['EMA_Custom'] = portfolio_ohlc['Close'].ewm(span=ema_custom_val, adjust=False).mean()

    # 2. GRAFİK OLUŞTURMA
    fig = go.Figure()

    # Mum Grafiği
    fig.add_trace(go.Candlestick(
        x=portfolio_ohlc.index,
        open=portfolio_ohlc['Open'], high=portfolio_ohlc['High'],
        low=portfolio_ohlc['Low'], close=portfolio_ohlc['Close'],
        name="Portföy"
    ))

    # EMA Çizgileri (Sadece checkbox işaretliyse görünür)
    if show_ema20:
        fig.add_trace(go.Scatter(x=portfolio_ohlc.index, y=portfolio_ohlc['EMA20'], 
                                 line=dict(color='#2962ff', width=1.5), name=f'EMA {ema20_val}'))
    
    if show_ema_custom:
        fig.add_trace(go.Scatter(x=portfolio_ohlc.index, y=portfolio_ohlc['EMA_Custom'], 
                                 line=dict(color='#ff9800', width=1.5), name=f'EMA {ema_custom_val}'))

    # Grafik Düzenlemeleri (Versiyon 1'deki butonları koruyoruz)
    fig.update_xaxes(
        type='date',
        gridcolor="#2a2e39",
        rangebreaks=[dict(bounds=["sat", "mon"])],
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
            bgcolor="#1e222d", activecolor="#2962ff"
        )
    )

    fig.update_layout(
        template='plotly_dark', height=750, xaxis_rangeslider_visible=False,
        yaxis=dict(side="right", gridcolor="#2a2e39", tickformat="$,.0f"),
        paper_bgcolor='#131722', plot_bgcolor='#131722',
        margin=dict(l=10, r=50, t=50, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"Hata: {e}")
