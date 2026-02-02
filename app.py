import streamlit as st
from modules import stocks          # Tablo + toplam portföy metricleri
from modules import stocks_chart    # Portföyün günlük değer grafiği

# --- PAGE CONFIG ---
st.set_page_config(layout="wide")
st.title("📈 Modular Portfolio App")

# --- SIDEBAR MODÜL SEÇİMİ ---
tab = st.sidebar.selectbox("Select Module", ["Stocks"])  # Şimdilik sadece Stocks var

if tab == "Stocks":
    # --- STOCKS TABLO VE METRICLER ---
    stocks.show()

    # --- PORTFÖY GRAFİĞİ TABLO ALTINDA ---
    stocks_chart.show()
