import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import pytz

def show():
    # --- AYARLAR VE STİL ---
    up_color, down_color = '#26a69a', '#ef5350'
    st.subheader("🛡️ Ultimate TWR Portfolio Terminal")
    
    # --- SIDEBAR AYARLARI ---
    st.sidebar.markdown("### 🎨 Terminal Ayarları")
    chart_mode = st.sidebar.selectbox("Mum Tipi", ["Candlestick", "Heiken Ashi"])
    show_ratio = st.sidebar.checkbox("Ratio Panelini Göster (NAV/VIX)", value=True)
    
    if st.sidebar.button("🔄 Verileri Yenile"):
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
        # VIX ve Beta için SPY ekle
        all_tickers = symbols + ["^VIX", "SPY"]
        raw_data = yf.download(all_tickers, start=trades['Date'].min(), interval="1d", progress=False)
        return trades, raw_data, symbols

    trades, raw_data, symbols = load_portfolio()
    if raw_data.empty: return

    # Verileri ayrıştır ve boşlukları doldur
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
    
    # --- SCALING (Portföy Değeri Hesaplama) ---
    final_market_value = sum(current_holdings[s] * closes[s].iloc[-1] for s in symbols if s in closes.columns)
    scalar = final_market_value / df_nav['Close'].iloc[-1] if not df_nav.empty else 1
    for col in ['Open', 'High', 'Low', 'Close']:
        df_nav[col] *= scalar
    
    # Boşluksuz grafik için Date_Str
    df_nav['Date_Str'] = df_nav['Date'].dt.strftime('%d %b %y')

    # --- METRİKLER (P/L % Dahil) ---
    last_val = df_nav['Close'].iloc[-1]
    prev_val = df_nav['Close'].iloc[-2] if len(df_nav) > 1 else last_val
    diff_pct = ((last_val - prev_val) / prev_val) * 100

    # Beta Hesabı (SPY korelasyonu)
    spy_rets = closes['SPY'].pct_change().dropna()
    pf_rets = df_nav['Close'].pct_change().dropna()
    common = pf_rets.index.intersection(spy_rets.index)
    beta_val = pf_rets[common].cov(spy_rets[common]) / spy_rets[common].var() if len(common) > 1 else 1.0

    c1, c2, c3 = st.columns(3)
    c1.metric("Portföy Değeri", f"${last_val:,.2f}", f"{diff_pct:+.2f}%")
    c2.metric("Portföy Betası (β)", f"{beta_val:.2f}")
    
    cur_ratio = df_nav['Ratio'].iloc[-1]
    c3.metric("Ratio (NAV/VIX)", f"{cur_ratio:.2f}", 
              delta="GÜVENLİ" if cur_ratio > 5 else "RİSKLİ", 
              delta_color="normal" if cur_ratio > 5 else "inverse")

    # --- GRAFİK YAPISI (SAĞ EKSEN VE BOŞLUKSUZ) ---
    if show_ratio:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])
    else:
        fig = go.Figure()

    # Heiken Ashi mi Standart mı?
    if chart_mode == "Heiken Ashi":
        ha_close = (df_nav['Open'] + df_nav['High'] + df_nav['Low'] + df_nav['Close']) / 4
        ha_open = [(df_nav['Open'].iloc[0] + df_nav['Close'].iloc[0]) / 2]
        for k in range(1, len(df_nav)):
            ha_open.append((ha_open[k-1] + ha_close.iloc[k-1]) / 2)
        main_trace = go.Candlestick(x=df_nav['Date_Str'], open=ha_open, high=df_nav['High'], 
                                    low=df_nav['Low'], close=ha_close, name="HA",
                                    increasing_line_color=up_color, decreasing_line_color=down_color)
    else:
        main_trace = go.Candlestick(x=df_nav['Date_Str'], open=df_nav['Open'], high=df_nav['High'], 
                                    low=df_nav['Low'], close=df_nav['Close'], name="Standart",
                                    increasing_line_color=up_color, decreasing_line_color=down_color)

    if show_ratio:
        fig.add_trace(main_trace, row=1, col=1)
        fig.add_trace(go.Scatter(x=df_nav['Date_Str'], y=df_nav['Ratio'], name="Ratio", 
                                 line=dict(color='#FF6D00', width=2)), row=2, col=1)
        fig.add_hline(y=5, line_dash="dash", line_color="red", row=2, col=1)
        # Sağ eksen ayarı
        fig.update_layout(yaxis=dict(side='right', tickformat='$,.2f'))
        fig.update_xaxes(type='category', row=2, col=1)
    else:
        fig.add_trace(main_trace)
        fig.update_layout(yaxis=dict(side='right', tickformat='$,.2f'))

    # --- KIRMIZI NOKTALI SON FİYAT ÇİZGİSİ ---
    fig.add_hline(y=last_val, line_dash="dot", line_color="red", line_width=1.5,
                  annotation_text=f"ŞU AN: ${last_val:,.2f}", 
                  annotation_position="right",
                  annotation_font=dict(color="red", size=12))

    fig.update_layout(
        height=800 if show_ratio else 600,
        template="plotly_white",
        xaxis_rangeslider_visible=False,
        xaxis=dict(type='category', nticks=20),
        showlegend=False,
        margin=dict(l=20, r=60, t=30, b=20)
    )

    st.plotly_chart(fig, use_container_width=True)
