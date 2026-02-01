import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# -------------------------------------------------
# 1. AYARLAR VE SAYFA DÜZENİ
# -------------------------------------------------
st.set_page_config(page_title="Özgür ETF Terminal v2", layout="wide", page_icon="📈")

st.sidebar.header("🛠 Grafik & Portföy Ayarları")

# Grafik Ayarları
chart_type = st.sidebar.selectbox("Grafik Tipi", ["Mum Grafiği (NAV)", "Çizgi (Getiri %)"])
show_benchmark = st.sidebar.toggle("Benchmark (SPY) Karşılaştır", True)

# İleride eklenebilecek özellikler için placeholder
st.sidebar.markdown("---")
st.sidebar.info("💡 İpucu: Portföy getirisi, nakit giriş/çıkışlarından arındırılarak hesaplanmıştır.")

# -------------------------------------------------
# 2. VERİ YÜKLEME VE İŞLEME (ETL)
# -------------------------------------------------
SHEET_ID = "1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

@st.cache_data(ttl=300)
def get_data():
    """Google Sheet verisini çeker ve temizler."""
    try:
        df = pd.read_csv(SHEET_URL)
        df["Date"] = pd.to_datetime(df["Date"])
        # Sayısal dönüşümler
        cols = ["Quantity", "Price", "Cash", "Commission"] # Commission varsa ekle, yoksa hata vermez
        for col in cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        return df
    except Exception as e:
        st.error(f"Veri çekme hatası: {e}")
        return pd.DataFrame()

def calculate_portfolio_performance(trades_df):
    """
    Portföy NAV ve Günlük Getirileri hesaplar.
    Gelecekteki karmaşık stratejiler için burası ana merkezdir.
    """
    if trades_df.empty:
        return None, None, None

    # 1. Milat Tarihi ve Semboller
    start_date = trades_df["Date"].min()
    symbols = sorted(trades_df.loc[trades_df["Symbol"] != "CASH", "Symbol"].unique().tolist())
    
    # 2. Piyasa Verilerini İndir (SPY dahil)
    # Ticker listesine SPY ekleyelim
    tickers = symbols + ["SPY"]
    market_data = yf.download(tickers, start=start_date, progress=False)["Close"]
    
    # Eğer tek sembol varsa yfinance serisi döner, df'e çevirelim
    if isinstance(market_data, pd.Series):
        market_data = market_data.to_frame()
    
    # Veri setindeki tüm işlem günlerini al (Tatiller ve haftasonları otomatik düşmüş olur)
    all_dates = market_data.index
    
    # 3. Günlük Pozisyon ve Nakit Akışı Hesaplama
    # Her gün için eldeki hisse adedi ve nakit bakiyesini bulacağız.
    
    # Pozisyon Tablosu (Adetler)
    pos_df = pd.DataFrame(0.0, index=all_dates, columns=symbols)
    # Nakit Akış Tablosu (Sadece o gün giren/çıkan para)
    cash_flow_daily = pd.Series(0.0, index=all_dates) 
    
    # İşlemleri günlere dağıt
    # Not: Aynı gün birden fazla işlem olabilir, groupby ile topla
    grouped_trades = trades_df.groupby(["Date", "Symbol"])[["Quantity", "Cash"]].sum().reset_index()
    
    for row in grouped_trades.itertuples():
        if row.Date in pos_df.index:
            # Sembol CASH değilse hisse adetini güncelle
            if row.Symbol in symbols:
                pos_df.loc[row.Date, row.Symbol] += row.Quantity
            
            # Nakit hareketi (Hisse alımı -Cash yazar, Para yatırma +Cash yazar)
            cash_flow_daily.loc[row.Date] += row.Cash

    # Kümülatif Pozisyonlar (Bugün elimde kaç adet var?)
    holdings = pos_df.cumsum()
    
    # Kümülatif Nakit Bakiyesi (Cüzdanda ne kadar var?)
    # Dikkat: Cash kolonunu kümülatif topluyoruz
    wallet_balance = cash_flow_daily.cumsum()

    # 4. NAV (Net Asset Value) Hesaplama
    # NAV = (Hisse Adedi * O günkü Fiyat) + Nakit
    stock_value = (holdings * market_data[symbols]).sum(axis=1)
    portfolio_nav = stock_value + wallet_balance
    
    # Veri olmayan (NAV'ın 0 veya NaN olduğu) ilk günleri temizle
    portfolio_nav = portfolio_nav[portfolio_nav != 0].dropna()
    
    # 5. SPY Benchmark Hesaplama (Normalize Edilmiş)
    spy_data = market_data["SPY"].loc[portfolio_nav.index]
    
    return portfolio_nav, spy_data, cash_flow_daily

# Veriyi Hazırla
df_trades = get_data()
if not df_trades.empty:
    nav_series, spy_series, daily_flows = calculate_portfolio_performance(df_trades)
else:
    st.warning("İşlem verisi bulunamadı.")
    st.stop()

# -------------------------------------------------
# 3. GELİŞMİŞ GETİRİ HESAPLAMASI (TWR MANTIGINA YAKIN)
# -------------------------------------------------
# Basit getiri yerine, para giriş çıkışlarını elimine ederek performans ölçelim.
# Formül: Günlük Getiri % = (Bugünkü NAV - Bugün Giren Nakit) / Dünkü NAV - 1

nav_df = pd.DataFrame({"Close": nav_series})
nav_df["Prev_Close"] = nav_df["Close"].shift(1)
nav_df["Net_Flow"] = daily_flows.reindex(nav_df.index).fillna(0)

