import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

st.set_page_config(page_title="Özgür ETF Terminal", layout="wide")

# --- SOL PANEL (AYARLAR & KONTROLLER) ---
st.sidebar.header("🛠 Grafik Ayarları")
chart_type = st.sidebar.selectbox("Grafik Tipi", ["Mum Grafiği", "Heikin Ashi", "Çizgi Grafik"])

st.sidebar.markdown("---")
st.sidebar.subheader("Göstergeler")
show_ema = st.sidebar.checkbox("EMA'ları Göster", value=True)
show_rsi = st.sidebar.checkbox("RSI Göster", value=False)
show_drawdown = st.sidebar.checkbox("Drawdown Göster", value=False)
show_benchmark = st.sidebar.checkbox("Benchmark (S&P 500) Kıyasla", value=False)
show_pie = st.sidebar.checkbox("Portföy Dağılımını Göster", value=True)

# 1. VERİ ÇEKME
sheet_id = "1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw"
url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"

@st.cache_data(ttl=300)
def load_data():
    df = pd.read_csv(url)
    df['Date'] = pd.to_datetime(df['Date'])
    return df

try:
    df_raw = load_data()
    symbols = df_raw['Symbol'].unique().tolist()
    
    # Veri derinliği (Benchmark için de gerekli)
    start_date = "2021-01-01"
    prices = yf.download(symbols + (['SPY'] if show_benchmark else []), start=start_date, interval="1d")
    
    # PORTFÖY HESAPLAMA
    portfolio = pd.DataFrame(index=prices.index)
    for col in ['Open', 'High', 'Low', 'Close']:
        portfolio[col] = 0.0
        for symbol in symbols:
            s_trades = df_raw[df_raw['Symbol'] == symbol].copy()
            s_trades = s_trades.set_index('Date').reindex(prices.index).fillna(0)
            cum_qty = s_trades['Quantity'].cumsum()
            portfolio[col] += prices[col][symbol] * cum_qty

    portfolio = portfolio[portfolio['Close'] > 0].dropna()
    
    # --- TEKNİK HESAPLAMALAR ---
    # RSI
    delta = portfolio['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    portfolio['RSI'] = 100 - (100 / (1 + rs))

    # Drawdown
    rolling_max = portfolio['Close'].cummax()
    portfolio['Drawdown'] = (portfolio['Close'] - rolling_max) / rolling_max * 100

    # Benchmark (Normalizasyon: İkisi de 100'den başlasın)
    if show_benchmark:
        bench = prices['Close']['SPY'].loc[portfolio.index[0]:]
        portfolio['Bench_Norm'] = (bench / bench.iloc[0]) * portfolio['Close'].iloc[0]

    # --- GRAFİK KURGUSU (SUBPLOTS) ---
    rows = 1
    row_heights = [0.7]
    if show_rsi: 
        rows += 1
        row_heights.append(0.15)
    if show_drawdown: 
        rows += 1
        row_heights.append(0.15)
    
    # row_heights toplamı 1 olmalı, dengeleyelim
    total_h = sum(row_heights)
    row_heights = [h/total_h for h in row_heights]

    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=row_heights)

    # Ana Grafik
    if chart_type == "Heikin Ashi":
        ha_close = (portfolio['Open'] + portfolio['High'] + portfolio['Low'] + portfolio['Close']) / 4
        ha_open = portfolio['Open'].copy()
        for i in range(1, len(portfolio)): ha_open.iloc[i] = (ha_open.iloc[i-1] + ha_close.iloc[i-1]) / 2
        fig.add_trace(go.Candlestick(x=portfolio.index, open=ha_open, high=portfolio['High'], low=portfolio['Low'], close=ha_close, name="HA Portföy"), row=1, col=1)
    elif chart_type == "Çizgi Grafik":
        fig.add_trace(go.Scatter(x=portfolio.index, y=portfolio['Close'], line=dict(color='#2962ff', width=2), name="Portföy"), row=1, col=1)
    else:
        fig.add_trace(go.Candlestick(x=portfolio.index, open=portfolio['Open'], high=portfolio['High'], low=portfolio['Low'], close=portfolio['Close'], name="Portföy"), row=1, col=1)

    # EMA & Benchmark
    if show_ema:
        fig.add_trace(go.Scatter(x=portfolio.index, y=portfolio['Close'].ewm(span=20).mean(), line=dict(color='#2962ff', width=1), name="EMA 20"), row=1, col=1)
        fig.add_trace(go.Scatter(x=portfolio.index, y=portfolio['Close'].ewm(span=50).mean(), line=dict(color='#ff9800', width=1), name="EMA 50"), row=1, col=1)
    if show_benchmark:
        fig.add_trace(go.Scatter(x=portfolio.index, y=portfolio['Bench_Norm'], line=dict(color='white', width=1, dash='dash'), name="S&P 500 (SPY)"), row=1, col=1)

    # RSI Subplot
    curr_row = 2
    if show_rsi:
        fig.add_trace(go.Scatter(x=portfolio.index, y=portfolio['RSI'], line=dict(color='#9c27b0', width=1.5), name="RSI (14)"), row=curr_row, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=curr_row, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=curr_row, col=1)
        curr_row += 1

    # Drawdown Subplot
    if show_drawdown:
        fig.add_trace(go.Scatter(x=portfolio.index, y=portfolio['Drawdown'], fill='tozeroy', line=dict(color='#f44336'), name="Drawdown %"), row=curr_row, col=1)

    # Düzenlemeler
    dt_all = pd.date_range(start=portfolio.index.min(), end=portfolio.index.max())
    dt_breaks = [d for d in dt_all.strftime("%Y-%m-%d").tolist() if d not in [idx.strftime("%Y-%m-%d") for idx in portfolio.index]]

    fig.update_xaxes(type='date', gridcolor="#2a2e39", rangebreaks=[dict(values=dt_breaks)])
    fig.update_layout(template='plotly_dark', height=900, xaxis_rangeslider_visible=False,
                      paper_bgcolor='#131722', plot_bgcolor='#131722', margin=dict(l=10, r=50, t=30, b=10))
    fig.update_yaxes(side="right", gridcolor="#2a2e39")

    st.plotly_chart(fig, use_container_width=True)

    # --- SIDEBAR PASTA GRAFİĞİ ---
    if show_pie:
        st.sidebar.markdown("---")
        st.sidebar.subheader("Portföy Dağılımı")
        latest_qtys = df_raw.groupby('Symbol')['Quantity'].sum()
        latest_prices = prices['Close'].iloc[-1]
        values = [latest_qtys[s] * latest_prices[s] for s in symbols]
        pie_fig = go.Figure(data=[go.Pie(labels=symbols, values=values, hole=.3)])
        pie_fig.update_layout(template='plotly_dark', showlegend=True, height=300, 
                              margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor='rgba(0,0,0,0)')
        st.sidebar.plotly_chart(pie_fig, use_container_width=True)

except Exception as e:
    st.error(f"Hata: {e}")
