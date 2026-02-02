import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go

def show():
    # TradingView Stil Ayarları
    up_color = '#26a69a'  # Standart TV Yeşili
    down_color = '#ef5350' # Standart TV Kırmızısı

    SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

    @st.cache_data(ttl=300)
    def load_clean_data():
        df = pd.read_csv(SHEET_URL)
        df['Date'] = pd.to_datetime(df['Date']).dt.normalize()
        return df[df["Symbol"] != "CASH"].sort_values('Date')

    trades = load_clean_data()
    symbols = trades["Symbol"].unique().tolist()
    start_date = trades['Date'].min()

    with st.spinner('Profesyonel terminal verileri yükleniyor...'):
        data = yf.download(symbols, start=start_date, interval="1d", group_by='ticker', progress=False)

    # --- PROFESYONEL OHLC HESAPLAMA ---
    daily_records = []
    for date in data.index:
        mkt_val_open = mkt_val_high = mkt_val_low = mkt_val_close = 0
        past_trades = trades[trades['Date'] <= date]
        
        for sym in symbols:
            qty = past_trades[past_trades['Symbol'] == sym]['Quantity'].sum()
            if qty > 0:
                try:
                    s_data = data[sym].loc[date] if len(symbols) > 1 else data.loc[date]
                    mkt_val_open  += qty * s_data['Open']
                    mkt_val_high  += qty * s_data['High']
                    mkt_val_low   += qty * s_data['Low']
                    mkt_val_close += qty * s_data['Close']
                except: continue
        
        if mkt_val_close > 0:
            daily_records.append({
                'Date': date, 'Open': mkt_val_open, 'High': mkt_val_high, 
                'Low': mkt_val_low, 'Close': mkt_val_close
            })

    df_ohlc = pd.DataFrame(daily_records).set_index('Date')

    # --- ÜST PANEL (DASHBOARD) ---
    current = df_ohlc['Close'].iloc[-1]
    prev = df_ohlc['Close'].iloc[-2]
    change = current - prev
    pct = (change / prev) * 100
    
    c1, c2 = st.columns([1, 3])
    with c1:
        st.markdown(f"### ${current:,.2f}")
    with c2:
        color = "green" if change >= 0 else "red"
        st.markdown(f"<p style='color:{color}; font-size:20px; margin-top:10px;'>{change:+,.2f} ({pct:+.2f}%) Today</p>", unsafe_allow_html=True)

    # --- GRAFİK OLUŞTURMA ---
    fig = go.Figure(data=[go.Candlestick(
        x=df_ohlc.index,
        open=df_ohlc['Open'],
        high=df_ohlc['High'],
        low=df_ohlc['Low'],
        close=df_ohlc['Close'],
        increasing_line_color=up_color, decreasing_line_color=down_color,
        increasing_fillcolor=up_color,  decreasing_fillcolor=down_color,
        line_width=1.5
    )])

    # --- PROFESYONEL DOKUNUŞLAR ---
    fig.update_xaxes(
        rangebreaks=[dict(bounds=["sat", "mon"])], # Hafta sonlarını kaldır
        gridcolor='#f0f0f0',
        tickformat='%d %b'
    )
    
    fig.update_yaxes(
        side="right", # Fiyat ekseni sağda
        gridcolor='#f0f0f0',
        tickprefix="$",
        tickformat=",.0f"
    )

    fig.update_layout(
        height=700,
        template="plotly_white",
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=60, t=10, b=10),
        hovermode='x unified'
    )

    st.plotly_chart(fig, use_container_width=True)
