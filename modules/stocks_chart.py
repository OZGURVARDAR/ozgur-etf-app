import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def show():
    # --- AYARLAR ---
    up_color, down_color = '#26a69a', '#ef5350'
    st.subheader("🛡️ Risk & Performance Terminal")
    
    col_opt, col_btn = st.columns([3, 1])
    with col_opt:
        chart_mode = st.selectbox("Grafik Modu", ["Candlestick", "Heiken Ashi"], key="chart_mode_sel")
    with col_btn:
        if st.button("🔄 Grafiği Yenile"):
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
        
        # 2. Yahoo Finance (GÜVENLİ İNDİRME)
        # Hepsini tek seferde indiriyoruz ama group_by kullanmıyoruz, işlemeyi aşağıda yapacağız
        tickers = symbols + ["^VIX", "SPY"]
        data = yf.download(tickers, start=trades['Date'].min(), interval="1d", progress=False)
        return trades, data, symbols

    trades, raw_data, symbols = get_data_bundle()

    # Eğer veri boşsa dur
    if raw_data.empty:
        st.error("Veri çekilemedi.")
        return

    # --- 1. BETA HESABI (Basitleştirilmiş) ---
    pf_beta = 1.0
    try:
        # Kapanış fiyatlarını al
        closes = raw_data['Close']
        # Eksik verileri doldur (ffill) ki hesap bozulmasın
        closes = closes.ffill()
        
        if 'SPY' in closes.columns:
            spy_ret = closes['SPY'].pct_change()
            total_w_val = 0
            temp_beta_sum = 0
            
            # Son fiyatlar
            last_prices = closes.iloc[-1]
            
            for sym in symbols:
                qty = trades[trades["Symbol"] == sym]["Quantity"].sum()
                if qty > 0 and sym in closes.columns:
                    val = qty * last_prices[sym]
                    
                    # Hisse betası
                    stock_ret = closes[sym].pct_change()
                    cov = stock_ret.cov(spy_ret)
                    var = spy_ret.var()
                    beta = cov / var if var != 0 else 1.0
                    
                    temp_beta_sum += val * beta
                    total_w_val += val
            
            if total_w_val > 0:
                pf_beta = temp_beta_sum / total_w_val
    except Exception as e:
        # Beta hesabı başarısız olursa varsayılan 1.0 kalır
        pass

    # --- 2. TWR MOTORU (MUM OLUŞTURUCU) ---
    # Burası grafiğin çizilmesini sağlayan çekirdek kısımdır
    
    # Kapanış, Açılış, Yüksek, Düşük verilerini ayrı dataframe olarak ayıklayalım
    # MultiIndex hatasını önlemek için
    try:
        df_close = raw_data['Close'].ffill()
        df_open = raw_data['Open'].ffill()
        df_high = raw_data['High'].ffill()
        df_low = raw_data['Low'].ffill()
    exceptKeyError:
        st.error("Veri formatı hatası.")
        return

    nav_series = []
    current_nav = 1.0
    current_holdings = {sym: 0.0 for sym in symbols}
    
    # Tarihleri al
    all_dates = df_close.index.sort_values()
    
    # VIX verisi (Ratio için)
    vix_series = df_close['^VIX'] if '^VIX' in df_close.columns else pd.Series(20, index=all_dates)

    for i, date in enumerate(all_dates):
        # O günkü portföy hareketi
        val_start = 0.0
        val_end = 0.0
        val_o, val_h, val_l = 0.0, 0.0, 0.0
        
        has_assets = False
        
        for sym, qty in current_holdings.items():
            if qty > 0 and sym in df_close.columns:
                has_assets = True
                p_c = df_close.at[date, sym]
                # Önceki gün kapanışı (veya bugün açılış)
                p_prev = df_close[sym].iloc[i-1] if i > 0 else df_open.at[date, sym]
                
                p_o = df_open.at[date, sym]
                p_h = df_high.at[date, sym]
                p_l = df_low.at[date, sym]
                
                val_start += qty * p_prev
                val_end += qty * p_c
                val_o += qty * p_o
                val_h += qty * p_h
                val_l += qty * p_l
        
        if has_assets and val_start > 0:
            nav_open = current_nav * (val_o / val_start)
            nav_high = current_nav * (val_h / val_start)
            nav_low = current_nav * (val_l / val_start)
            nav_close = current_nav * (val_end / val_start)
            
            # Ratio Hesabı
            vix_val = vix_series.at[date]
            if pd.isna(vix_val): vix_val = 20.0
            ratio = (nav_close * 100) / vix_val if vix_val > 0 else 0

            nav_series.append({
                'Date': date, 'Open': nav_open, 'High': nav_high, 
                'Low': nav_low, 'Close': nav_close, 'Ratio': ratio
            })
            current_nav = nav_close
        else:
            # Varlık yoksa veya ilk günse
            if i == 0:
                 nav_series.append({'Date': date, 'Open': 1, 'High': 1, 'Low': 1, 'Close': 1, 'Ratio': 0})

        # Alım satımları güncelle
        todays_trades = trades[trades['Date'] == date]
        for _, row in todays_trades.iterrows():
            current_holdings[row['Symbol']] += row['Quantity']

    # --- 3. GÖRSELLEŞTİRME ---
    df_res = pd.DataFrame(nav_series)
    if df_res.empty:
        st.warning("Grafik verisi oluşmadı.")
        return

    # Scaling: Grafiği gerçek dolar değerine oturt
    final_market_val = 0
    for sym, qty in current_holdings.items():
        if qty > 0 and sym in df_close.columns:
            final_market_val += qty * df_close[sym].iloc[-1]

    scalar = final_market_val / df_res['Close'].iloc[-1] if df_res['Close'].iloc[-1] != 0 else 1
    
    for c in ['Open', 'High', 'Low', 'Close']:
        df_res[c] *= scalar
        
    df_res['Date_Str'] = df_res['Date'].dt.strftime('%d %b %y')

    # Metrikler
    c1, c2, c3 = st.columns(3)
    c1.metric("Portföy Değeri", f"${final_market_val:,.2f}")
    c2.metric("Beta (Risk)", f"{pf_beta:.2f}")
    
    cur_ratio = df_res['Ratio'].iloc[-1]
    c3.metric("Ratio (NAV/VIX)", f"{cur_ratio:.2f}", 
              delta="RİSKLİ" if cur_ratio < 5 else "GÜVENLİ",
              delta_color="inverse" if cur_ratio < 5 else "normal")

    # Çift Grafik
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.08, row_heights=[0.7, 0.3])

    # Fiyatlar
    if chart_mode == "Heiken Ashi":
        ha_close = (df_res['Open'] + df_res['High'] + df_res['Low'] + df_res['Close']) / 4
        ha_open = [df_res['Open'].iloc[0]]
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

    # Ratio Çizgisi
    fig.add_trace(go.Scatter(
        x=df_res['Date_Str'], y=df_res['Ratio'], mode='lines', 
        line=dict(color='#FF6D00', width=2), name="Ratio"
    ), row=2, col=1)
    
    fig.add_hline(y=5, line_dash="dash", line_color="red", row=2, col=1, annotation_text="Limit 5.0")

    fig.update_layout(height=700, template="plotly_white", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)
