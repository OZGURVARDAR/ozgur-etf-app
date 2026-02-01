import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go

st.set_page_config(page_title="Özgür Portfolio Debug", layout="wide")

# -------------------------------------------------
# GOOGLE SHEET
# -------------------------------------------------
SHEET_ID = "1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

@st.cache_data(ttl=300)
def load_trades():
    df = pd.read_csv(CSV_URL)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df[df["Symbol"] != "CASH"]  # CASH TAMAMEN YOK SAYILIYOR
    return df

trades = load_trades()

# -------------------------------------------------
# BASIC CONTROLS
# -------------------------------------------------
symbols = trades["Symbol"].unique().tolist()
start_date = trades["Date"].min()

# -------------------------------------------------
# PRICE DATA (NET VE SAĞLAM)
# -------------------------------------------------
price_data = yf.download(
    tickers=symbols,
    start=start_date,
    auto_adjust=True,
    progress=False
)

prices = price_data["Close"]

# -------------------------------------------------
# POZİSYON HESABI
# -------------------------------------------------
dates = prices.index
positions = pd.DataFrame(0.0, index=dates, columns=symbols)

for sym in symbols:
    sym_trades = trades[trades["Symbol"] == sym][["Date", "Quantity"]]
    sym_trades = sym_trades.set_index("Date").reindex(dates, fill_value=0)
    positions[sym] = sym_trades["Quantity"].cumsum()

# -------------------------------------------------
# PORTFÖY DEĞERİ
# -------------------------------------------------
portfolio_value = (positions * prices).sum(axis=1)
portfolio_value = portfolio_value[portfolio_value > 0]

# -------------------------------------------------
# GERÇEK GETİRİ (%)
# -------------------------------------------------
initial_value = portfolio_value.iloc[0]
current_value = portfolio_value.iloc[-1]

total_return_pct = (current_value / initial_value - 1) * 100

# -------------------------------------------------
# UI – NET VE AÇIK
# -------------------------------------------------
st.metric(
    label="📈 Toplam Portföy Getirisi (%)",
    value=f"{total_return_pct:.2f}%"
)

# -------------------------------------------------
# GRAFİK (SADECE MUM)
# -------------------------------------------------
fig = go.Figure()

fig.add_trace(
    go.Candlestick(
        x=portfolio_value.index,
        open=portfolio_value.shift(1),
        high=portfolio_value.rolling(2).max(),
        low=portfolio_value.rolling(_
