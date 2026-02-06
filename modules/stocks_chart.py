import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import pytz

def show():
    # --- AYARLAR ---
    up_color, down_color = '#26a69a', '#ef5350'
    st.subheader("🛡️ Risk & Performance Terminal")
    
    # --- SIDEBAR KONTROLLERİ ---
    st.sidebar.markdown("### 🛠️ Terminal Ayarları")
    chart_mode = st.sidebar.selectbox("Mum Tipi", ["Candlestick", "Heiken Ashi"])
    show_ratio = st.sidebar.checkbox("Ratio Panelini Göster (NAV/VIX)", value=True)
    
    if st.sidebar.button("🔄 Verileri Yenile"):
        st.cache_data.clear()
        st.rerun()

    # --- VERİ YÜKLEME ---
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

    @st.cache_data(ttl=60)
    def load_bundle():
        df = pd.read_csv(SHEET_URL)
        df['Date'] = pd.to_datetime(df['Date']).dt.normalize()
        trades = df[df["Symbol"] != "CASH"].sort_values('Date')
        symbols = trades["Symbol"].unique().tolist()
        
        # Beta ve Ratio için SPY ve VIX'i de alıyoruz
        all_tickers = symbols + ["^VIX", "SPY"]
        raw_data = yf.download(all_tickers, start=trades['Date'].min(), interval="1d", progress=False)
        return trades, raw_data, symbols

    trades, raw_data, symbols = load_bundle()
    if raw_data.empty: return

    closes = raw_data['Close'].ffill()
    opens = raw_data['Open'].ffill()
    highs = raw_data['High'].ffill()
    lows = raw_data['Low'].ffill()

    # --- TWR MOTORU (KİLİTLİ YAPI) ---
    nav_series = []
    current_nav = 1.0
    current_holdings = {sym: 0.0 for sym in symbols}
    dates = closes.index.sort_values()

    for i, date in enumerate(dates):
        v_start, v_end, v_o, v_h, v_l = 0.0, 0.0, 0.0, 0.0, 0.0
        active = False
        
        for sym in symbols:
            if current_holdings[sym] > 0 and sym in closes.columns:
                active = True
                p_prev = closes[sym].iloc[i-1] if i > 0 else opens.at[date, sym]
                qty = current_holdings[sym]
                v_start += qty * p_prev
                v_end += qty * closes.at[date, sym]
                v_o += qty * opens.at[date, sym]
                v_h += qty * highs.at[date, sym]
                v_l += qty * lows.at[date, sym]
        
        if active and v_start > 0:
            nav_close = current_nav * (v_end / v_start)
            vix_val = closes.at[date, "^VIX"] if "^VIX" in closes.columns else 20
            
            nav_series.append({
                'Date': date, 
                'Open': current_nav * (v_o / v_start), 
                'High': current_nav * (v_h / v_start), 
                'Low': current_nav * (v_l / v_start), 
                'Close': nav_close,
                'Ratio': (nav_close * 100) / vix_val
            })
            current_nav = nav_close

        day_trades = trades[trades['Date'] == date]
        for _, row in day_trades.iterrows():
            current_holdings[row['Symbol']] += row['Quantity']

    df_nav = pd.DataFrame(nav_series)
    
    # --- SCALING (Doğru Portföy Değeri) ---
    final_market_value = sum(current_holdings[s] * closes[s].iloc[-1] for s in symbols if s in closes.columns)
    scalar = final_market_value / df_nav['Close'].iloc[-1] if not df_nav.empty else 1
    for col in ['Open', 'High', 'Low', 'Close']:
        df_nav[col] *= scalar
    
    # Hafta sonu boşluklarını kaldırmak için Date_Str
    df_nav['Date_Str'] = df_nav['Date'].dt.strftime('%d %b %y')

    # --- METRİKLER (K/Z Yüzdesi Dahil) ---
    last_c = df_nav['Close'].iloc[-1]
    prev_c = df_nav['Close'].iloc[-2] if len(df_nav) > 1 else last_c
    diff_pct = ((last_c - prev_c) / prev_c) * 100

    # Portföy Betası (SPY'a kıyasla)
    spy_rets = closes['SPY'].pct_change().dropna()
    pf_rets = df_nav['Close'].pct_change().dropna()
    common = pf_rets.index.intersection(spy_rets.index)
    beta = pf_rets[common].cov(spy_rets[common]) / spy_rets[common].var() if len(common) > 1 else 1.0

    c1, c2, c3 = st.columns(3)
    c1.metric("Portföy Değeri", f"${last_c:,.2f}", f"{diff_pct:+.2f}%")
    c2.metric("Portföy Betası (β)", f"{beta:.2f}")
    
    cur_ratio = df_nav['Ratio'].iloc[-1]
    c3.metric("Current Ratio", f"{cur_ratio:.2f}", 
              delta="GÜVENLİ" if cur_ratio > 5 else "RİSKLİ", 
              delta_color="normal" if cur_ratio > 5 else "inverse")

    # --- GRAFİK YAPILANDIRMASI ---
    if show_ratio:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
    else:
        fig = go.Figure()

    # Heiken Ashi veya Standart
    if chart_mode == "Heiken Ashi":
        ha_close = (df_nav['Open'] + df_nav['High'] + df_nav['Low'] + df_nav['Close']) / 4
        ha_open = [(df_nav['Open'].iloc[0] + df_nav['Close'].iloc[0]) / 2]
        for k in range(1, len(df_nav)):
            ha_open.append((ha_open[k-1] + ha_close.iloc[k-1]) / 2)
        
        trace = go.Candlestick(
            x=df_nav['Date_Str'], open=ha_open, high=df_nav['High'], low=df_nav['Low'], close=ha_close,
            increasing_line_color=up_color, decreasing_line_color=down_color, name="HA"
        )
    else:
        trace = go.Candlestick(
            x=df_nav['Date_Str'], open=df_nav['Open'], high=df_nav['High'], low=df_nav['Low'], close=df_nav['Close'],
            increasing_line_color=up_color, decreasing_line_color=down_color, name="Standart"
        )

    if show_ratio:
        fig.add_trace(trace, row=1, col=1)
        # Ratio Paneli (Alt Grafik)
        fig.add_trace(go.Scatter(
            x=df_nav['Date_Str'], y=df_nav['Ratio'], 
            line=dict(color='#FF6D00', width=2), name="Ratio"
        ), row=2, col=1)
        fig.add_hline(y=5, line_dash="dash", line_color="red", row=2, col=1)
    else:
        fig.add_trace(trace)

    fig.update_layout(
        height=800 if show_ratio else 500,
        template="plotly_white",
        xaxis_rangeslider_visible=False,
        xaxis=dict(type='category', nticks=20),
        showlegend=False
    )
    if show_ratio:
        fig.update_xaxes(type='category', row=2, col=1)

    st.plotly_chart(fig, use_container_width=True)
