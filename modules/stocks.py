import streamlit as st
import pandas as pd
import yfinance as yf

def show():
    st.subheader("📊 Hisse Senedi Portföyü")
    
    if st.button("🔄 VERİLERİ SIFIRLA VE YENİLE"):
        st.cache_data.clear()
        st.rerun()

    SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

    @st.cache_data(ttl=60)
    def load_clean_data():
        df = pd.read_csv(SHEET_URL)
        df["Date"] = pd.to_datetime(df["Date"])
        df = df[df["Symbol"] != "CASH"].copy()
        df["Quantity"] = pd.to_numeric(df["Quantity"], errors='coerce')
        df["Price"] = pd.to_numeric(df["Price"], errors='coerce')
        df["Cost_Basis"] = df["Quantity"] * df["Price"]
        return df

    raw_df = load_clean_data()
    if raw_df.empty: return

    # Birleştirme
    portfolio = raw_df.groupby("Symbol").agg({"Quantity": "sum", "Cost_Basis": "sum"}).reset_index()
    portfolio = portfolio[portfolio["Quantity"] > 0]
    symbols = portfolio["Symbol"].tolist()

    # Fiyatlar
    with st.spinner('Fiyatlar alınıyor...'):
        try:
            data = yf.download(symbols, period="1d", progress=False)['Close']
            curr_prices = data.iloc[-1] if isinstance(data, pd.DataFrame) else data
        except:
            st.error("Bağlantı hatası.")
            return

    rows = []
    for _, row in portfolio.iterrows():
        s = row["Symbol"]
        q = row["Quantity"]
        cost = row["Cost_Basis"]
        p = curr_prices[s] if s in curr_prices else (cost/q)
        
        val = q * p
        pl = val - cost
        pct = (pl / cost * 100) if cost != 0 else 0
        rows.append({"Symbol": s, "Adet": q, "Ort. Maliyet": cost/q, "Toplam Maliyet ($)": cost, 
                     "Güncel Fiyat ($)": p, "Güncel Değer ($)": val, "Kâr/Zarar ($)": pl, "Kâr/Zarar (%)": pct})

    df_view = pd.DataFrame(rows)

    # ÖZET METRİKLER (Doğru Matematik)
    t_cost = df_view["Toplam Maliyet ($)"].sum()
    t_val = df_view["Güncel Değer ($)"].sum()
    t_pl = t_val - t_cost
    t_pct = (t_pl / t_cost * 100) if t_cost != 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Toplam Maliyet", f"${t_cost:,.2f}")
    c2.metric("Güncel Değer", f"${t_val:,.2f}")
    c3.metric("Toplam K/Z ($)", f"${t_pl:,.2f}")
    c4.metric("Toplam K/Z (%)", f"%{t_pct:.2f}")

    st.dataframe(df_view.style.format({"Ort. Maliyet": "{:.2f}", "Toplam Maliyet ($)": "{:.2f}", 
                                      "Güncel Fiyat ($)": "{:.2f}", "Güncel Değer ($)": "{:.2f}", 
                                      "Kâr/Zarar ($)": "{:.2f}", "Kâr/Zarar (%)": "{:.2f}"}), use_container_width=True)
