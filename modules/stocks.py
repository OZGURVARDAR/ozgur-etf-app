import streamlit as st
import pandas as pd
import yfinance as yf

def show():
    st.subheader("📊 Hisse Senedi Portföyü")
    
    # --- CACHE TEMİZLEME MEKANİZMASI ---
    if st.button("🔄 VERİLERİ TEMİZLE VE YENİLE (Buna Bas)", type="primary"):
        st.cache_data.clear()
        st.rerun()

    # --- VERİ YÜKLEME ---
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

    @st.cache_data(ttl=60)
    def load_portfolio_data():
        df = pd.read_csv(SHEET_URL)
        df["Date"] = pd.to_datetime(df["Date"])
        df = df[df["Symbol"] != "CASH"].copy()
        df["Quantity"] = pd.to_numeric(df["Quantity"], errors='coerce')
        df["Price"] = pd.to_numeric(df["Price"], errors='coerce')
        df["Cost_Basis"] = df["Quantity"] * df["Price"]
        return df

    raw_df = load_portfolio_data()

    if raw_df.empty:
        st.warning("Veri bulunamadı.")
        return

    # --- GRUPLAMA VE HESAPLAMA ---
    # Aynı hisseden birden fazla alımı tek satıra indir
    portfolio = raw_df.groupby("Symbol").agg({
        "Quantity": "sum",
        "Cost_Basis": "sum"
    }).reset_index()

    portfolio = portfolio[portfolio["Quantity"] > 0]
    symbols = portfolio["Symbol"].tolist()

    # --- FİYATLAR ---
    with st.spinner('Güncel fiyatlar alınıyor...'):
        try:
            # period="1d" en güvenli yöntemdir
            price_data = yf.download(symbols, period="1d", progress=False)['Close']
            # Tek hisse varsa Series gelir, DataFrame yapalım
            if isinstance(price_data, pd.Series):
                price_data = price_data.to_frame()
            current_prices = price_data.iloc[-1]
        except:
            st.error("Fiyat verisi alınamadı. İnternet bağlantısını kontrol edin.")
            return

    # --- TABLO OLUŞTURMA ---
    rows = []
    for _, row in portfolio.iterrows():
        sym = row["Symbol"]
        qty = row["Quantity"]
        total_cost = row["Cost_Basis"]
        
        # Fiyat güvenliği
        try:
            cur_price = current_prices[sym]
        except:
            cur_price = total_cost / qty # Hata varsa maliyeti kullan

        val = qty * cur_price
        pl_abs = val - total_cost
        # Hisse bazlı yüzde
        pl_pct = (pl_abs / total_cost * 100) if total_cost != 0 else 0
        
        rows.append({
            "Symbol": sym,
            "Adet": qty,
            "Ort. Maliyet": total_cost / qty,
            "Toplam Maliyet ($)": total_cost,
            "Güncel Fiyat ($)": cur_price,
            "Güncel Değer ($)": val,
            "Kâr/Zarar ($)": pl_abs,
            "Kâr/Zarar (%)": pl_pct
        })

    df_final = pd.DataFrame(rows)

    # --- DOĞRU MATEMATİK İLE GENEL TOPLAM ---
    # Ortalamaların ortalaması ALINMAZ. Toplamlardan gidilir.
    total_cost = df_final["Toplam Maliyet ($)"].sum()
    total_val = df_final["Güncel Değer ($)"].sum()
    total_pl = total_val - total_cost
    
    # Beklediğin %2.63 civarı sonucu verecek formül:
    total_pl_pct = (total_pl / total_cost * 100) if total_cost != 0 else 0

    # --- METRİKLER ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Toplam Maliyet", f"${total_cost:,.2f}")
    c2.metric("Güncel Değer", f"${total_val:,.2f}")
    c3.metric("Toplam K/Z ($)", f"${total_pl:,.2f}")
    c4.metric("Toplam K/Z (%)", f"%{total_pl_pct:.2f}", 
              delta=f"{total_pl_pct:.2f}%", delta_color="normal")

    st.markdown("---")

    # --- DETAYLI TABLO ---
    def color_vals(val):
        if val > 0: return 'color: green'
        elif val < 0: return 'color: red'
        return 'color: black'

    st.dataframe(
        df_final.style.format({
            "Ort. Maliyet": "${:,.2f}",
            "Toplam Maliyet ($)": "${:,.2f}",
            "Güncel Fiyat ($)": "${:,.2f}",
            "Güncel Değer ($)": "${:,.2f}",
            "Kâr/Zarar ($)": "${:,.2f}",
            "Kâr/Zarar (%)": "%{:,.2f}"
        }).applymap(color_vals, subset=["Kâr/Zarar ($)", "Kâr/Zarar (%)"]),
        use_container_width=True,
        hide_index=True
    )
