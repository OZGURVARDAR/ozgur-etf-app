import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

# -------------------------------------------------
# 1. AYARLAR & SAYFA YAPISI
# -------------------------------------------------
st.set_page_config(page_title="Özgür Portföy Terminal v4", layout="wide", page_icon="📊")

st.sidebar.header("🛠 Grafik & Strateji")
chart_mode = st.sidebar.selectbox("Grafik Tipi", ["Çizgi Grafik", "Mum Grafiği", "Heikin Ashi"])
show_benchmark = st.sidebar.toggle("SPY Karşılaştır", True)

# Google Sheet Verisi
SHEET_ID = "1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw"
URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# -------------------------------------------------
# 2. VERİ YÜKLEME VE TEMİZLEME
# -------------------------------------------------
@st.cache_data(ttl=300)
def load_and_clean_data():
    df = pd.read_csv(URL)
    df["Date"] = pd.to_datetime(df["Date"])
    for col in ["Quantity", "Price", "Cash"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    df["Symbol"] = df["Symbol"].str.strip().str.upper()
    return df.sort_values("Date")

df_trades = load_and_clean_data()
milat_date = df_trades["Date"].min()

# -------------------------------------------------
# 3. PORTFÖY HESAPLAMA MOTORU (Doğru Getiri Mantığı)
# -------------------------------------------------
def calculate_performance(trades):
    symbols = sorted([s for s in trades["Symbol"].unique() if s != "CASH"])
    
    # Piyasa verilerini çek (SPY dahil)
    market_data = yf.download(symbols + ["SPY"], start=milat_date, progress=False)["Close"]
    if isinstance(market_data, pd.Series): market_data = market_data.to_frame()
    market_data = market_data.ffill()
    
    all_dates = market_data.index
    perf_data = []
    
    # Takip değişkenleri
    current_holdings = {sym: 0.0 for sym in symbols}
    cash_in_hand = 0.0      # Portföydeki nakit (Alım satımlarla değişir)
    invested_capital = 0.0  # Cebimizden çıkan toplam para (External Flow)
    
    for dt in all_dates:
        # O günkü işlemler
        daily_trades = trades[trades["Date"] == dt]
        
        day_external_flow = 0.0 # O gün dışarıdan eklenen nakit
        
        for _, row in daily_trades.iterrows():
            if row["Symbol"] == "CASH":
                # Dışarıdan para girişi (Deposit)
                cash_in_hand += row["Cash"]
                day_external_flow += row["Cash"]
                invested_capital += row["Cash"]
            else:
                # Hisse işlemi
                current_holdings[row["Symbol"]] += row["Quantity"]
                cash_in_hand += row["Cash"] # (Qty * Price + Komisyon zaten Excel'inde Cash sütununda)

        # Portföy Değeri (Mark-to-Market)
        market_value = sum(current_holdings[s] * market_data.loc[dt, s] for s in symbols if s in market_data.columns)
        total_nav = market_value + cash_in_hand
        
        perf_data.append({
            "Date": dt,
            "NAV": total_nav,
            "External_Flow": day_external_flow,
            "Invested_Capital": invested_capital,
            "SPY_Price": market_data.loc[dt, "SPY"]
        })

    perf_df = pd.DataFrame(perf_data).set_index("Date")
    return perf_df

perf_df = calculate_performance(df_trades)

# -------------------------------------------------
# 4. TWR (TIME-WEIGHTED RETURN) HESAPLAMA
# -------------------------------------------------
# Nakit girişlerinden arındırılmış günlük yüzde değişim
perf_df["Prev_NAV"] = perf_df["NAV"].shift(1)
perf_df["Daily_Return"] = 0.0

# Formül: (Bugünkü NAV - Eklenen Para - Dünkü NAV) / (Dünkü NAV + Eklenen Para)
for i in range(1, len(perf_df)):
    row = perf_df.iloc[i]
    prev_nav = row["Prev_NAV"]
    flow = row["External_Flow"]
    
    # Payda: Önceki bakiye + yeni eklenen para (Sermaye tabanı)
    denominator = prev_nav + flow
    if denominator > 0:
        # Net kâr = Bugünkü değer - (Dünkü değer + bugün cebimden koyduğum)
        net_profit = row["NAV"] - (prev_nav + flow)
        perf_df.iloc[i, perf_df.columns.get_loc("Daily_Return")] = net_profit / denominator

# Kümülatif Getiri
perf_df["Port_Cum_Return"] = (1 + perf_df["Daily_Return"]).cumprod() - 1
perf_df["SPY_Cum_Return"] = (perf_df["SPY_Price"] / perf_df["SPY_Price"].iloc[0]) - 1

# -------------------------------------------------
# 5. GRAFİK HAZIRLIĞI (OHLC & HEIKIN ASHI)
# -------------------------------------------------
# NAV bazlı Mum grafiği için OHLC oluşturma
perf_df["Open"] = perf_df["NAV"].shift(1).fillna(perf_df["NAV"])
perf_df["High"] = perf_df[["Open", "NAV"]].max(axis=1)
perf_df["Low"] = perf_df[["Open", "NAV"]].min(axis=1)
perf_df["Close"] = perf_df["NAV"]

if chart_mode == "Heikin Ashi":
    # HA Hesaplama
    ha_close = (perf_df["Open"] + perf_df["High"] + perf_df["Low"] + perf_df["Close"]) / 4
    ha_open = ha_close.copy()
    for i in range(1, len(perf_df)):
        ha_open.iloc[i] = (ha_open.iloc[i-1] + ha_close.iloc[i-1]) / 2
    ha_high = perf_df[["High", "Open", "Close"]].max(axis=1) # Basitleştirilmiş
    ha_low = perf_df[["Low", "Open", "Close"]].min(axis=1)   # Basitleştirilmiş
    perf_df["Open"], perf_df["High"], perf_df["Low"], perf_df["Close"] = ha_open, ha_high, ha_low, ha_close

# -------------------------------------------------
# 6. GÖRSELLEŞTİRME
# -------------------------------------------------
# Tatil günlerini x ekseninden kaldır
all_days = pd.date_range(perf_df.index.min(), perf_df.index.max())
trading_days = perf_df.index
missing_dates = all_days.difference(trading_days).strftime("%Y-%m-%d").tolist()

fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])

