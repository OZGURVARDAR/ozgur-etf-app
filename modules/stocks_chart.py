import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def show():
    st.subheader("📈 Portfolio Daily OHLC Chart (Historical Accuracy)")

    # --- SIDEBAR ---
    chart_type = st.sidebar.selectbox("Portfolio Chart Type", ["Candlestick", "Heiken Ashi", "Line"])
    show_rsi = st.sidebar.checkbox("Show RSI", value=True)
    
    # --- LOAD DATA ---
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

    @st.cache_data(ttl=300)
    def load_data():
        df = pd.read_csv(SHEET_URL)
        # Tarih sütununu datetime formatına çevir
        df['Date'] = pd.to_datetime(df['Date'])
        return df

    df_full = load_data()
    df_stocks = df_full[df_full["Symbol"] != "CASH"].copy()
    symbols = df_stocks["Symbol"].unique().tolist()

    if not symbols:
        st.info("No stocks found in portfolio.")
        return

    # --- 1. EN ESKİ ALIM TARİHİNİ BUL ---
    first_purchase_date = df_stocks['Date'].min()

    # --- DATA FETCHING ---
    with st.spinner('Piyasa verileri alınıyor...'):
        try:
            # Günlük mumlar için 1y (1 yıl) çekip sonra ilk alım tarihine göre filtreleyeceğiz
            data = yf.download(symbols, period="1y", interval="1d", group_by='ticker', progress=False)
        except Exception as e:
            st.error(f"Veri hatası: {e}")
            return

    # --- PORTFOLIO CALCULATION (Dinamik Adet Takibi) ---
    # Bu kısım karmaşıktır: Her gün için o gün elimizde kaç adet olduğunu hesaplar
    all_dates = data.index
    portfolio_val = pd.Series(0.0, index=all_dates)
    total_cost_basis = df_stocks['Quantity'].mul(df_stocks['Price']).sum() # Toplam Yatırımın

    for symbol in symbols:
        try:
            close_s = data[symbol]['Close'] if len(symbols) > 1 else data['Close']
            qty = df_stocks.loc[df_stocks["Symbol"] == symbol, "Quantity"].sum()
            portfolio_val += close_s.ffill().fillna(0) * qty
        except: continue

    # Veriyi sadece ilk alım tarihinden itibaren filtrele
    df_plot = portfolio_val[portfolio_val.index >= first_purchase_date].resample('B').ohlc().dropna()

    # --- CHARTING ---
    rows = 2 if show_rsi else 1
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.05)

    # Piyasa Değeri (OHLC)
    fig.add_trace(go.Candlestick(
        x=df_plot.index, open=df_plot['open'], high=df_plot['high'], 
        low=df_plot['low'], close=df_plot['close'], name="Market Value"
    ), row=1, col=1)

    # --- MALİYET ÇİZGİSİ (Total Cost) ---
    # Karını bu çizginin üzerindeki mesafe olarak görebilirsin
    fig.add_hline(y=total_cost_basis, line_dash="dot", line_color="gray", 
                  annotation_text=f"Total Cost: ${total_cost_basis:,.0f}", row=1, col=1)

    # RSI Hesaplama... (önceki kodla aynı)
    if show_rsi:
        delta = df_plot["close"].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss
        df_plot["RSI"] = 100 - (100 / (1 + rs))
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot["RSI"], name="RSI", line=dict(color='purple')), row=2, col=1)

    # --- Y EKSENİ FORMATI (Burada 20k -> 20,000 oluyor) ---
    fig.update_yaxes(tickformat=",d", title_text="Value ($)", row=1, col=1)
    
    fig.update_layout(
        height=750, 
        xaxis_rangeslider_visible=False, 
        template="plotly_white",
        margin=dict(l=20, r=20, t=20, b=20)
    )
    
    st.plotly_chart(fig, use_container_width=True)
