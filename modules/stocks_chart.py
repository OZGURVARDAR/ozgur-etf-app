import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go

def show():
    # --- TRADINGVIEW RENK PALETİ ---
    up_color, down_color = '#26a69a', '#ef5350'
    
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

    @st.cache_data(ttl=300)
    def load_data():
        df = pd.read_csv(SHEET_URL)
        df['Date'] = pd.to_datetime(df['Date']).dt.normalize()
        trades = df[df["Symbol"] != "CASH"].sort_values('Date')
        return trades, trades['Date'].min()

    trades, first_date = load_data()
    symbols = trades["Symbol"].unique().tolist()

    # Sidebar: Görünüm Seçimi
    chart_mode = st.sidebar.selectbox("Grafik Türü", ["Candlestick", "Heiken Ashi", "Line"])

    with st.spinner('Piyasa verileri işleniyor...'):
        data = yf.download(symbols, start=first_date, interval="1d", group_by='ticker', progress=False)

    # --- OHLC VERİ ÜRETİMİ (Sıkıştırılmış Yapı) ---
    final_ohlc = []
    for date in data.index:
        current_status = trades[trades['Date'] <= date]
        if current_status.empty: continue

        o = h = l = c = 0
        for sym in symbols:
            qty = current_status[current_status['Symbol'] == sym]['Quantity'].sum()
            if qty > 0:
                try:
                    s = data[sym].loc[date] if len(symbols) > 1 else data.loc[date]
                    o += qty * s['Open']; h += qty * s['High']
                    l += qty * s['Low']; c += qty * s['Close']
                except: continue
        
        if c > 0:
            final_ohlc.append({'Date': date, 'Open': o, 'High': h, 'Low': l, 'Close': c})

    df = pd.DataFrame(final_ohlc)
    # Tarihi grafik etiketleri için string'e çeviriyoruz (Boşlukları bitirmek için kritik adım)
    df['Date_Str'] = df['Date'].dt.strftime('%d %b %y')

    # --- ÜST DASHBOARD ---
    last_c, prev_c = df['Close'].iloc[-1], df['Close'].iloc[-2]
    diff, p_diff = last_c - prev_c, ((last_c - prev_c) / prev_c) * 100
    
    st.markdown(f"### Portföy Değeri: ${last_c:,.2f} <span style='color:{up_color if diff >=0 else down_color}; font-size:20px;'> {diff:+,.2f} ({p_diff:+.2f}%)</span>", unsafe_allow_html=True)

    # --- GRAFİK MOTORU ---
    fig = go.Figure()

    if chart_mode == "Candlestick":
        fig.add_trace(go.Candlestick(
            x=df['Date_Str'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
            increasing_line_color=up_color, decreasing_line_color=down_color,
            increasing_fillcolor=up_color, decreasing_fillcolor=down_color, name="Portfolio"
        ))
    
    elif chart_mode == "Heiken Ashi":
        ha_c = (df['Open'] + df['High'] + df['Low'] + df['Close']) / 4
        ha_o = (df['Open'].shift(1) + df['Close'].shift(1)) / 2
        ha_o.iloc[0] = df['Open'].iloc[0]
        fig.add_trace(go.Candlestick(
            x=df['Date_Str'], open=ha_o, high=df['High'], low=df['Low'], close=ha_c,
            increasing_line_color=up_color, decreasing_line_color=down_color,
            increasing_fillcolor=up_color, decreasing_fillcolor=down_color, name="HA"
        ))

    else: # Line
        fig.add_trace(go.Scatter(x=df['Date_Str'], y=df['Close'], line=dict(color='#2962FF', width=3), fill='tozeroy', name="Price"))

    # --- SIFIR BOŞLUK AYARLARI ---
    fig.update_xaxes(
        type='category', # BU SATIR TÜM BOŞLUKLARI SİLER
        tickangle=-45,
        nticks=15,
        gridcolor='#f0f0f0'
    )
    
    fig.update_layout(
        height=700, template="plotly_white",
        yaxis=dict(side="right", tickformat=",.0f", gridcolor='#f0f0f0', tickprefix="$"),
        xaxis_rangeslider_visible=False,
        margin=dict(l=0, r=50, t=10, b=10),
        hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True)
