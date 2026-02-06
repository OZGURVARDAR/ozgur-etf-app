import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import pytz

def show():
    up_color, down_color = '#26a69a', '#ef5350'
    st.subheader("🛡️ Risk & Performance Terminal (Beta & Ratio 5)")
    
    # --- SIDEBAR ---
    chart_mode = st.sidebar.selectbox("Mum Tipi", ["Candlestick", "Heiken Ashi"])
    if st.sidebar.button("🔄 Verileri Yenile"): st.cache_data.clear()

    # --- DATA LOADING ---
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

    @st.cache_data(ttl=60)
    def get_data():
        df = pd.read_csv(SHEET_URL)
        df['Date'] = pd.to_datetime(df['Date']).dt.normalize()
        trades = df[df["Symbol"] != "CASH"].sort_values('Date')
        symbols = trades["Symbol"].unique().tolist()
        # VIX ve Pazar Endeksini (Beta için) de çekelim
        all_tickers = symbols + ["^VIX", "SPY"]
        raw_data = yf.download(all_tickers, start=trades['Date'].min(), interval="1d", group_by='ticker', progress=False)
        return trades, raw_data, symbols

    trades, raw_data, symbols = get_data()

    # --- BETA HESABI ---
    # Her sembolün beta değerini (Weighted Average) hesaplayalım
    portfolio_beta = 0.0
    total_val = 0.0
    weights = {}
    
    with st.spinner('Beta değerleri hesaplanıyor...'):
        for sym in symbols:
            qty = trades[trades["Symbol"] == sym]["Quantity"].sum()
            if qty > 0:
                price = raw_data[sym]['Close'].iloc[-1]
                val = qty * price
                total_val += val
                weights[sym] = val
        
        # Basitlik için hisselerin son 1 yıllık Betasını çekelim
        for sym, val in weights.items():
            try:
                ticker_info = yf.Ticker(sym).info
                b = ticker_info.get('beta', 1.0) # Bilgi yoksa 1.0 kabul et
                portfolio_beta += (val / total_val) * b
            except: portfolio_beta += (val / total_val) * 1.0

    # --- TWR & RATIO ENGINE ---
    nav_series = []
    current_nav = 1.0 
    current_holdings = {sym: 0.0 for sym in symbols}
    all_dates = raw_data.index.sort_values()
    
    for i, date in enumerate(all_dates):
        val_start, val_end = 0.0, 0.0
        has_assets = False
        
        for sym, qty in current_holdings.items():
            if qty != 0:
                has_assets = True
                try:
                    s = raw_data[sym]
                    p_close = s['Close'].loc[date]
                    p_prev = s['Close'].loc[all_dates[i-1]] if i > 0 else s['Open'].loc[date]
                    val_start += qty * p_prev
                    val_end += qty * p_close
                except: continue
        
        if has_assets and val_start > 0:
            current_nav *= (val_end / val_start)
        
        # VIX Verisi
        vix_price = raw_data['^VIX']['Close'].loc[date]
        ratio = (current_nav * 100) / vix_price # NAV baz 100 üzerinden oran
        
        nav_series.append({
            'Date': date, 'Close': current_nav, 'VIX': vix_price, 'Ratio': ratio
        })

        for _, row in trades[trades['Date'] == date].iterrows():
            current_holdings[row['Symbol']] += row['Quantity']

    # --- SCALING ---
    df_res = pd.DataFrame(nav_series)
    scalar = total_val / df_res['Close'].iloc[-1]
    df_res['Portfolio_Value'] = df_res['Close'] * scalar
    df_res['Date_Str'] = df_res['Date'].dt.strftime('%d %b %y')

    # --- METRİKLER ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Portföy Değeri", f"${total_val:,.2f}")
    col2.metric("Portföy Betası (β)", f"{portfolio_beta:.2f}", 
                "Agresif" if portfolio_beta > 1.2 else "Dengeli")
    current_ratio = df_res['Ratio'].iloc[-1]
    col3.metric("Current Ratio (NAV/VIX)", f"{current_ratio:.2f}", 
                delta="TEHLİKE" if current_ratio < 5 else "GÜVENLİ", 
                delta_color="inverse" if current_ratio < 5 else "normal")

    # --- MULTI-CHART (Price + Ratio) ---
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=[0.7, 0.3])

    # Üst Grafik: Portföy Değeri
    fig.add_trace(go.Scatter(x=df_res['Date_Str'], y=df_res['Portfolio_Value'], 
                             line=dict(color='#2962FF', width=2), name="Portföy $"), row=1, col=1)

    # Alt Grafik: Ratio 5 Hattı
    fig.add_trace(go.Scatter(x=df_res['Date_Str'], y=df_res['Ratio'], 
                             line=dict(color='#FF9800', width=2), name="NAV/VIX Ratio"), row=2, col=1)
    
    # 5 Seviyesi Kırmızı Çizgi
    fig.add_hline(y=5, line_dash="dash", line_color="red", line_width=2, row=2, col=1)
    
    fig.update_layout(height=800, template="plotly_white", showlegend=False,
                      yaxis=dict(side="right", tickprefix="$"),
                      yaxis2=dict(side="right", title="Ratio"))
    
    st.plotly_chart(fig, use_container_width=True)
