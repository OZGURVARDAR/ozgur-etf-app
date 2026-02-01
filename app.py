import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# -------------------------------------------------
# 1. AYARLAR VE SAYFA DÜZENİ
# -------------------------------------------------
st.set_page_config(page_title="Özgür ETF Terminal v3", layout="wide", page_icon="📈")

st.sidebar.header("🛠 Grafik & Portföy Ayarları")
chart_type = st.sidebar.selectbox("Grafik Tipi", ["Mum Grafiği (NAV)", "Çizgi (Getiri %)"])
show_benchmark = st.sidebar.toggle("Benchmark (SPY) Karşılaştır", True)

# -------------------------------------------------
# 2. VERİ YÜKLEME VE İŞLEME
# -------------------------------------------------
SHEET_ID = "1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

@st.cache_data(ttl=300)
def get_data():
    try:
        df = pd.read_csv(SHEET_URL)
        df["Date"] = pd.to_datetime(df["Date"])
        cols = ["Quantity", "Price", "Cash"]
        for col in cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        return df
    except Exception as e:
        st.error(f"Veri hatası: {e}")
        return pd.DataFrame()

def calculate_portfolio_performance(trades_df):
    if trades_df.empty: return None, None

    # --- A. TARİH VE SEMBOL HAZIRLIĞI ---
    start_date = trades_df["Date"].min()
    symbols = sorted(trades_df.loc[trades_df["Symbol"] != "CASH", "Symbol"].unique().tolist())
    
    # SPY ve Hisse Verilerini Çek
    tickers = symbols + ["SPY"]
    # Not: Bugüne kadar olan veriyi çekmek için end belirtmiyoruz veya dinamik yapıyoruz
    market_data = yf.download(tickers, start=start_date, progress=False)["Close"]
    
    if isinstance(market_data, pd.Series):
        market_data = market_data.to_frame()
        
    # --- B. GÜNLÜK POZİSYON VE NAKİT AKIŞI ---
    # Tüm işlem günlerini içeren boş bir iskelet oluştur
    all_dates = market_data.index
    pos_df = pd.DataFrame(0.0, index=all_dates, columns=symbols)
    cash_flow_daily = pd.Series(0.0, index=all_dates)
    
    # İşlemleri günlere işle
    grouped = trades_df.groupby(["Date", "Symbol"])[["Quantity", "Cash"]].sum().reset_index()
    
    for row in grouped.itertuples():
        # Eğer işlem tarihi market datasında yoksa (örn: pazar günü), en yakın sonraki iş gününe kaydırabiliriz
        # Ancak basitlik adına sadece market datasında olan tarihlerle eşleşenleri alalım ya da reindex kullanalım.
        # Burada tam eşleşme arıyoruz, eğer haftasonu işlem girildiyse o günkü fiyat olmadığı için sonraki pazartesiye yansıtmak gerekebilir.
        # Şimdilik market datadaki tarihlerle işlem yapıyoruz:
        
        if row.Date in pos_df.index:
            if row.Symbol in symbols:
                pos_df.loc[row.Date, row.Symbol] += row.Quantity
            cash_flow_daily.loc[row.Date] += row.Cash
        else:
            # Eğer tarih indexte yoksa (Haftasonu vs), en yakın geçerli tarihe ekle
            nearest_idx = all_dates.searchsorted(row.Date)
            if nearest_idx < len(all_dates):
                real_date = all_dates[nearest_idx]
                if row.Symbol in symbols:
                    pos_df.loc[real_date, row.Symbol] += row.Quantity
                cash_flow_daily.loc[real_date] += row.Cash

    # Kümülatif Adetler (Bugün elimde ne var?)
    holdings = pos_df.cumsum()
    
    # Kümülatif Nakit Bakiyesi (Cüzdan)
    wallet_balance = cash_flow_daily.cumsum()

    # --- C. NAV HESAPLAMA ---
    # NAV = (Adet * Fiyat) + Nakit Bakiye
    stock_val = (holdings * market_data[symbols]).sum(axis=1)
    nav = stock_val + wallet_balance
    
    # --- D. PERFORMANS DATAFRAME OLUŞTURMA ---
    perf = pd.DataFrame({
        "NAV": nav,
        "Net_Flow": cash_flow_daily,  # O gün giren/çıkan taze para
        "SPY_Price": market_data["SPY"]
    })
    
    # Sadece portföyde paranın olduğu günleri alalım
    perf = perf[perf["NAV"] != 0].copy()
    
    return perf

df_trades = get_data()
perf_df = None

if not df_trades.empty:
    perf_df = calculate_portfolio_performance(df_trades)

if perf_df is None or perf_df.empty:
    st.warning("Gösterilecek veri yok.")
    st.stop()

# -------------------------------------------------
# 3. DOĞRU GETİRİ HESAPLAMASI (FIXED TWR)
# -------------------------------------------------

# Önceki günün NAV'ını al
perf_df["Prev_NAV"] = perf_df["NAV"].shift(1).fillna(0)

# Kritik Düzeltme: Getiri Hesabı
# Formül: (NAV_End - NAV_Start - Flow) / (NAV_Start + Flow)
# Eğer NAV_Start + Flow = 0 ise (İlk gün), getiri 0'dır.

