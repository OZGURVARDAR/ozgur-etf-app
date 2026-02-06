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
    st.subheader("🛡️ Risk & Performance Terminal (V3.1)")
    
    # Sağ üst köşeye son güncelleme saati
    tz_ny = pytz.timezone('America/New_York')
    now_ny = datetime.now(tz_ny).strftime('%H:%M')
    
    col_info, col_btn = st.columns([3, 1])
    with col_info:
        st.caption(f"ℹ️ **TWR Modu:** Portföy performansı ve Risk Oranı (Ratio 5) izleniyor. | 🇺🇸 NY: {now_ny}")
    with col_btn:
        if st.button("🔄 Verileri Yenile"):
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
        
        # VIX ve SPY (Beta için) ekleyerek toplu indir
        all_tickers = symbols + ["^VIX", "SPY"]
        raw_data = yf.download(all_tickers, start=trades['Date'].min(), interval="1d", progress=False)
        return trades, raw_data, symbols

    trades, raw_data, symbols = load_bundle()

    if raw_data.empty:
        st.error("Veri alınamadı, lütfen bağlantıyı kontrol edin.")
        return

    # Verileri ayrıştır (MultiIndex kontrolü ile)
    closes = raw_data['Close'].ffill()
    opens = raw_data['Open'].ffill()
    highs = raw_data['High'].ffill()
    lows = raw_data['Low'].ffill()

    # --- TWR & RATIO MOTORU ---
    nav_series = []
    current_nav = 1.0
    current_holdings = {sym: 0.0 for sym in symbols}
    dates = closes.index.sort_values()

    for i, date in enumerate(dates):
        v_start, v_end, v_o, v_h, v_l = 0.0, 0.0, 0.0, 0.0, 0.0
        has_assets = False
        
        for sym in symbols:
            if current_holdings[sym] > 0 and sym in closes.columns:
                has_assets = True
                p_prev = closes[sym].iloc[i-1] if i > 0 else opens.at[date, sym]
                qty = current_holdings[sym]
                
                v_start += qty * p_prev
                v_end += qty * closes.at[date, sym]
                v_o += qty * opens.at[date, sym]
                v_h += qty * highs.at[date, sym]
                v_l += qty * lows.at[date, sym]
        
        if has_assets and v_start > 0:
            daily_ret = v_end / v_start
            nav_open = current_nav * (v_o / v_start)
            nav_high = current_nav * (v_h / v_start)
            nav_low = current_nav * (v_l / v_start)
            nav_close = current_nav * daily_ret
            
            # Ratio 5 Hesaplama (NAV * 100 / VIX)
            vix_val = closes.at[date, "^VIX"] if "^VIX" in closes.columns else 20
            ratio = (nav_close * 100) / vix_val if vix_val > 0 else 0

            nav_series.append({
                'Date': date, 'Open': nav_open, 'High': nav_high, 
                'Low': nav_low, 'Close': nav_close, 'Ratio': ratio
            })
            current_nav = nav_close

        # İşlemleri güncelle
        day_trades = trades[trades['Date'] == date]
        for _, row in day_trades.iterrows():
            current_holdings[row['Symbol']] += row['Quantity']

    df_nav = pd.DataFrame(nav_series)
    if df_nav.empty:
        st.warning("Görüntülenecek veri yok.")
        return

    # Scaling: Gerçek değere ölçekle
    final_val = sum(current_holdings[s] * closes[s].iloc[-1] for s in symbols if s in closes.columns)
    scalar = final_val / df_nav['Close'].iloc[-1] if df_nav['Close'].iloc[-1] != 0 else 1
    for col in ['Open', 'High', 'Low', 'Close']:
        df_nav[col] *= scalar

    # --- BETA HESABI ---
    spy_rets = closes['SPY'].pct_change().dropna()
    pf_rets = df_nav['Close'].pct_change().dropna()
    common_idx = pf_rets.index.intersection(spy_rets.index)
    if len(common_idx) > 5:
        beta = pf_rets[common_idx].cov(spy_rets[common_idx]) / spy_rets[common_idx].var()
    else:
        beta = 1.0

    # --- METRİKLER (RATIO & BETA) ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Portföy Değeri", f"${final_val:,.2f}")
    c2.metric("Portföy Betası (β)", f"{beta:.2f}")
    
    last_ratio = df_nav['Ratio'].iloc[-1]
    status = "GÜVENLİ" if last_ratio >= 5 else "KAR AL / EXIT"
    c3.metric(f"Ratio: {status}", f"{last_ratio:.2f}", 
              delta=f"{last_ratio-5:.2f} Sınır Farkı", 
              delta_color="normal" if last_ratio >= 5 else "inverse")

    # --- ÇİFT PANELLİ GRAFİK ---
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=[0.7, 0.3])

    # Üst Panel: Mum Grafiği
    fig.add_trace(go.Candlestick(
        x=df_nav['Date'], open=df_nav['Open'], high=df_nav['High'], 
        low=df_nav['Low'], close=df_nav['Close'],
        increasing_line_color=up_color, decreasing_line_color=down_color, name="Portföy"
    ), row=1, col=1)

    # Alt Panel: Ratio 5 Hattı
    fig.add_trace(go.Scatter(
        x=df_nav['Date'], y=df_nav['Ratio'], 
        line=dict(color='#FF6D00', width=2), name="Ratio (NAV/VIX)"
    ), row=2, col=1)
    
    # 5.00 Kırmızı Kesikli Çizgi (Senin kuralın)
    fig.add_hline(y=5, line_dash="dash", line_color="red", line_width=2, row=2, col=1,
                  annotation_text="Kâr Al (Limit 5.0)", annotation_position="bottom left")

    fig.update_layout(height=700, template="plotly_white", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)
