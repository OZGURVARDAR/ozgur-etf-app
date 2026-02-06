import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime

def show_metrics(df_nav, closes):
    """
    df_nav: stocks_chart.py içindeki TWR hesaplanmış DataFrame
    closes: yfinance üzerinden çekilmiş tüm kapanış fiyatları
    """
    
    # 1. HESAPLAMALAR
    # Beta (SPY ile korelasyon)
    spy_rets = closes['SPY'].pct_change().dropna()
    pf_rets = df_nav['Close'].pct_change().dropna()
    common = pf_rets.index.intersection(spy_rets.index)
    beta_val = pf_rets[common].cov(spy_rets[common]) / spy_rets[common].var() if len(common) > 1 else 1.0

    # Ratio (NAV / VIX)
    vix_last = closes['^VIX'].iloc[-1]
    nav_last = df_nav['Close'].iloc[-1]
    # NAV normalize (100 bazlı) oranlama
    current_ratio = (nav_last / df_nav['Close'].iloc[0] * 100) / vix_last

    # 2. GÖRÜNÜM (SOL TARAFA HİZALANMIŞ YARIM EKRAN)
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📊 Risk Paneli")
        
        # Üst metrikler
        m1, m2 = st.columns(2)
        m1.metric("Portföy Betası (β)", f"{beta_val:.2f}")
        m2.metric("Ratio (NAV/VIX)", f"{current_ratio:.2f}", 
                  delta="GÜVENLİ" if current_ratio > 5 else "RİSKLİ",
                  delta_color="normal" if current_ratio > 5 else "inverse")

        # Ratio Grafiği
        fig_ratio = go.Figure()
        
        # VIX Ratio Çizgisi
        fig_ratio.add_trace(go.Scatter(
            x=df_nav['Date'], 
            y=(df_nav['Close'] / df_nav['Close'].iloc[0] * 100) / closes['^VIX'].reindex(df_nav['Date']).ffill(),
            line=dict(color='#FF6D00', width=2),
            fill='tozeroy',
            name="Ratio"
        ))
        
        # Eşik Değeri (5)
        fig_ratio.add_hline(y=5, line_dash="dash", line_color="red", annotation_text="Kritik Eşik (5)")

        fig_ratio.update_layout(
            height=300,
            margin=dict(l=10, r=10, t=10, b=10),
            template="plotly_white",
            xaxis=dict(showgrid=False),
            yaxis=dict(side='right'),
            showlegend=False
        )
        
        st.plotly_chart(fig_ratio, use_container_width=True)

    with col2:
        # Burası ileride US500 kıyaslaması için boş bırakıldı
        st.info("📈 US500 Kıyaslama Grafiği yakında buraya eklenecek.")
