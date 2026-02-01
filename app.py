import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Özgür ETF Terminal", layout="wide")

# --- SOL PANEL (AYARLAR) ---
st.sidebar.header("🛠 Grafik Ayarları")
chart_type = st.sidebar.selectbox("Grafik Tipi", ["Mum Grafiği", "Heikin Ashi", "Çizgi Grafik"])

st.sidebar.markdown("---")
st.sidebar.subheader("Göstergeler")
show_ema = st.sidebar.checkbox("EMA'ları Göster", value=True)
ema1_val = st.sidebar.number_input("EMA 1 Periyot", value=20, min_value=1)
ema2_val = st.sidebar.number_input("EMA 2 Periyot", value=50, min_value=1)

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
    
    # Tüm sembolleri ve gerekirse SPY'yi indiriyoruz
    download_list = symbols.copy()
    if show_benchmark:
        download_list.append("SPY")
        
    prices = yf.download(download_list, start="2021-01-01", interval="1d")
    
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
    
    # 2. GRAFİK KURGUSU
    rows = 1
    row_heights = [0.7]
    if show_rsi: rows += 1; row_heights.append(0.15)
    if show_drawdown: rows += 1; row_heights.append(0.15)
    
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=row_heights)

    # ANA GRAFİK
    if chart_type == "Heikin Ashi":
        ha_close = (portfolio['Open'] + portfolio['High'] + portfolio['Low'] + portfolio['Close']) / 4
        ha_open = portfolio['Open'].copy()
        for i in range(1, len(portfolio)): ha_open.iloc[i] = (ha_open.iloc[i-1] + ha_close.iloc[i-1]) / 2
        fig.add_trace(go.Candlestick(x=portfolio.index, open=ha_open, high=portfolio['High'], low=portfolio['Low'], close=ha_close, name="HA Portföy"), row=1, col=1)
    elif chart_type == "Çizgi Grafik":
        fig.add_trace(go.Scatter(x=portfolio.index, y=portfolio['Close'], line=dict(color='#2962ff', width=1.5), name="Portföy"), row=1, col=1)
    else:
        fig.add_trace(go.Candlestick(x=portfolio.index, open=portfolio['Open'], high=portfolio['High'], low=portfolio['Low'], close=portfolio['Close'], name="Portföy"), row=1, col=1)

    # EMA'lar (İnce Çizgiler)
    if show_ema:
        fig.add_trace(go.Scatter(x=portfolio.index, y=portfolio['Close'].ewm(span=ema1_val).mean(), line=dict(color='#2962ff', width=0.8), name=f"EMA {ema1_val}"), row=1, col=1)
        fig.add_trace(go.Scatter(x=portfolio.index, y=portfolio['Close'].ewm(span=ema2_val).mean(), line=dict(color='#ff9800', width=0.8), name=f"EMA {ema2_val}"), row=1, col=1)

    # BENCHMARK DÜZELTME
    if show_benchmark and "SPY" in prices['Close']:
        spy_close = prices['Close']['SPY'].reindex(portfolio.index).ffill()
        bench_norm = (spy_close / spy_close.iloc[0]) * portfolio['Close'].iloc[0]
        fig.add_trace(go.Scatter(x=portfolio.index, y=bench_norm, line=dict(color='rgba(255,255,255,0.4)', width=1, dash='dash'), name="S&P 500 (SPY)"), row=1, col=1)

    # RSI & DRAWDOWN
    curr_row = 2
    if show_rsi:
        delta = portfolio['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + (gain / loss)))
        fig.add_trace(go.Scatter(x=portfolio.index, y=rsi, line=dict(color='#9c27b0', width=1), name="RSI"), row=curr_row, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=curr_row, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=curr_row, col=1)
        curr_row += 1
    if show_drawdown:
        dd = (portfolio['Close'] - portfolio['Close'].cummax()) / portfolio['Close'].cummax() * 100
        fig.add_trace(go.Scatter(x=portfolio.index, y=dd, fill='tozeroy', line=dict(color='#f44336', width=0.5), name="Drawdown %"), row=curr_row, col=1)

    # TATİL GÜNLERİNİ TEMİZLEME VE ZAMAN BUTONLARI
    dt_all = pd.date_range(start=portfolio.index.min(), end=portfolio.index.max())
    dt_obs = [d.strftime("%Y-%m-%d") for d in portfolio.index]
    dt_breaks = [d for d in dt_all.strftime("%Y-%m-%d").tolist() if d not in dt_obs]

    fig.update_xaxes(
        type='date', gridcolor="#2a2e39", rangebreaks=[dict(values=dt_breaks)],
        rangeselector=dict(
            buttons=list([
                dict(count=1, label="1A", step="month", stepmode="backward"),
                dict(count=3, label="3A", step="month", stepmode="backward"),
                dict(count=6, label="6A", step="month", stepmode="backward"),
                dict(count=1, label="YTD", step="year", stepmode="todate"),
                dict(count=1, label="1Y", step="year", stepmode="backward"),
                dict(count=3, label="3Y", step="year", stepmode="backward"),
                dict(count=5, label="5Y", step="year", stepmode="backward"),
                dict(step="all", label="Tümü")
            ]),
            bgcolor="#1e222d", activecolor="#2962ff", font=dict(color="white")
        )
    )

    fig.update_layout(
        template='plotly_dark', height=850, xaxis_rangeslider_visible=False,
        paper_bgcolor='#131722', plot_bgcolor='#131722', margin=dict(l=10, r=50, t=30, b=10)
    )
    fig.update_yaxes(side="right", gridcolor="#2a2e39")

    st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True, 'displayModeBar': True, 'modeBarButtonsToAdd': ['drawline','eraseshape']})

    # PASTA GRAFİĞİ (SIDEBAR)
    if show_pie:
        st.sidebar.markdown("---")
        st.sidebar.subheader("Portföy Dağılımı")
        last_prices = prices['Close'].iloc[-1]
        pie_values = [df_raw[df_raw['Symbol'] == s]['Quantity'].sum() * last_prices[s] for s in symbols]
        pie_fig = go.Figure(data=[go.Pie(labels=symbols, values=pie_values, hole=.3)])
        pie_fig.update_layout(template='plotly_dark', height=350, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor='rgba(0,0,0,0)')
        st.sidebar.plotly_chart(pie_fig, use_container_width=True)

except Exception as e:
    st.error(f"Sistemsel Hata: {e}")
