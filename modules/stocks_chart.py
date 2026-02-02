import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def show():
    st.subheader("🛡️ Portfolio Performance Index (Base 100)")

    # --- SIDEBAR ---
    chart_mode = st.sidebar.selectbox("Grafik Türü", ["Candlestick", "Line", "Heiken Ashi"])
    show_rsi = st.sidebar.checkbox("RSI Göster", value=True)

    SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

    @st.cache_data(ttl=300)
    def load_data():
        df = pd.read_csv(SHEET_URL)
        df['Date'] = pd.to_datetime(df['Date']).dt.normalize()
        return df[df["Symbol"] != "CASH"].sort_values('Date')

    trades = load_data()
    symbols = trades["Symbol"].unique().tolist()
    first_trade_date = trades['Date'].min() # 18.11.2025

    # --- DATA FETCHING ---
    with st.spinner('Fiyatlar güncelleniyor...'):
        # Veriyi ilk işlem tarihinden başlatıyoruz
        data = yf.download(symbols, start=first_trade_date, interval="1d", group_by='ticker', progress=False)

    # --- PORTFOLIO CALCULATION ---
    daily_values = []
    all_trading_days = data.index.normalize()

    for date in all_trading_days:
        mkt_val = 0.0
        # O tarihe kadar sahip olunan toplam adetleri hesapla
        current_status = trades[trades['Date'] <= date]
        
        for sym in symbols:
            sym_trades = current_status[current_status['Symbol'] == sym]
            if not sym_trades.empty:
                qty = sym_trades['Quantity'].sum()
                try:
                    # O günkü kapanış fiyatı
                    price_series = data[sym]['Close'] if len(symbols) > 1 else data['Close']
                    price = price_series.loc[date]
                    if pd.isna(price): price = price_series.asof(date) # Tatilse son fiyat
                    mkt_val += qty * price
                except: continue
        
        if mkt_val > 0:
            daily_values.append({'Date': date, 'MarketValue': mkt_val})

    df_results = pd.DataFrame(daily_values).set_index('Date')

    # --- INDEXING (BASE 100) ---
    # İlk günkü toplam değeri 100'e eşitliyoruz
    base_val = df_results['MarketValue'].iloc[0]
    df_results['NAV'] = (df_results['MarketValue'] / base_val) * 100

    # Resample to OHLC (Günlük Mumlar)
    df_ohlc = df_results['NAV'].resample('B').ohlc().dropna()

    # --- CHARTING ---
    rows = 2 if show_rsi else 1
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.05)
    
    # X ekseni etiketlerini temizle
    x_axis = df_ohlc.index.strftime('%Y-%m-%d')

    if chart_mode == "Candlestick":
        fig.add_trace(go.Candlestick(x=x_axis, open=df_ohlc['open'], high=df_ohlc['high'], 
                                     low=df_ohlc['low'], close=df_ohlc['close'], name="Index"), row=1, col=1)
    elif chart_mode == "Heiken Ashi":
        ha_c = (df_ohlc['open'] + df_ohlc['high'] + df_ohlc['low'] + df_ohlc['close']) / 4
        ha_o = (df_ohlc['open'].shift(1) + df_ohlc['close'].shift(1)) / 2
        ha_o.iloc[0] = df_ohlc['open'].iloc[0]
        fig.add_trace(go.Candlestick(x=x_axis, open=ha_o, high=df_ohlc['high'], low=df_ohlc['low'], close=ha_c, name="HA Index"), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(x=x_axis, y=df_ohlc['close'], line=dict(color='#2962FF', width=2), name="Index Line"), row=1, col=1)

    # RSI (Opsiyonel)
    if show_rsi:
        delta = df_ohlc['close'].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + (gain/loss)))
        fig.add_trace(go.Scatter(x=x_axis, y=rsi, name="RSI", line=dict(color='purple')), row=2, col=1)

    # Format
    fig.update_layout(height=700, template="plotly_white", xaxis_rangeslider_visible=False)
    fig.update_yaxes(title_text="Portfolio Index (Start=100)", tickformat=".2f", row=1, col=1)
    fig.update_xaxes(type='category', nticks=15)
    
    st.plotly_chart(fig, use_container_width=True)

    # Doğrulama Mesajı
    current_index = df_ohlc['close'].iloc[-1]
    st.success(f"Güncel Endeks Değeri: {current_index:.2f} (Bu, başlangıçtan beri %{current_index-100:.2f} kârda olduğunuzu gösterir.)")
