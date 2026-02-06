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
    st.subheader("🛡️ Risk & Performance Terminal (Kilitli Yapı + Ratio/Beta)")
    
    # Sidebar Ayarları
    chart_mode = st.sidebar.selectbox("Mum Tipi", ["Candlestick", "Heiken Ashi"])
    
    tz_ny = pytz.timezone('America/New_York')
    now_ny = datetime.now(tz_ny).strftime('%H:%M')
    
    col_info, col_btn = st.columns([3, 1])
    with col_info:
        st.caption(f"ℹ️ **TWR Modu:** Gerçek performans izleniyor. Hafta sonu boşlukları temizlendi. | 🇺🇸 NY: {now_ny}")
    with col_btn:
        if st.button("🔄 Verileri Yenile"):
            st.cache_data.clear()
            st.rerun()

    # --- VERİ YÜKLEME (KİLİTLİ YAPI) ---
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

    @st.cache_data(ttl=60)
    def load_portfolio():
        df = pd.read_csv(SHEET_URL)
        df['Date'] = pd.to_datetime(df['Date']).dt.normalize()
        trades = df[df["Symbol"] != "CASH"].sort_values('Date')
        symbols = trades["Symbol"].unique().tolist()
        
        # Ekstralar: Beta ve Ratio için SPY ve VIX
        all_tickers = symbols + ["^VIX", "SPY"]
        raw_data = yf.download(all_tickers, start=trades['Date'].min(), interval="1d", progress=False)
        return trades, raw_data, symbols

    trades, raw_data, symbols = load_portfolio()
    if raw_data.empty: return

    # Veri Hazırlığı
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
            nav_open = current_nav * (v_o / v_start)
            nav_high = current_nav * (v_h / v_start)
            nav_low = current_nav * (v_l / v_start)
            nav_close = current_nav * (v_end / v_start)
            
            # Ratio 5 Hesaplama
            vix_val = closes.at[date, "^VIX"] if "^VIX" in closes.columns else 20
            ratio_val = (nav_close * 100) / vix_val
            
            nav_series.append({
                'Date': date, 'Open': nav_open, 'High': nav_high, 
                'Low': nav_low, 'Close': nav_close, 'Ratio': ratio_val
            })
            current_nav = nav_close

        day_trades = trades[trades['Date'] == date]
        for _, row in day_trades.iterrows():
            current_holdings[row['Symbol']] += row['Quantity']

    df_nav = pd.DataFrame(nav_series)
    
    # --- ÖLÇEKELEME (SCALING - Portföy Değeri Hatasını Çözen Kısım) ---
    final_market_value = sum(current_holdings[s] * closes[s].iloc[-1] for s in symbols if s in closes.columns)
    scalar = final_market_value / df_nav['Close'].iloc[-1] if not df_nav.empty else 1
    for col in ['Open', 'High', 'Low', 'Close']:
        df_nav[col] *= scalar
    
    df_nav['Date_Str'] = df_nav['Date'].dt.strftime('%d %b %y')

    # --- METRİKLER (K/Z YÜZDESİ DAHİL) ---
    last_c = df_nav['Close'].iloc[-1]
    prev_c = df_nav['Close'].iloc[-2] if len(df_nav) > 1 else last_c
    diff_pct = ((last_c - prev_c) / prev_c) * 100

    # Beta Hesabı
    spy_rets = closes['SPY'].pct_change()
    pf_rets = df_nav['Close'].pct_change()
    beta = pf_rets.cov(spy_rets) / spy_rets.var() if len(pf_rets) > 1 else 1.0

    c1, c2, c3 = st.columns(3)
    c1.metric("Portföy Değeri", f"${last_c:,.2f}", f"{diff_pct:+.2f}%")
    c2.metric("Portföy Betası (β)", f"{beta:.2f}")
    
    cur_ratio = df_nav['Ratio'].iloc[-1]
    c3.metric("Ratio (NAV/VIX)", f"{cur_ratio:.2f}", "LIMIT 5.0", 
              delta_color="normal" if cur_ratio > 5 else "inverse")

    # --- GRAFİK (BOŞLUKSUZ & İKİ PANELLİ) ---
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])

    if chart_mode == "Heiken Ashi":
        # Kilitli kodundaki HA mantığı
        ha_close = (df_nav['Open'] + df_nav['High'] + df_nav['Low'] + df_nav['Close']) / 4
        ha_open = [(df_nav['Open'].iloc[0] + df_nav['Close'].iloc[0]) / 2]
        for k in range(1, len(df_nav)):
            ha_open.append((ha_open[k-1] + ha_close.iloc[k-1]) / 2)
        
        fig.add_trace(go.Candlestick(
            x=df_nav['Date_Str'], open=ha_open, high=df_nav['High'], low=df_nav['Low'], close=ha_close,
            increasing_line_color=up_color, decreasing_line_color=down_color, name="HA"
        ), row=1, col=1)
    else:
        fig.add_trace(go.Candlestick(
            x=df_nav['Date_Str'], open=df_nav['Open'], high=df_nav['High'], low=df_nav['Low'], close=df_nav['Close'],
            increasing_line_color=up_color, decreasing_line_color=down_color, name="Standart"
        ), row=1, col=1)

    # Ratio Paneli (Alt Grafik)
    fig.add_trace(go.Scatter(
        x=df_nav['Date_Str'], y=df_nav['Ratio'], 
        line=dict(color='#FF6D00', width=2), name="Ratio"
    ), row=2, col=1)
    
    fig.add_hline(y=5, line_dash="dash", line_color="red", row=2, col=1, annotation_text="Limit 5.0")

    fig.update_layout(
        height=750, template="plotly_white", showlegend=False,
        xaxis=dict(type='category', nticks=20), # BOŞLUKLARI KALDIRAN KISIM
        xaxis2=dict(type='category', nticks=20),
        xaxis_rangeslider_visible=False,
        margin=dict(l=20, r=20, t=30, b=20)
    )
    
    st.plotly_chart(fig, use_container_width=True)
