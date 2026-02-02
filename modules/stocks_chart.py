import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go

def show():
    # --- STİL VE RENKLER ---
    up_color, down_color = '#26a69a', '#ef5350'
    
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

    @st.cache_data(ttl=300)
    def load_data():
        df = pd.read_csv(SHEET_URL)
        df['Date'] = pd.to_datetime(df['Date']).dt.normalize()
        # Sadece hisseleri ve İLK işlem tarihinden sonrasını al
        trades = df[df["Symbol"] != "CASH"].sort_values('Date')
        return trades, trades['Date'].min()

    trades, first_trade_date = load_data()
    symbols = trades["Symbol"].unique().tolist()

    # Sidebar Seçimleri
    st.sidebar.subheader("Grafik Ayarları")
    chart_mode = st.sidebar.selectbox("Grafik Türü", ["Candlestick", "Heiken Ashi", "Line"])

    with st.spinner('Piyasa verileri temizleniyor...'):
        # Boşluğu önlemek için tam olarak İLK işlem tarihinde başlatıyoruz
        data = yf.download(symbols, start=first_trade_date, interval="1d", group_by='ticker', progress=False)

    # --- OHLC VERİ ÜRETİMİ ---
    ohlc_list = []
    for date in data.index:
        # Sadece o güne kadar olan alımları hesapla
        current_status = trades[trades['Date'] <= date]
        if current_status.empty: continue # Eğer o gün henüz alım yapılmadıysa pas geç (Boşluğu önler)

        o = h = l = c = 0
        for sym in symbols:
            qty = current_status[current_status['Symbol'] == sym]['Quantity'].sum()
            if qty > 0:
                try:
                    s = data[sym].loc[date] if len(symbols) > 1 else data.loc[date]
                    o += qty * s['Open']
                    h += qty * s['High']
                    l += qty * s['Low']
                    c += qty * s['Close']
                except: continue
        
        if c > 0:
            ohlc_list.append({'Date': date, 'Open': o, 'High': h, 'Low': l, 'Close': c})

    df_final = pd.DataFrame(ohlc_list).set_index('Date')

    # --- DASHBOARD PANELİ ---
    last_val = df_final['Close'].iloc[-1]
    prev_val = df_final['Close'].iloc[-2]
    d_val = last_val - prev_val
    d_pct = (d_val / prev_val) * 100
    
    st.markdown(f"### Portföy Değeri: ${last_val:,.2f} <span style='color:{'#26a69a' if d_val >=0 else '#ef5350'}; font-size:18px;'> {d_val:+,.2f} ({d_pct:+.2f}%)</span>", unsafe_allow_html=True)

    # --- GRAFİK OLUŞTURMA ---
    fig = go.Figure()

    if chart_mode == "Candlestick":
        fig.add_trace(go.Candlestick(x=df_final.index, open=df_final['Open'], high=df_final['High'], 
                                     low=df_final['Low'], close=df_final['Close'],
                                     increasing_line_color=up_color, decreasing_line_color=down_color,
                                     name="Candle"))
    
    elif chart_mode == "Heiken Ashi":
        # HA Hesaplama
        ha_close = (df_final['Open'] + df_final['High'] + df_final['Low'] + df_final['Close']) / 4
        ha_open = (df_final['Open'].shift(1) + df_final['Close'].shift(1)) / 2
        ha_open.iloc[0] = df_final['Open'].iloc[0]
        fig.add_trace(go.Candlestick(x=df_final.index, open=ha_open, high=df_final['High'], 
                                     low=df_final['Low'], close=ha_close,
                                     increasing_line_color=up_color, decreasing_line_color=down_color,
                                     name="Heiken Ashi"))

    else: # Line Chart
        fig.add_trace(go.Scatter(x=df_final.index, y=df_final['Close'], line=dict(color='#2962FF', width=3), 
                                 fill='tozeroy', name="Line"))

    # --- BOŞLUKLARI VE HAFTA SONLARINI SİLME ---
    fig.update_xaxes(
        rangebreaks=[dict(bounds=["sat", "mon"])], # Hafta sonu boşluklarını sil
        type='date',
        gridcolor='#f0f0f0'
    )
    
    fig.update_layout(
        height=700, template="plotly_white",
        yaxis=dict(side="right", tickformat=",.0f", gridcolor='#f0f0f0'),
        xaxis_rangeslider_visible=False,
        margin=dict(l=0, r=50, t=10, b=10),
        hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True)