# Üst Panel: Portföy Değeri (Seçilen tipte)
if chart_mode in ["Mum Grafiği", "Heikin Ashi"]:
    fig.add_trace(go.Candlestick(
        x=perf_df.index, open=perf_df["Open"], high=perf_df["High"],
        low=perf_df["Low"], close=perf_df["Close"], name="NAV (USD)"
    ), row=1, col=1)
else:
    fig.add_trace(go.Scatter(
        x=perf_df.index, y=perf_df["NAV"], mode='lines', name="NAV (USD)", line=dict(color='#00C805')
    ), row=1, col=1)

# Alt Panel: Getiri Karşılaştırması (%)
fig.add_trace(go.Scatter(
    x=perf_df.index, y=perf_df["Port_Cum_Return"]*100,
    name="Portföy (%)", line=dict(color='#00C805', width=2), fill='tozeroy', fillcolor='rgba(0, 200, 5, 0.1)'
), row=2, col=1)

if show_benchmark:
    fig.add_trace(go.Scatter(
        x=perf_df.index, y=perf_df["SPY_Cum_Return"]*100,
        name="SPY (%)", line=dict(color='orange', dash='dot')
    ), row=2, col=1)

# Layout Ayarları
fig.update_layout(height=850, template="plotly_dark", xaxis_rangeslider_visible=False, hovermode="x unified")
fig.update_xaxes(rangebreaks=[dict(values=missing_dates)])

# Metrikler
total_gain_pct = perf_df["Port_Cum_Return"].iloc[-1] * 100
spy_gain_pct = perf_df["SPY_Cum_Return"].iloc[-1] * 100

st.title("📈 Özgür ETF Portföy Analizi")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Güncel NAV", f"${perf_df['NAV'].iloc[-1]:,.2f}")
c2.metric("Net Getiri (%)", f"%{total_gain_pct:.2f}")
c3.metric("SPY Getiri (%)", f"%{spy_gain_pct:.2f}")
c4.metric("Alpha", f"%{(total_gain_pct - spy_gain_pct):.2f}")

st.plotly_chart(fig, use_container_width=True)
