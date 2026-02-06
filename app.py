import streamlit as st
from modules import stocks          # Tablo + toplam portföy metricleri
from modules import stocks_chart    # Portföyün günlük değer grafiği (Anayasa)
from modules import ratio_beta      # Yeni oluşturacağın Ratio & Beta modülü

# --- PAGE CONFIG ---
st.set_page_config(layout="wide", page_title="Portfolio Terminal")
st.title("📈 Modular Portfolio App")

# --- SIDEBAR MODÜL SEÇİMİ ---
tab = st.sidebar.selectbox("Select Module", ["Stocks"])

if tab == "Stocks":
    # 1. STOCKS TABLO VE METRICLER (Üst Kısım)
    stocks.show()

    st.markdown("---")

    # 2. PORTFÖY GRAFİĞİ (Anayasa Kod)
    # stocks_chart.show() fonksiyonunun df_nav ve closes döndürdüğünden emin olun
    result = stocks_chart.show()
    
    if result is not None:
        df_nav, closes = result
        
        st.markdown("---")
        
        # 3. RATIO VE BETA PANELİ (Grafiğin Altı)
        # Bu fonksiyon ratio_beta.py içinde tanımladığımız fonksiyondur
        ratio_beta.show_metrics(df_nav, closes)
