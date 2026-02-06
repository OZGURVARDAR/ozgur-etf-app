import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime
import pytz

def show():
    # --- STİL VE AYARLAR ---
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
        return trades

    trades = load_portfolio()
    symbols = trades["Symbol"].unique().tolist()
    first_date = trades['Date'].min()

    with st.spinner('Piyasa verileri senkronize ediliyor...'):
        data = yf.download(symbols, start=first_date, interval="1d", group_by='ticker', progress=False)
        # Piyasa açıkken gelen boş satırları temizle
        data = data.dropna(how='all')

    # --- 1. KESİN GÜNCEL DEĞER HESABI (Scaling Base) ---
    final_market_value = 0.0
    yesterday_market_value = 0.0
    
    for sym in symbols:
        qty = trades[trades["Symbol"] == sym]["Quantity"].sum()
        if qty != 0:
            try:
                # Çoklu sembol yapısında veriye erişim düzeltmesi
                s_data = data[sym] if len(symbols) > 1 else data
                s_data = s_data.ffill() # Piyasa açılışındaki nan değerleri doldur
                
                current_price = s_data['Close'].iloc[-1]
                prev_price = s_data['Close'].iloc[-2] if len(s_data) > 1 else current_price
                
                if not pd.isna(current_price):
                    final_market_value += qty * current_price
                    yesterday_market_value += qty * prev_price
            except: pass

    # --- 2. TWR / NAV MOTORU ---
    nav_series = []
    current_nav = 1.0 
    current_holdings = {sym: 0.0 for sym in symbols}
    all_dates = data.index.sort_values()
    
    for i, date in enumerate(all_dates):
        val_start, val_end = 0.0, 0.0
        val_open, val_high, val_low = 0.0, 0.0, 0.0
        has_assets = False
        
        for sym, qty in current_holdings.items():
            if qty != 0:
                has_assets = True
                try:
                    s_data = data[sym] if len(symbols) > 1 else data
                    # Tarih bazlı veri çekme hatasını önlemek için ffill uygulanmış veri kullan
                    row = s_data.loc[date]
                    
                    # Önceki günün kapanışı (Eğer ilk günse açılışı kullan)
                    if i > 0:
                        p_prev = s_data['Close'].iloc[i-1]
                    else:
                        p_prev = row['Open']

                    # Sıfıra bölünme ve nan kontrolü
                    if p_prev > 0 and not pd.isna(p_prev):
                        val_start += qty * p_prev
                        val_end += qty * row['Close']
                        val_open += qty * row['Open']
                        val_high += qty * row['High']
                        val_low += qty * row['Low']
                except: continue
        
        if has_assets and val_start > 0:
            r_open, r_high, r_low, r_close = val_open/val_start, val_high/val_start, val_low/val_start, val_end/val_start
            
            # Nan değerlerin nav_series'e girmesini engelle
            if not any(pd.isna([r_open, r_high, r_low, r_close])):
                nav_series.append({
                    'Date': date, 'Open': current_nav * r_open, 'High': current_nav * r_high, 
                    'Low': current_nav * r_low, 'Close': current_nav * r_close
                })
                current_nav *= r_close
        else:
            # Varlık yoksa seviyeyi koru
            nav_series.append({'Date': date, 'Open': current_nav, 'High': current_nav, 'Low': current_nav, 'Close': current_nav})

        todays_trades = trades[trades['Date'] == date]
        for _, row in todays_trades.iterrows():
            current_holdings[row['Symbol']] += row['Quantity']

    # --- 3. SCALING & ALIGNMENT ---
    df_nav = pd.DataFrame(nav_series)
    
    if not df_nav.empty and df_nav['Close'].iloc[-1] != 0:
        scalar = final_market_value / df_nav['Close'].iloc[-1]
    else:
        scalar = 1.0
        
    for col in ['Open', 'High', 'Low', 'Close']:
        df_nav[col] *= scalar
    
    df_nav['Date_Str'] = df_nav['Date'].dt.strftime('%d %b %y')

    # --- METRİKLER ---
    daily_chg_pct = ((final_market_value - yesterday_market_value) / yesterday_market_value * 100) if yesterday_market_value != 0 else 0
    st.metric("Güncel Portföy Değeri", f"${final_market_value:,.2f}", f"{daily_chg_pct:+.2f}%")

    # --- GRAFİK ---
    fig = go.Figure()

    if chart_mode == "Heiken Ashi":
        ha_close = (df_nav['Open'] + df_nav['High'] + df_nav['Low'] + df_nav['Close']) / 4
        ha_open = [(df_nav['Open'].iloc[0] + df_nav['Close'].iloc[0]) / 2]
        for i in range(1, len(df_nav)):
            ha_open.append((ha_open[i-1] + ha_close.iloc[i-1]) / 2)
        
        df_nav['HA_Open'] = ha_open
        df_nav['HA_Close'] = ha_close
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

    fig.add_hline(
        y=final_market_value, line_dash="dot", line_color="red", line_width=1.5,
        annotation_text=f"${final_market_value:,.2f}", 
        annotation_position="right",
        annotation_font=dict(color="white", size=12),
        annotation_bgcolor="red"
    )

    fig.update_layout(
        height=700, template="plotly_white",
        yaxis=dict(side="right", tickformat=",.0f", tickprefix="$", gridcolor="#f4f4f4"),
        xaxis=dict(type='category', nticks=12, gridcolor="#f4f4f4"),
        xaxis_rangeslider_visible=False,
        margin=dict(l=0, r=80, t=20, b=20),
        hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True)
