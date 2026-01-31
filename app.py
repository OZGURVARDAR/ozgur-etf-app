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

    # İlk alımdan önceki boş günleri ve hafta sonlarını temizle
    portfolio_ohlc = portfolio_ohlc[portfolio_ohlc['Close'] > 0].dropna()

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=portfolio_ohlc.index,
        open=portfolio_ohlc['Open'],
        high=portfolio_ohlc['High'],
        low=portfolio_ohlc['Low'],
        close=portfolio_ohlc['Close'],
        increasing_line_color='#089981', decreasing_line_color='#f23645',
        increasing_fillcolor='#089981', decreasing_fillcolor='#f23645',
        line=dict(width=1),
        name="Özgür ETF"
    ))

    # --- TRADINGVIEW ESNEKLİĞİ VE BOŞLUK GİDERME ---
    fig.update_xaxes(
        type='date',
        rangebreaks=[dict(bounds=["sat", "mon"])], # Hafta sonu boşluklarını siler
        gridcolor="#2a2e39",
        # Tarih skalası esnekliği
        fixedrange=False,
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
        template='plotly_dark',
        height=800,
        xaxis_rangeslider_visible=False,
        # Fiyat skalası esnekliği (Sağda)
        yaxis=dict(
            side="right",
            fixedrange=False, 
            gridcolor="#2a2e39",
            tickformat=",.0f"
        ),
        paper_bgcolor='#131722',
        plot_bgcolor='#131722',
        margin=dict(l=10, r=50, t=30, b=10),
        # Mouse ile seçim yerine kaydırma/ölçeklendirme modu
        dragmode='pan'
    )

    # Streamlit üzerinde skalayı çekebilmek için konfigürasyon
    st.plotly_chart(fig, use_container_width=True, config={
        'scrollZoom': True,           # Mouse tekerleği ile zoom
        'displayModeBar': True,       # Mod barını göster
        'modeBarButtonsToAdd': ['drawline', 'drawopenpath', 'eraseshape'], # Çizim araçları (Opsiyonel)
        'editable': True              # Eksenlerin elle çekilebilmesini sağlar
    })

    # ANALİZ PANELİ
    curr = portfolio_ohlc['Close'].iloc[-1]
    st.metric("Güncel Portföy Değeri", f"${curr:,.2f}")

except Exception as e:
    st.error(f"Hata: {e}")
