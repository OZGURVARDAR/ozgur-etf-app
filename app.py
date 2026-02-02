import streamlit as st
from modules import stocks  # Diğer modüller ileride eklenecek

st.set_page_config(layout="wide")
st.title("📈 Modular Portfolio App")

# Sidebar ile modül seçimi
tab = st.sidebar.selectbox("Select Module", ["Stocks"])  # Şimdilik sadece Stocks var

if tab == "Stocks":
    stocks.show()
