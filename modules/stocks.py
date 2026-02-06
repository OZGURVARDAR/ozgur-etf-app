import streamlit as st
import pandas as pd
import yfinance as yf

def show():
    st.header("📊 Hisse Senedi Portföyü")
    
    # --- GOOGLE SHEETS VERİSİNİ ÇEK ---
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

    @st.cache_data(ttl=60) # Veriyi 1 dakika önbellekte tut
    def load_data():
        df = pd.read_csv(SHEET_URL)
        df["Date"] = pd.to_datetime(df["Date"])
        # Nakit satırlarını çıkar
        df = df[df["Symbol"] != "CASH"].copy()
        
        # Sayısal değerleri garantiye al
        df["Quantity"] = pd.to_numeric(df["Quantity"], errors='coerce')
        df["Price"] = pd.to_numeric(df["Price"], errors='coerce')
        
        # Her işlem satırı için o işlemin toplam maliyetini hesapla
        df["Cost_Basis"] = df["Quantity"] * df["Price"]
        return df

    raw_df = load_data()

    if raw_df.empty:
        st.info("Portföyde henüz hisse bulunmuyor.")
        return

    # --- AYNI HİSSELERİ BİRLEŞTİR (GROUP BY) ---
    # Örneğin RKLB'den 2 farklı alım varsa bunları tek satıra indirip toplam maliyet ve adedi buluyoruz.
    portfolio = raw_df.groupby("Symbol").agg({
        "Quantity": "sum",
        "Cost_Basis": "sum"
    }).reset_index()

    # Adedi 0 olanları (tamamı satılmışları) filtrele
    portfolio = portfolio[portfolio["Quantity"] > 0]
    
    symbols = portfolio["Symbol"].tolist()

    # --- GÜNCEL FİYATLARI ÇEK ---
    with st.spinner('Güncel fiyatlar alınıyor...'):
        try:
            # period="1d" son kapanışı veya canlı fiyatı getirir
            current_data = yf.download(symbols, period="1d", progress=False)['Close']
            # Eğer tek hisse varsa Series gelir, DataFrame'e çevirelim
            if isinstance(current_data, pd.Series):
                current_data = current_data.to_frame()
                
            # Son satırı (en güncel fiyatı) alalım
            current_prices = current_data.iloc[-1]
        except Exception as e:
            st.error(f"Fiyat verisi alınamadı: {e}")
            return

    # --- PORTFÖY HESAPLAMALARI ---
    portfolio_data = []
    
    # Döngüyle her hissenin güncel değerini hesapla
    for _, row in portfolio.iterrows():
        sym = row["Symbol"]
        qty = row["Quantity"]
        total_cost = row["Cost_Basis"] # O hisse için harcanan toplam para
        
        # Güncel fiyatı bul (Hata olursa maliyeti baz al ki tablo bozulmasın)
        try:
            cur_price = current_prices[sym]
        except:
            cur_price = total_cost / qty # Fallback

        market_value = qty * cur_price
        pl_abs = market_value - total_cost
        pl_pct = (pl_abs / total_cost * 100) if total_cost != 0 else 0
        
        portfolio_data.append({
            "Symbol": sym,
            "Adet": qty,
            "Ort. Maliyet": total_cost / qty, # Birim Maliyet
            "Toplam Maliyet ($)": total_cost,
            "Güncel Fiyat ($)": cur_price,
            "Güncel Değer ($)": market_value,
            "Kâr/Zarar ($)": pl_abs,
            "Kâr/Zarar (%)": pl_pct
        })

    df_view = pd.DataFrame(portfolio_data)

    # --- GENEL TOPLAMLAR (DOĞRU MATEMATİK) ---
    total_cost_portfolio = df_view["Toplam Maliyet ($)"].sum()
    total_value_portfolio = df_view["Güncel Değer ($)"].sum()
    
    total_pl_portfolio = total_value_portfolio - total_cost_portfolio
    
    # İşte burası düzeldi: Toplam Kar / Toplam Maliyet
    total_pl_pct_portfolio = (total_pl_portfolio / total_cost_portfolio * 100) if total_cost_portfolio != 0 else 0

    # --- ÜST METRİKLER ---
    st.subheader("💰 Portföy Özeti")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Toplam Maliyet", f"${total_cost_portfolio:,.2f}")
    c2.metric("Güncel Değer", f"${total_value_portfolio:,.2f}")
    c3.metric("Toplam K/Z ($)", f"${total_pl_portfolio:,.2f}", delta_color="normal")
    c4.metric("Toplam K/Z (%)", f"%{total_pl_pct_portfolio:.2f}", 
              delta=f"{total_pl_pct_portfolio:.2f}%", 
              delta_color="normal")

    st.markdown("---")

    # --- DETAYLI TABLO ---
    st.subheader("💹 Hisse Bazlı Detaylar")
    
    # Renklendirme fonksiyonu
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
