import streamlit as st
import pandas as pd
import yfinance as yf

def show():
    st.header("📊 Hisse Senedi Portföyü")
    
    # --- DATA LOADING ---
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

    @st.cache_data(ttl=300)
    def load_data():
        df = pd.read_csv(SHEET_URL)
        df["Date"] = pd.to_datetime(df["Date"])
        # Sadece hisseleri al ve sayısal verileri zorla
        df = df[df["Symbol"] != "CASH"].copy()
        df["Quantity"] = pd.to_numeric(df["Quantity"])
        df["Price"] = pd.to_numeric(df["Price"])
        return df

    df = load_data()
    symbols = df["Symbol"].unique().tolist()

    if not symbols:
        st.info("Portföyde henüz hisse bulunmuyor.")
        return

    # --- GET LATEST PRICES (Optimized) ---
    # Sadece son fiyatı almak için period="1d" yeterli
    price_data = yf.download(symbols, period="1d", progress=False)["Close"]
    
    # --- CALCULATE METRICS ---
    stock_list = []
    for symbol in symbols:
        s_df = df[df["Symbol"] == symbol]
        
        # Satışları da hesaba katan net adet ve maliyet
        net_qty = s_df["Quantity"].sum()
        
        # Eğer hisse tamamen satıldıysa (adet 0 ise) tabloda gösterme
        if net_qty <= 0:
            continue
            
        total_cost = (s_df["Quantity"] * s_df["Price"]).sum()
        avg_price = total_cost / net_qty if net_qty > 0 else 0
        
        # Fiyat çekme hatasına karşı kontrol
        try:
            current_price = price_data[symbol].iloc[-1] if len(symbols) > 1 else price_data.iloc[-1]
        except:
            current_price = 0
            
        current_value = net_qty * current_price
        pl_val = current_value - total_cost
        pl_pct = (pl_val / total_cost * 100) if total_cost != 0 else 0
        
        stock_list.append({
            "Symbol": symbol,
            "Adet": net_qty,
            "Maliyet ($)": total_cost,
            "Ort. Fiyat ($)": avg_price,
            "Güncel Fiyat ($)": current_price,
            "Güncel Değer ($)": current_value,
            "Kâr/Zarar ($)": pl_val,
            "Kâr/Zarar (%)": pl_pct
        })

    stocks_df = pd.DataFrame(stock_list)

    # --- SUMMARY METRICS ---
    t_cost = stocks_df["Maliyet ($)"].sum()
    t_value = stocks_df["Güncel Değer ($)"].sum()
    t_pl = t_value - t_cost
    t_pl_pct = (t_pl / t_cost * 100) if t_cost != 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Toplam Maliyet", f"${t_cost:,.2f}")
    c2.metric("Güncel Değer", f"${t_value:,.2f}")
    c3.metric("Toplam K/Z ($)", f"${t_pl:,.2f}", f"{t_pl_pct:.2f}%")
    c4.metric("Aktif Hisse Sayısı", len(stocks_df))

    # --- DETAILED TABLE (Modern Formatting) ---
    st.subheader("💹 Detaylı Portföy Tablosu")
    st.dataframe(
        stocks_df,
        column_config={
            "Kâr/Zarar (%)": st.column_config.NumberColumn(format="%.2f%%"),
            "Güncel Değer ($)": st.column_config.NumberColumn(format="$%.2f"),
            "Kâr/Zarar ($)": st.column_config.NumberColumn(format="$%.2f"),
        },
        hide_index=True,
        use_container_width=True
    )
