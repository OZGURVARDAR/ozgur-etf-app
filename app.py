import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from gspread_pandas import Spread
from google.oauth2.service_account import Credentials

# -----------------------------
# STREAMLIT CONFIG
# -----------------------------
st.set_page_config(layout="wide")
st.title("📊 Portfolio vs SPY Benchmark (TWR)")

# -----------------------------
# GOOGLE SHEETS CONNECTION
# -----------------------------
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=SCOPES
)

spread = Spread(
    "Ozgur_ETF_Data",
    sheet="transactions",
    creds=creds
)

df = spread.sheet_to_df()

# -----------------------------
# DATA CLEANING
# -----------------------------
df["Date"] = pd.to_datetime(df["Date"])
df = df.sort_values("Date")

df["Quantity"] = pd.to_numeric(df["Quantity"])
df["Price"] = pd.to_numeric(df["Price"], errors="coerce")
df["Cash"] = pd.to_numeric(df["Cash"])

start_date = df["Date"].min()

# -----------------------------
# PRICE DATA
# -----------------------------
symbols = df.loc[df["Symbol"] != "CASH", "Symbol"].unique().tolist()
symbols.append("SPY")

prices = yf.download(
    symbols,
    start=start_date,
    progress=False
)["Adj Close"]

prices = prices.ffill()

# -----------------------------
# PORTFOLIO HOLDINGS OVER TIME
# -----------------------------
dates = prices.index
holdings = pd.DataFrame(0.0, index=dates, columns=symbols)

for _, row in df.iterrows():
    if row["Symbol"] != "CASH":
        holdings.loc[row["Date"]:, row["Symbol"]] += row["Quantity"]

# -----------------------------
# PORTFOLIO VALUE (EX CASH)
# -----------------------------
portfolio_value = (holdings.drop(columns="SPY") * prices.drop(columns="SPY")).sum(axis=1)

# -----------------------------
# TIME-WEIGHTED RETURN (PORTFOLIO)
# -----------------------------
portfolio_returns = portfolio_value.pct_change().fillna(0)
portfolio_twr = (1 + portfolio_returns).cumprod() * 100

# -----------------------------
# SPY TIME-WEIGHTED RETURN
# -----------------------------
spy_prices = prices["SPY"]
spy_returns = spy_prices.pct_change().fillna(0)
spy_twr = (1 + spy_returns).cumprod() * 100

# Normalize both to 100 at start
portfolio_twr /= portfolio_twr.iloc[0] / 100
spy_twr /= spy_twr.iloc[0] / 100

# -----------------------------
# PLOT
# -----------------------------
fig = go.Figure()

fig.add_trace(go.Scatter(
    x=portfolio_twr.index,
    y=portfolio_twr,
    mode="lines",
    name="Portfolio (TWR)",
    line=dict(width=3)
))

fig.add_trace(go.Scatter(
    x=spy_twr.index,
    y=spy_twr,
    mode="lines",
    name="SPY (TWR)",
    line=dict(width=2, dash="dash")
))

fig.update_layout(
    title="📈 Time-Weighted Return Comparison",
    yaxis_title="Indexed Return (Start = 100)",
    xaxis_title="Date",
    template="plotly_white",
    hovermode="x unified"
)

st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# METRICS
# -----------------------------
col1, col2 = st.columns(2)

col1.metric(
    "Portfolio Total Return",
    f"{portfolio_twr.iloc[-1] - 100:.2f}%"
)

col2.metric(
    "SPY Total Return",
    f"{spy_twr.iloc[-1] - 100:.2f}%"
)
