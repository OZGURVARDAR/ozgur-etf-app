import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go

st.set_page_config(page_title="Özgür Portfolio", layout="wide")

# -------------------------------------------------
# GOOGLE SHEET
# -------------------------------------------------
SHEET_ID = "1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

@st.cache_data(ttl=300)
def load_trades():
    df = pd.read_csv(CSV_URL)
    df["Date"] = pd.to_datetime(df["Date"])
    return df

trades = load_trades()

# -------------------------------------------------
# BASIC CHECK
# -------------------------------------------------
symbols = trades["Symbol"].unique().tolist()
start_date = trades["Date"].min()

# -------------------------------------------------
# PRICE DATA (SAĞLAM YOL)
# -------------------------------------------------
prices = yf.download(
    tickers=symbols,
    start=start_date,
    auto_adjust=True,
    progress=False
)["Close"]

# -------------------------------------------------
# POZİSYONLAR
# -------------------------------------------------
positions = pd.DataFrame(0.0, index=prices.index, columns=symbols)

for sym in symbols:
    t = trades[trades["Symbol"] == sym][["Date", "Quantity"]]
    t = t.set_index("Date").reindex(prices.index, fill_value=0)
    positions[sym] = t["Quantity"].cumsum()

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
# UI
# -------------------------------------------------
st.metric(
    "📈 Toplam Portföy Getirisi (%)",
    f"{total_return_pct:.2f}%"
)

fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=portfolio_value.index,
        y=portfolio_value,
        name="Portföy Değeri"
    )
)

fig.update_layout(
    template="plotly_dark",
    height=600,
    xaxis_rangeslider_visible=False
)

st.plotly_chart(fig, use_container_width=True)
