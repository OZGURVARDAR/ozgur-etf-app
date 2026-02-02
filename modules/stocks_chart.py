import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def show():
    st.subheader("🛡️ Portfolio ETF Terminal (TradingView Style)")

    # --- SIDEBAR CONTROLS ---
    chart_type = st.sidebar.selectbox("Grafik Türü", ["Candlestick", "Line", "Heiken Ashi"])
    ema_fast = st.sidebar.number_input("Hızlı EMA", value=20)
    ema_slow = st.sidebar.number_input("Yavaş EMA", value=50)
    show_rsi = st.sidebar.checkbox("RSI Göster", value=True)

    SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

    @st.cache_data(ttl=300)
    def load_and_fix_data():
        df = pd.read_csv(SHEET_URL)
        df['Date'] = pd.to_datetime(df['Date']).dt.normalize()
        # Sadece hisse alım-satımlarını al
        trades = df[df["Symbol"] != "CASH"].sort_values('Date').copy()
        return trades

    trades = load_and_fix_data()
    symbols = trades["Symbol"].unique().tolist()
    start_date = trades['Date'].min() # 18.11.2025

    # --- DATA FETCHING ---
    with st.spinner('Piyasa verileri senkronize ediliyor...'):
        data = yf.download(symbols, start=start_date, interval="1d", group_by='ticker', progress=False)

    # --- NAV CALCULATION (THE ETF ENGINE) ---
    all_dates = data.index.normalize()
    nav_results = []
    current_holdings = {sym: 0 for sym in symbols}
    current_nav = 100.0  # Başlangıç Endeksi

    for i, date in enumerate(all_dates):
        # 1. O gün yapılan işlemleri ekle
        todays_trades = trades[trades['Date'] == date]
        new_investment_today = 0
        for _, row in todays_trades.iterrows():
            current_holdings[row['Symbol']] += row['Quantity']
            new_investment_today += row['Quantity'] * row['Price']

        # 2. Portföyün bugünkü değerini hesapla
        daily_mkt_val = 0
        for sym, qty in current_holdings.items():
            if qty > 0:
                try:
                    price = data[sym]['Close'].loc[date] if len(symbols) > 1 else data['Close'].loc[date]
                    if pd.isna(price): price = data[sym]['Close'].asof(date)
                    daily_mkt_val += qty * price
                except: continue
        
        # 3. Getiri Hesapla (Yeni yatırımı toplam değerden düşerek performansı izole et)
        if i > 0:
            prev_val = nav_results[-1]['mkt_val']
            if prev_val > 0:
                # Saf performans = (Bugünkü Değer - Yeni Eklenen Para) / Dünkü Değer
                returns = (daily_mkt_val - new_investment_today) / prev_val
                current_nav *= returns

        nav_results.append({'Date': date, 'NAV': current_nav, 'mkt_val': daily_mkt_val})

    df_nav = pd.DataFrame(nav_results).set_index('Date')
    df_ohlc = df_nav['NAV'].resample('B').ohlc().dropna()

    # --- INDICATORS ---
    df_ohlc['EMA_F'] = df_ohlc['close'].ewm(span=ema_fast).mean()
    df_ohlc['EMA_S'] = df_ohlc['close'].ewm(span=ema_slow).mean()

    # --- CHARTING ---
    rows = 2 if show_rsi else 1
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3] if show_rsi else [1])

    # Tarih formatını temizle
    date_labels = df_ohlc.index.strftime('%d %b %y')

    if chart_type == "Candlestick":
        fig.add_trace(go.Candlestick(x=date_labels, open=df_ohlc['open'], high=df_ohlc['high'], low=df_ohlc['low'], close=df_ohlc['close'], name="Portfolio NAV"), row=1, col=1)
    elif chart_type == "Heiken Ashi":
        ha_c = (df_ohlc['open'] + df_ohlc['high'] + df_ohlc['low'] + df_ohlc['close']) / 4
        ha_o = (df_ohlc['open'].shift(1) + df_ohlc['close'].shift(1)) / 2
        ha_o.iloc[0] = df_ohlc['open'].iloc[0]
        fig.add_trace(go.Candlestick(x=date_labels, open=ha_o, high=df_ohlc['high'], low=df_ohlc['low'], close=ha_c, name="HA NAV"), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(x=date_labels, y=df_ohlc['close'], line=dict(color='#2962FF', width=3), name="Portfolio Value"), row=1, col=1)

    # EMA'lar
    fig.add_trace(go.Scatter(x=date_labels, y=df_ohlc['EMA_F'], name=f"EMA{ema_fast}", line=dict(color='orange', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=date_labels, y=df_ohlc['EMA_S'], name=f"EMA{ema_slow}", line=dict(color='blue', width=1)), row=1, col=1)

    # RSI
    if show_rsi:
        delta = df_ohlc['close'].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + (gain/loss)))
        fig.add_trace(go.Scatter(x=date_labels, y=rsi, name="RSI", line=dict(color='purple')), row=2, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

    # Final Düzenlemeler
    fig.update_xaxes(type='category', nticks=10)
    fig.update_yaxes(title_text="NAV (Baz 100)", tickformat=".2f", row=1, col=1)
    fig.update_layout(height=800, template="plotly_white", xaxis_rangeslider_visible=False, margin=dict(l=50,r=20,t=20,b=20))

    st.plotly_chart(fig, use_container_width=True)

    # --- ÖZET PANELİ ---
    c1, c2 = st.columns(2)
    current_nav_val = df_ohlc['close'].iloc[-1]
    total_perf = (current_nav_val - 100)
    c1.metric("ETF Birim Değeri", f"{current_nav_val:.2f}", f"{total_perf:.2f}%")
    c2.write("💡 Grafik 100 puanın ne kadar üzerindeyse, stratejiniz o kadar kârdadır.")

if __name__ == "__main__":
    show()