# İlk günün getirisi 0 kabul edilir
nav_df["Daily_Ret"] = 0.0
# 2. günden itibaren hesapla
nav_df.loc[nav_df.index[1:], "Daily_Ret"] = (
    (nav_df["Close"] - nav_df["Net_Flow"]) / nav_df["Prev_Close"]
) - 1

# Kümülatif Getiri Endeksi (Başlangıç 100 veya %0)
nav_df["Cum_Return_Pct"] = ((1 + nav_df["Daily_Ret"]).cumprod() - 1) * 100

# SPY Getirisi (Basit kümülatif, çünkü SPY'a para ekleyip çıkarmıyoruz, sadece fiyatı izliyoruz)
spy_return_pct = (spy_series / spy_series.iloc[0] - 1) * 100

# OHLC Oluşturma (Görsellik için NAV üzerinden)
# Not: NAV mum grafiği toplam varlığı gösterir.
nav_ohlc = nav_df[["Close"]].copy()
nav_ohlc["Open"] = nav_ohlc["Close"].shift(1)
nav_ohlc["High"] = nav_ohlc[["Open", "Close"]].max(axis=1)
nav_ohlc["Low"] = nav_ohlc[["Open", "Close"]].min(axis=1)
nav_ohlc.dropna(inplace=True)

# -------------------------------------------------
# 4. GRAFİK OLUŞTURMA (BOŞLUKSUZ)
# -------------------------------------------------
# Grafik için boşlukları (Holidays) hesaplayalım
# Tüm takvim günleri ile bizim datamızdaki günler arasındaki farkı bulup Plotly'e "bunları gösterme" diyeceğiz.
all_calendar_dates = pd.date_range(start=nav_ohlc.index.min(), end=nav_ohlc.index.max())
trading_days = nav_ohlc.index
missing_dates = all_calendar_dates.difference(trading_days)
# Rangebreaks için format (string listesi)
missing_dates_str = [d.strftime("%Y-%m-%d") for d in missing_dates]

# Layout Ayarları
row_count = 2 if show_benchmark else 1
row_heights = [0.7, 0.3] if show_benchmark else [1.0]

fig = make_subplots(
    rows=row_count, cols=1,
    shared_xaxes=True,
    vertical_spacing=0.03,
    row_heights=row_heights,
    subplot_titles=("Portföy Değeri & NAV", "Kümülatif Getiri Karşılaştırması (%)" if show_benchmark else "")
)

# --- PANEL 1: NAV (Varlık Değeri) ---
if chart_type.startswith("Mum"):
    fig.add_trace(
        go.Candlestick(
            x=nav_ohlc.index,
            open=nav_ohlc["Open"],
            high=nav_ohlc["High"],
            low=nav_ohlc["Low"],
            close=nav_ohlc["Close"],
            name="Portföy NAV ($)"
        ), row=1, col=1
    )
else:
    # Çizgi Grafik seçilirse Getiri %'sini ana ekrana alıyoruz
    fig.add_trace(
        go.Scatter(
            x=nav_df.index,
            y=nav_df["Cum_Return_Pct"],
            name="Portföy Getiri %",
            line=dict(color="#00C805", width=2)
        ), row=1, col=1
    )

# --- PANEL 2 (veya Ana Panel): Benchmark ---
if show_benchmark:
    # Sadece Benchmark panelinde (altta) yüzdesel kıyaslama yapıyoruz
    
    # Portföy Getirisi
    fig.add_trace(
        go.Scatter(
            x=nav_df.index,
            y=nav_df["Cum_Return_Pct"],
            name="Portföy (%)",
            line=dict(color="#00C805", width=2),
            legendgroup="group2"
        ), row=2, col=1
    )
    
    # SPY Getirisi
    fig.add_trace(
        go.Scatter(
            x=spy_return_pct.index,
            y=spy_return_pct,
            name="SPY (%)",
            line=dict(color="orange", width=2, dash="dot"),
            legendgroup="group2"
        ), row=2, col=1
    )
    
    # Sıfır çizgisi
    fig.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)

# --- GENEL GRAFİK AYARLARI ---
fig.update_layout(
    template="plotly_dark",
    height=800,
    xaxis_rangeslider_visible=False,
    title_text=f"Portföy Performansı (Başlangıç: {nav_df.index[0].strftime('%d %B %Y')})",
    hovermode="x unified"
)

# BOŞLUKLARI KALDIRMA SİHRİ
fig.update_xaxes(
    rangebreaks=[
        dict(values=missing_dates_str)  # Tatilleri ve haftasonlarını gizle
    ]
)

# Metrikler
total_return = nav_df["Cum_Return_Pct"].iloc[-1]
spy_total_return = spy_return_pct.iloc[-1]
diff = total_return - spy_total_return

col1, col2, col3 = st.columns(3)
col1.metric("Portföy Getirisi", f"%{total_return:.2f}", delta_color="normal")
col2.metric("SPY Getirisi", f"%{spy_total_return:.2f}", delta_color="normal")
col3.metric("Alpha (Fark)", f"%{diff:.2f}", delta=f"{diff:.2f}")

st.plotly_chart(fig, use_container_width=True)

# Debug için veri tablosu (İsteğe bağlı açılabilir)
with st.expander("Detaylı Veri Tablosunu Göster"):
    st.dataframe(nav_df[["Close", "Net_Flow", "Daily_Ret", "Cum_Return_Pct"]].tail(10))
