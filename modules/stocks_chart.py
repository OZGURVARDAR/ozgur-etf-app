import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime
import pytz

def show():
    # --- AYARLAR VE STİL ---
    up_color, down_color = '#26a69a', '#ef5350'
    st.subheader("🚀 Ultimate TWR Portfolio Terminal")
    
    # Sidebar
    st.sidebar.markdown("### 🎨 Grafik Ayarları")
    chart_mode = st.sidebar.selectbox("Mum Tipi", ["Candlestick", "Heiken Ashi"])
    
    tz_ny = pytz.timezone('America/New_York')
    now_ny = datetime.now(tz_ny).strftime('%H:%M')
    
    col_info, col_btn = st.columns([3, 1])
    with col_info:
        st.caption(f"ℹ️ **TWR Modu:** Alım/Satımlardan arındırılmış gerçek performans. | 🇺🇸 NY: {now_ny}")
    with col_btn:
        if st.button("🔄 Canlı Veri Yenile"):
            st.cache_data.clear()
            st.rerun()

    # --- VERİ YÜKLEME ---
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

    @st.cache_data(ttl=60)
    def load_portfolio():
        df = pd.read_csv(SHEET_URL)
        df['Date'] = pd.to_datetime(df['Date']).dt.normalize()
        trades = df[df["Symbol"] != "CASH"].sort_values('Date')
        symbols = trades["Symbol"].unique().tolist()
        
        # Sadece hisseler + Beta için SPY çekiyoruz
        all_tickers = symbols + ["SPY"]
        raw_data = yf.download(all_tickers, start=trades['Date'].min(), interval="1d", progress=False)
        return trades, raw_data, symbols

    trades, raw_data, symbols = load_portfolio()
    if raw_data.empty: return

    # Fiyat verilerini hazırla
    closes = raw_data['Close'].ffill()
    opens = raw_data['Open'].ffill()
    highs = raw_data['High'].ffill()
    lows = raw_data['Low'].ffill()

    # --- TWR MOTORU (DOKUNULMADI) ---
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
            nav_series.append({
                'Date': date,
                'Open': current_nav * (v_o / v_start),
                'High': current_nav * (v_h / v_start),
                'Low': current_nav * (v_l / v_start),
                'Close': current_nav * (v_end / v_start)
            })
            current_nav = nav_series[-1]['Close']

        day_trades = trades[trades['Date'] == date]
        for _, row in day_trades.iterrows():
            current_holdings[row['Symbol']] += row['Quantity']

    df_nav = pd.DataFrame(nav_series)

    # --- SCALING (DOKUNULMADI) ---
    final_market_value = sum(current_holdings[s] * closes[s].iloc[-1] for s in symbols if s in closes.columns)
    scalar = final_market_value / df_nav['Close'].iloc[-1] if not df_nav.empty else 1.0
    for col in ['Open', 'High', 'Low', 'Close']:
        df_nav[col] *= scalar
    
    df_nav['Date_Str'] = df_nav['Date'].dt.strftime('%d %b %y')

    # --- METRİKLER (BETA EKLENDİ) ---
    last_val = df_nav['Close'].iloc[-1]
    prev_val = df_nav['Close'].iloc[-2] if len(df_nav) > 1 else last_val
    diff_pct = ((last_val - prev_val) / prev_val) * 100

    # Beta Hesaplama
    spy_rets = closes['SPY'].pct_change().dropna()
    pf_rets = df_nav['Close'].pct_change().dropna()
    common = pf_rets.index.intersection(spy_rets.index)
    beta_val = pf_rets[common].cov(spy_rets[common]) / spy_rets[common].var() if len(common) > 1 else 1.0

    m1, m2 = st.columns(2)
    m1.metric("Portföy Değeri", f"${last_val:,.2f}", f"{diff_pct:+.2f}%")
    m2.metric("Portföy Betası (β)", f"{beta_val:.2f}", help="Pazar (SPY) ile olan korelasyonunuz.")

    # --- GRAFİK ---
    fig = go.Figure()

    if chart_mode == "Heiken Ashi":
        ha_close = (df_nav['Open'] + df_nav['High'] + df_nav['Low'] + df_nav['Close']) / 4
        ha_open = [(df_nav['Open'].iloc[0] + df_nav['Close'].iloc[0]) / 2]
        for i in range(1, len(df_nav)):
            ha_open.append((ha_open[i-1] + ha_close.iloc[i-1]) / 2)
        
        df_nav['HA_Open'], df_nav['HA_Close'] = ha_open, ha_close
        df_nav['HA_High'] = df_nav[['High', 'HA_Open', 'HA_Close']].max(axis=1)
        df_nav['HA_Low'] = df_nav[['Low', 'HA_Open', 'HA_Close']].min(axis=1)

        fig.add_trace(go.Candlestick(
            x=df_nav['Date_Str'], open=df_nav['HA_Open'], high=df_nav['HA_High'], 
            low=df_nav['HA_Low'], close=df_nav['HA_Close'],
            increasing_line_color=up_color, decreasing_line_color=down_color, name="HA"
        ))
    else:
        fig.add_trace(go.Candlestick(
            x=df_nav['Date_Str'], open=df_nav['Open'], high=df_nav['High'], 
            low=df_nav['Low'], close=df_nav['Close'],
            increasing_line_color=up_color, decreasing_line_color=down_color, name="Standart"
        ))

    # --- SON FİYAT ÇİZGİSİ VE STİL ---
    fig.add_hline(
        y=last_val, line_dash="dot", line_color="red", line_width=1.5,
        annotation_text=f"ŞU AN: ${last_val:,.2f}", 
        annotation_position="right",
        annotation_font=dict(color="red", size=12)
    )

    fig.update_layout(
        height=650,
        template="plotly_white",
        xaxis_rangeslider_visible=False,
        xaxis=dict(type='category', nticks=20), # Boşlukları kaldıran ayar
        yaxis=dict(side='right', tickformat='$,.2f'), # Sağ eksen ve tam rakam
        showlegend=False,
        margin=dict(l=10, r=60, t=10, b=10)
    )

    st.plotly_chart(fig, use_container_width=True)
