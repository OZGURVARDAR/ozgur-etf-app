import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pytz
from datetime import datetime

def show():
    st.subheader("🛡️ Risk & Performance Terminal")
    
    # Sidebar
    chart_mode = st.sidebar.selectbox("Mum Tipi", ["Candlestick", "Heiken Ashi"])
    if st.sidebar.button("🔄 Verileri Yenile"):
        st.cache_data.clear()
        st.rerun()

    # --- VERİ YÜKLEME ---
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

    @st.cache_data(ttl=300)
    def get_data_bundle():
        # 1. Google Sheets
        df = pd.read_csv(SHEET_URL)
        df['Date'] = pd.to_datetime(df['Date']).dt.normalize()
        trades = df[df["Symbol"] != "CASH"].sort_values('Date')
        symbols = trades["Symbol"].unique().tolist()
        
        # 2. Yahoo Finance (Toplu İndirme - Hız için)
        # SPY (Piyasa) ve ^VIX (Korku) ekliyoruz
        tickers_to_download = symbols + ["SPY", "^VIX"]
        data = yf.download(tickers_to_download, start=trades['Date'].min(), interval="1d", group_by='ticker', progress=False)
        return trades, data, symbols

    trades, raw_data, symbols = get_data_bundle()

    # --- 1. BETA HESAPLAMA (Matematiksel & Hızlı) ---
    # İnternetten tek tek sormak yerine, eldeki veriden varyans/kovaryans ile buluyoruz.
    pf_beta_weighted = 0.0
    total_market_val = 0.0
    
    # Önce güncel portföy ağırlıklarını bulalım
    symbol_values = {}
    for sym in symbols:
        qty = trades[trades["Symbol"] == sym]["Quantity"].sum()
        if qty > 0:
            try:
                price = raw_data[sym]['Close'].iloc[-1]
                val = qty * price
                symbol_values[sym] = val
                total_market_val += val
            except: pass

    # Her hissenin SPY ile korelasyonuna göre Beta hesapla
    if 'SPY' in raw_data.columns:
        spy_rets = raw_data['SPY']['Close'].pct_change().dropna()
        for sym, val in symbol_values.items():
            try:
                stock_rets = raw_data[sym]['Close'].pct_change().dropna()
                # Ortak tarihleri al
                common_idx = stock_rets.index.intersection(spy_rets.index)
                if len(common_idx) > 10:
                    cov = stock_rets[common_idx].cov(spy_rets[common_idx])
                    var = spy_rets[common_idx].var()
                    beta = cov / var if var != 0 else 1.0
                else:
                    beta = 1.0
                
                weight = val / total_market_val
                pf_beta_weighted += weight * beta
            except:
                # Veri hatası varsa Beta'yı etkisiz kabul et
                pf_beta_weighted += (val / total_market_val) * 1.0
    else:
        pf_beta_weighted = 1.0 # SPY verisi yoksa varsayılan

    # --- 2. TWR & RATIO ENGINE ---
    nav_series = []
    current_nav = 1.0 
    current_holdings = {sym: 0.0 for sym in symbols}
    all_dates = raw_data.index.sort_values()
    
    # VIX Verisi Güvenliği
    vix_data = raw_data['^VIX']['Close'] if '^VIX' in raw_data.columns else pd.Series(20, index=all_dates)

    for i, date in enumerate(all_dates):
        val_start, val_end = 0.0, 0.0
        val_open, val_high, val_low = 0.0, 0.0, 0.0
        has_assets = False
        
        # Günlük Performans
        for sym, qty in current_holdings.items():
            if qty != 0:
                has_assets = True
                try:
                    s = raw_data[sym]
                    # Günlük OHLC verileri
                    row = s.loc[date]
                    p_prev = s['Close'].iloc[s.index.get_loc(date)-1] if i > 0 else row['Open']

                    val_start += qty * p_prev
                    val_end += qty * row['Close']
                    val_open += qty * row['Open']
                    val_high += qty * row['High']
                    val_low += qty * row['Low']
                except: continue
        
        if has_assets and val_start > 0:
            r_o, r_h, r_l, r_c = val_open/val_start, val_high/val_start, val_low/val_start, val_end/val_start
            
            # VIX Ratio
            try:
                vix_val = vix_data.loc[date]
                # Eğer VIX o gün yoksa (tatil vs) önceki günü al
                if pd.isna(vix_val): vix_val = 20.0 
            except: vix_val = 20.0
            
            nav_point = current_nav * r_c
            ratio = (nav_point * 100) / vix_val if vix_val > 0 else 0

            nav_series.append({
                'Date': date, 'Open': current_nav*r_o, 'High': current_nav*r_h, 
                'Low': current_nav*r_l, 'Close': nav_point,
                'VIX': vix_val, 'Ratio': ratio
            })
            current_nav = nav_point
        
        # Alım/Satımları Ekle
        todays_trades = trades[trades['Date'] == date]
        for _, row in todays_trades.iterrows():
            current_holdings[row['Symbol']] += row['Quantity']

    # --- 3. GÖRSELLEŞTİRME ---
    if not nav_series:
        st.warning("Grafik oluşturulacak yeterli veri yok.")
        return

    df_res = pd.DataFrame(nav_series)
    
    # SCALING: Son değeri Portfolio Total Value'ya eşitle
    if df_res['Close'].iloc[-1] > 0:
        scalar = total_market_val / df_res['Close'].iloc[-1]
    else:
        scalar = 1.0
    
    for c in ['Open', 'High', 'Low', 'Close']:
        df_res[c] *= scalar

    df_res['Date_Str'] = df_res['Date'].dt.strftime('%d %b %y')

    # METRİKLER
    c1, c2, c3 = st.columns(3)
    c1.metric("Portföy Değeri", f"${total_market_val:,.2f}")
    c2.metric("Portföy Betası (β)", f"{pf_beta_weighted:.2f}", "Piyasa Riski")
    
    last_ratio = df_res['Ratio'].iloc[-1]
    c3.metric("Ratio (NAV/VIX)", f"{last_ratio:.2f}", 
              delta="RİSKLİ BÖLGE (<5)" if last_ratio < 5 else "GÜVENLİ (>5)",
              delta_color="inverse" if last_ratio < 5 else "normal")

    # ÇİFT GRAFİK
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, row_heights=[0.7, 0.3])

    # 1. Fiyat Grafiği
    if chart_mode == "Heiken Ashi":
        ha_close = (df_res['Open'] + df_res['High'] + df_res['Low'] + df_res['Close']) / 4
        ha_open = [(df_res['Open'].iloc[0] + df_res['Close'].iloc[0]) / 2]
        for k in range(1, len(df_res)):
            ha_open.append((ha_open[k-1] + ha_close.iloc[k-1]) / 2)
        
        fig.add_trace(go.Candlestick(
            x=df_res['Date_Str'], open=ha_open, high=df_res['High'], low=df_res['Low'], close=ha_close,
            name="Heiken Ashi"
        ), row=1, col=1)
    else:
        fig.add_trace(go.Candlestick(
            x=df_res['Date_Str'], open=df_res['Open'], high=df_res['High'], low=df_res['Low'], close=df_res['Close'],
            name="Fiyat"
        ), row=1, col=1)

    # 2. Ratio Grafiği
    fig.add_trace(go.Scatter(
        x=df_res['Date_Str'], y=df_res['Ratio'], mode='lines', 
        line=dict(color='#FF6D00', width=2), name="Ratio"
    ), row=2, col=1)
    
    # Kritik 5 Seviyesi
    fig.add_hline(y=5, line_dash="dot", line_color="red", line_width=2, row=2, col=1, annotation_text="Limit: 5.0")

    fig.update_layout(height=700, template="plotly_white", xaxis_rangeslider_visible=False, hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)
