import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

# -------------------------------------------------
# 1. AYARLAR
# -------------------------------------------------
st.set_page_config(page_title="Özgür Portföy & IBKR TWR", layout="wide", page_icon="📈")
st.sidebar.header("Ayarlar")
show_spy = st.sidebar.toggle("SPY (Benchmark) Göster", True)

# Google Sheet ID (Senin verdiğin ID)
SHEET_ID = "1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# -------------------------------------------------
# 2. VERİ ÇEKME VE TEMİZLEME
# -------------------------------------------------
@st.cache_data(ttl=300)
def get_data():
    try:
        df = pd.read_csv(SHEET_URL)
        df["Date"] = pd.to_datetime(df["Date"])
        
        # Sayısal sütunları zorla, hataları 0 yap
        for col in ["Quantity", "Price", "Cash"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        
        # Symbol boşluklarını temizle ve büyüt
        df["Symbol"] = df["Symbol"].astype(str).str.upper().str.strip()
        return df
    except Exception as e:
        st.error(f"Veri okuma hatası: {e}")
        return pd.DataFrame()

df_trades = get_data()

if df_trades.empty:
    st.warning("Veri bulunamadı. Lütfen Google Sheet bağlantısını kontrol et.")
    st.stop()

# -------------------------------------------------
# 3. PORTFÖY MOTORU (CORE ENGINE)
# -------------------------------------------------
def calculate_portfolio(trades):
    # A. Tarih Aralığı ve Semboller
    start_date = trades["Date"].min()
    end_date = pd.Timestamp.today() # Veya trades["Date"].max()
    
    # "CASH" sembolü hariç hisse senetleri
    symbols = trades.loc[trades["Symbol"] != "CASH", "Symbol"].unique().tolist()
    
    # B. Piyasa Verilerini İndir (SPY Dahil)
    tickers = symbols + ["SPY"]
    market_data = yf.download(tickers, start=start_date, end=end_date, progress=False)["Close"]
    
    # Tek hisse varsa Series gelir, DataFrame'e çevir
    if isinstance(market_data, pd.Series):
        market_data = market_data.to_frame()

    # Eğer veri içinde boşluklar varsa (Haftasonu değil, işlem günü eksikliği) doldur
    market_data = market_data.ffill()

    # C. Günlük Hesaplama Döngüsü
    # Market verisinin olduğu her gün için hesap yapacağız
    all_dates = market_data.index
    
    performance_rows = []
    
    # Kümülatif tutucular
    cum_holdings = {sym: 0.0 for sym in symbols} # Eldeki hisse adetleri
    wallet_cash = 0.0 # Cüzdandaki nakit (Boşta duran para)
    
    for current_date in all_dates:
        # O gün (veya öncesinde hafta sonu) yapılan işlemleri bul
        # Not: Basitlik için o günkü işlemleri alıyoruz. 
        # (Daha hassas modda: Bir önceki kapanıştan bugüne kadar olanları alabiliriz)
        daily_activity = trades[trades["Date"] == current_date]
        
        # 1. External Flow (Sadece "CASH" sembolü olan giriş/çıkışlar)
        # Bu para, hesaplamada 'Sermaye Artırımı' olarak kabul edilir, KAR değildir.
        external_flow = daily_activity.loc[daily_activity["Symbol"] == "CASH", "Cash"].sum()
        
        # 2. İşlemleri İşle (Internal Flow)
        for _, row in daily_activity.iterrows():
            sym = row["Symbol"]
            qty = row["Quantity"]
            cash_change = row["Cash"]
            
            # Cüzdan bakiyesini her işlemde güncelle (Alım yapınca para azalır, deposit yapınca artar)
            wallet_cash += cash_change
            
            # Hisse adedini güncelle (CASH değilse)
            if sym != "CASH" and sym in cum_holdings:
                cum_holdings[sym] += qty
        
        # 3. Gün Sonu Değerleme (Mark-to-Market)
        equity_value = 0.0
        for sym in symbols:
            if sym in market_data.columns:
                price = market_data.loc[current_date, sym]
                # Fiyat NaN ise (o gün işlem yoksa) 0 sayma, önceki fiyatı ffill yaptık zaten
                if pd.notna(price):
                    equity_value += cum_holdings[sym] * price
        
        total_nav = equity_value + wallet_cash
        
        performance_rows.append({
            "Date": current_date,
            "NAV": total_nav,
            "External_Flow": external_flow,
            "SPY_Price": market_data.loc[current_date, "SPY"] if "SPY" in market_data.columns else np.nan
        })
        
    return pd.DataFrame(performance_rows).set_index("Date")

# Hesaplamayı Başlat
df_perf = calculate_portfolio(df_trades)

# -------------------------------------------------
# 4. TWR (TIME-WEIGHTED RETURN) HESAPLAMASI
# -------------------------------------------------
# Burası sihirli kısım. External Flow'ları formülden düşüyoruz.

# Önceki günün verilerini al
df_perf["Prev_NAV"] = df_perf["NAV"].shift(1)
df_perf["Prev_NAV"].iloc[0] = 0 # İlk gün öncesi 0

# Günlük Getiri Formülü: 
# (Bugünkü NAV - Dünkü NAV - Bugün Giren Para) / (Dünkü NAV + Bugün Giren Para)
# Not: "Bugün Giren Para" paydaya eklenir çünkü o parayla gün içinde işlem yapmış olabilirsin (Basit yaklaşım).
# Veya gün sonu girdiyse paydaya eklenmez. IBKR genelde "Modified Dietz" kullanır.
# Biz en temiz yöntem olan basit TWR kullanalım:

df_perf["Daily_Return"] = 0.0

for i in range(1, len(df_perf)):
    nav_end = df_perf["NAV"].iloc[i]
    nav_start = df_perf["Prev_NAV"].iloc[i]
    flow = df_perf["External_Flow"].iloc[i]
    
    # Payda: Sermaye tabanı. 
    # Eğer gün ortasında para girdiyse, kâra etkisi olmaması için sermayeye ekliyoruz.
    denominator = nav_start + flow
    
    if denominator != 0:
        # Pay: Oluşan değer farkından, cebimizden koyduğumuz parayı (flow) düşüyoruz.
        gain_loss = nav_end - (nav_start + flow)
        df_perf.iloc[i, df_perf.columns.get_loc("Daily_Return")] = gain_loss / denominator
    else:
        df_perf.iloc[i, df_perf.columns.get_loc("Daily_Return")] = 0.0

# Kümülatif Getiri (Compound)
df_perf["Portfolio_Cum_Pct"] = (1 + df_perf["Daily_Return"]).cumprod() - 1
df_perf["Portfolio_Cum_Pct"] *= 100

# SPY Normalize Etme
spy_start = df_perf["SPY_Price"].iloc[0]
df_perf["SPY_Cum_Pct"] = ((df_perf["SPY_Price"] / spy_start) - 1) * 100

# -------------------------------------------------
# 5. GÖRSELLEŞTİRME (IBKR TARZI)
# -------------------------------------------------

# Grafik verisindeki boşlukları (haftasonları) hesapla
all_cal_days = pd.date_range(start=df_perf.index.min(), end=df_perf.index.max())
trading_days = df_perf.index
missing_dates = all_cal_days.difference(trading_days).strftime("%Y-%m-%d").tolist()

# Sonuç Kartları
last_row = df_perf.iloc[-1]
port_return = last_row["Portfolio_Cum_Pct"]
spy_return = last_row["SPY_Cum_Pct"]
alpha = port_return - spy_return
curr_nav = last_row["NAV"]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Toplam Varlık (NAV)", f"${curr_nav:,.2f}")
col2.metric("Portföy Getirisi (TWR)", f"%{port_return:.2f}", delta_color="normal")
col3.metric("SPY Getirisi", f"%{spy_return:.2f}", delta_color="normal")
col4.metric("Alpha (Fark)", f"%{alpha:.2f}", delta=f"{alpha:.2f}")

# Grafik
fig = go.Figure()

# Portföy Alanı (Dolu Grafik - Area)
fig.add_trace(go.Scatter(
    x=df_perf.index,
    y=df_perf["Portfolio_Cum_Pct"],
    mode='lines',
    name='Portföy TWR',
    line=dict(color='#00C805', width=2),
    fill='tozeroy', # IBKR tarzı altı dolu
    fillcolor='rgba(0, 200, 5, 0.1)' # Yeşil saydam
))

# Benchmark (Çizgi)
if show_spy:
    fig.add_trace(go.Scatter(
        x=df_perf.index,
        y=df_perf["SPY_Cum_Pct"],
        mode='lines',
        name='S&P 500 (SPY)',
        line=dict(color='#5b33e8', width=2) # IBKR moru
    ))

fig.update_layout(
    title="Kümülatif Getiri Karşılaştırması (%)",
    template="plotly_white",
    hovermode="x unified",
    xaxis_rangeslider_visible=False,
    height=600,
    yaxis=dict(tickformat=".2f", title="Getiri (%)"),
    xaxis=dict(
        rangebreaks=[dict(values=missing_dates)] # Boşlukları sil
    )
)

st.plotly_chart(fig, use_container_width=True)

# Debug Tablosu (Gizli)
with st.expander("Hesaplama Detaylarını İncele"):
    st.dataframe(df_perf[["NAV", "External_Flow", "Prev_NAV", "Daily_Return", "Portfolio_Cum_Pct"]])
