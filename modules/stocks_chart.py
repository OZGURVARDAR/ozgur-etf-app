import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def show():
    st.subheader("🛡️ Risk & Performance Terminal")
    
    if st.sidebar.button("🔄 Terminali Yenile"):
        st.cache_data.clear()
        st.rerun()

    SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

    @st.cache_data(ttl=300)
    def fetch_all():
        df = pd.read_csv(SHEET_URL)
        df['Date'] = pd.to_datetime(df['Date']).dt.normalize()
        trades = df[df["Symbol"] != "CASH"].sort_values('Date')
        syms = trades["Symbol"].unique().tolist()
        data = yf.download(syms + ["^VIX", "SPY"], start=trades['Date'].min(), interval="1d", progress=False)
        return trades, data, syms

    trades, raw_data, syms = fetch_all()
    if raw_data.empty: return

    # Verileri Ayıkla
    closes = raw_data['Close'].ffill()
    opens = raw_data['Open'].ffill()
    highs = raw_data['High'].ffill()
    lows = raw_data['Low'].ffill()

    # TWR Hesaplama
    nav_pts = []
    c_nav = 1.0
    holdings = {s: 0.0 for s in syms}
    dates = closes.index.sort_values()

    for i, d in enumerate(dates):
        v_start, v_end, v_o, v_h, v_l = 0.0, 0.0, 0.0, 0.0, 0.0
        active = False
        for s in syms:
            if holdings[s] > 0:
                active = True
                p_prev = closes[s].iloc[i-1] if i > 0 else opens.at[d, s]
                v_start += holdings[s] * p_prev
                v_end += holdings[s] * closes.at[d, s]
                v_o += holdings[s] * opens.at[d, s]
                v_h += holdings[s] * highs.at[d, s]
                v_l += holdings[s] * lows.at[d, s]
        
        if active and v_start > 0:
            ratio_v = (c_nav * (v_end/v_start) * 100) / (closes.at[d, "^VIX"] if "^VIX" in closes.columns else 20)
            nav_pts.append({'Date': d, 'Open': c_nav*(v_o/v_start), 'High': c_nav*(v_h/v_start), 
                            'Low': c_nav*(v_l/v_start), 'Close': c_nav*(v_end/v_start), 'Ratio': ratio_v})
            c_nav *= (v_end/v_start)

        for _, r in trades[trades['Date'] == d].iterrows():
            holdings[r['Symbol']] += r['Quantity']

    # Görselleştirme
    df_res = pd.DataFrame(nav_pts)
    # Gerçek fiyata ölçekle
    last_val = sum(holdings[s] * closes[s].iloc[-1] for s in syms if s in closes.columns)
    scalar = last_val / df_res['Close'].iloc[-1] if not df_res.empty else 1
    for c in ['Open', 'High', 'Low', 'Close']: df_res[c] *= scalar

    # Metrikler (Beta Hesabı Dahil)
    col1, col2, col3 = st.columns(3)
    col1.metric("Portföy Değeri", f"${last_val:,.2f}")
    
    # Beta
    spy_ret = closes['SPY'].pct_change()
    pf_ret = df_res['Close'].pct_change()
    beta_v = pf_ret.cov(spy_ret) / spy_ret.var() if len(pf_ret)>1 else 1.0
    col2.metric("Beta (Risk)", f"{beta_v:.2f}")
    col3.metric("Ratio", f"{df_res['Ratio'].iloc[-1]:.2f}")

    # Grafik
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
    fig.add_trace(go.Candlestick(x=df_res['Date'], open=df_res['Open'], high=df_res['High'], 
                                 low=df_res['Low'], close=df_res['Close'], name="Portföy"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_res['Date'], y=df_res['Ratio'], line=dict(color='orange'), name="Ratio"), row=2, col=1)
    fig.add_hline(y=5, line_dash="dash", line_color="red", row=2, col=1)
    fig.update_layout(height=600, xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)
