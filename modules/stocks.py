import streamlit as st
import pandas as pd
import yfinance as yf

def show():
    st.header("📊 Hisse Senedi Portföyü")
    
    # Cache temizleme butonu (Eski veriyi silmek için)
    if st.button("🔄 Hesaplamaları Sıfırla"):
        st.cache_data.clear()
        st.rerun()

    # --- GOOGLE SHEETS VERİSİ ---
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

    @st.cache_data(ttl=60)
    def load_data():
        df = pd.read_csv(SHEET_URL)
        df["Date"] = pd.to_datetime(df["Date"])
        df = df[df["Symbol"] != "CASH"].copy()
        
        # Sayısal dönüşüm
        df["Quantity"] = pd.to_numeric(df["Quantity"], errors='coerce')
        df["Price"] = pd.to_numeric(df["Price"], errors='coerce')
        
        # Her satırın maliyeti
        df["Cost_Basis"] = df["Quantity"] * df["Price"]
        return df

    raw_df = load_data()

    if raw_df.empty:
        st.info("Veri yok.")
        return

    # --- KONSOLİDE ETME (Aynı hisseleri topla) ---
    portfolio = raw_df.groupby("Symbol").agg({
        "Quantity": "sum",
        "Cost_Basis": "sum"
    }).reset_index()

    # Elimizde kalmayanları çıkar (Adet <= 0)
    portfolio = portfolio[portfolio["Quantity"] > 0]
    symbols = portfolio["Symbol"].tolist()

    # --- FİYATLARI ÇEK ---
    with st.spinner('Fiyatlar güncelleniyor...'):
        try:
            current_data = yf.download(symbols, period="1d", progress=False)['Close']
            if isinstance(current_data, pd.Series):
                current_data = current_data.to_frame()
            current_prices = current_data.iloc[-1]
        except:
            st.error("Fiyat verisi alınamadı.")
            return

    # --- TABLO OLUŞTURMA ---
    table_rows = []
    
    for _, row in portfolio.iterrows():
        sym = row["Symbol"]
        qty = row["Quantity"]
        total_cost = row["Cost_Basis"]
        
        # Fiyat yoksa maliyet fiyatını kullan (Hata önleyici)
        try:
            cur_price = current_prices[sym]
        except:
            cur_price = total_cost / qty

        market_val = qty * cur_price
        pl_abs = market_val - total_cost
        # Tekil hisse yüzdesi
        pl_pct = (pl_abs / total_cost * 100) if total_cost != 0 else 0
        
        table_rows.append({
            "Symbol": sym,
            "Adet": qty,
            "Ort. Maliyet": total_cost / qty,
            "Toplam Maliyet ($)": total_cost,
            "Güncel Fiyat ($)": cur_price,
            "Güncel Değer ($)": market_val,
            "Kâr/Zarar ($)": pl_abs,
            "Kâr/Zarar (%)": pl_pct
        })

    df_view = pd.DataFrame(table_rows)

    # --- GENEL TOPLAM HESABI (AĞIRLIKLI ORTALAMA) ---
    total_cost_pf = df_view["Toplam Maliyet ($)"].sum()
    total_val_pf = df_view["Güncel Değer ($)"].sum()
    total_pl_pf = total_val_pf - total_cost_pf
    
    # % Kâr = (Toplam Kâr / Toplam Para) * 100
    total_pl_pct_pf = (total_pl_pf / total_cost_pf * 100) if total_cost_pf != 0 else 0

    # --- METRİKLER ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Toplam Maliyet", f"${total_cost_pf:,.2f}")
    c2.metric("Güncel Değer", f"${total_val_pf:,.2f}")
    c3.metric("Toplam K/Z ($)", f"${total_pl_pf:,.2f}", delta_color="normal")
    c4.metric("Toplam K/Z (%)", f"%{total_pl_pct_pf:.2f}", 
              delta=f"{total_pl_pct_pf:.2f}%", delta_color="normal")

    st.divider()

    # --- RENKLİ TABLO ---
    def color_pl(val):
        color = 'green' if val > 0 else 'red' if val < 0 else 'black'
        return f'color: {color}'

    st.dataframe(
        df_view.style.format({
            "Ort. Maliyet": "${:,.2f}",
            "Toplam Maliyet ($)": "${:,.2f}",
            "Güncel Fiyat ($)": "${:,.2f}",
            "Güncel Değer ($)": "${:,.2f}",
            "Kâr/Zarar ($)": "${:,.2f}",
            "Kâr/Zarar (%)": "%{:,.2f}"
        }).applymap(color_pl, subset=["Kâr/Zarar ($)", "Kâr/Zarar (%)"]),
        use_container_width=True,
        hide_index=True
    )