perf_df["Daily_Ret"] = 0.0

for i in range(len(perf_df)):
    if i == 0:
        # İlk gün getiri hesaplanmaz, 0 kabul edilir.
        perf_df.iloc[i, perf_df.columns.get_loc("Daily_Ret")] = 0.0
    else:
        nav_end = perf_df.iloc[i]["NAV"]
        flow = perf_df.iloc[i]["Net_Flow"]
        nav_start = perf_df.iloc[i]["Prev_NAV"]
        
        # Payda: Başlangıç sermayesi + Gün içinde giren para
        denominator = nav_start + flow
        
        if denominator == 0:
            # Payda sıfırsa (henüz para yoksa) getiri 0
            ret = 0.0
        else:
            # Pay: Kâr/Zarar (Toplam varlık - (Önceki varlık + Eklenen para))
            profit = nav_end - (nav_start + flow)
            ret = profit / denominator
            
        perf_df.iloc[i, perf_df.columns.get_loc("Daily_Ret")] = ret

# Kümülatif Getiriye Dönüştürme
perf_df["Cum_Return"] = (1 + perf_df["Daily_Ret"]).cumprod()
perf_df["Cum_Return_Pct"] = (perf_df["Cum_Return"] - 1) * 100

# SPY Getirisi (Portföyün başladığı günden itibaren normalize et)
spy_start_price = perf_df["SPY_Price"].iloc[0]
perf_df["SPY_Return_Pct"] = ((perf_df["SPY_Price"] / spy_start_price) - 1) * 100

# OHLC Hazırlığı (NAV için)
ohlc_df = perf_df[["NAV"]].copy()
ohlc_df.rename(columns={"NAV": "Close"}, inplace=True)
ohlc_df["Open"] = ohlc_df["Close"].shift(1)
ohlc_df["Open"].iloc[0] = ohlc_df["Close"].iloc[0] # İlk gün açılışı kapanışa eşitle
ohlc_df["High"] = ohlc_df[["Open", "Close"]].max(axis=1)
ohlc_df["Low"] = ohlc_df[["Open", "Close"]].min(axis=1)

# -------------------------------------------------
# 4. GRAFİK
# -------------------------------------------------
# Tatil günlerini grafikten silmek için
all_days = pd.date_range(start=perf_df.index.min(), end=perf_df.index.max())
trading_days = perf_df.index
missing = all_days.difference(trading_days).strftime("%Y-%m-%d").tolist()

rows = 2 if show_benchmark else 1
row_heights = [0.7, 0.3] if show_benchmark else [1]

fig = make_subplots(
    rows=rows, cols=1,
    shared_xaxes=True,
    vertical_spacing=0.05,
    row_heights=row_heights
)

# --- ANA GRAFİK ---
if chart_type.startswith("Mum"):
    fig.add_trace(go.Candlestick(
        x=ohlc_df.index,
        open=ohlc_df["Open"], high=ohlc_df["High"],
        low=ohlc_df["Low"], close=ohlc_df["Close"],
        name="Portföy Değeri ($)"
    ), row=1, col=1)
else:
    fig.add_trace(go.Scatter(
        x=perf_df.index, y=perf_df["Cum_Return_Pct"],
        name="Portföy Getirisi (%)",
        line=dict(color="#00C805", width=2)
    ), row=1, col=1)

# --- BENCHMARK GRAFİĞİ ---
if show_benchmark:
    # Portföy
    fig.add_trace(go.Scatter(
        x=perf_df.index, y=perf_df["Cum_Return_Pct"],
        name="Portföy (%)",
        line=dict(color="#00C805", width=2),
        legendgroup="g2"
    ), row=2, col=1)
    
    # SPY
    fig.add_trace(go.Scatter(
        x=perf_df.index, y=perf_df["SPY_Return_Pct"],
        name="SPY (%)",
        line=dict(color="orange", dash="dot", width=2),
        legendgroup="g2"
    ), row=2, col=1)
    
    fig.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)

# Metrikler
total_ret = perf_df["Cum_Return_Pct"].iloc[-1]
spy_ret = perf_df["SPY_Return_Pct"].iloc[-1]
alpha = total_ret - spy_ret

st.markdown(f"### 📊 Güncel Durum: {perf_df.index[-1].strftime('%d %B %Y')}")
col1, col2, col3 = st.columns(3)
col1.metric("Portföy Getirisi", f"%{total_ret:.2f}", delta=None)
col2.metric("SPY Getirisi", f"%{spy_ret:.2f}", delta=None)
col3.metric("Alpha", f"%{alpha:.2f}", delta=f"{alpha:.2f}")

fig.update_layout(
    template="plotly_dark",
    height=800,
    xaxis_rangeslider_visible=False,
    title="Portföy Performans Analizi",
    hovermode="x unified"
)
fig.update_xaxes(rangebreaks=[dict(values=missing)])

st.plotly_chart(fig, use_container_width=True)

# Debug için tabloyu açıp kontrol edebilirsin
with st.expander("Hesaplama Detayları (Kontrol Tablosu)"):
    st.dataframe(perf_df[["NAV", "Net_Flow", "Prev_NAV", "Daily_Ret", "Cum_Return_Pct"]].style.format("{:.2f}"))
