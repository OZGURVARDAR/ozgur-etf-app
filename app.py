import pandas as pd
import yfinance as yf
import streamlit as st

st.set_page_config(layout="wide")

# ===============================
# GOOGLE SHEETS'TEN VERİYİ ÇEK
# ===============================
SHEET_ID = "1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw"
SHEET_NAME = "Sheet1"

url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}"
df = pd.read_csv(url)

df["Date"] = pd.to_datetime(df["Date"])
df = df.sort_values("Date")

# ===============================
# SADECE CASH FLOW'LARI AYIR
# ===============================
cash_flows = (
    df[df["Symbol"] == "CASH"]
    .groupby("Date")["Cash"]
    .sum()
)

# ===============================
# HİSSE POZİSYONLARINI HESAPLA
# ===============================
trades = df[df["Symbol"] != "CASH"]

positions = (
    trades
    .groupby(["Date", "Symbol"])["Quantity"]
    .sum()
    .groupby(level=1)
    .cumsum()
    .reset_index()
)

symbols = positions["Symbol"].unique().tolist()

# ===============================
# FİYATLARI ÇEK
# ===============================
start = df["Date"].min()
end = pd.Timestamp.today()

prices = yf.download(symbols, start=start, end=end, progress=False)["Adj Close"]

# ===============================
# GÜNLÜK PORTFÖY DEĞERİ
# ===============================
dates = prices.index
portfolio_value = pd.Series(0.0, index=dates)

for symbol in symbols:
    qty = (
        positions[positions["Symbol"] == symbol]
        .set_index("Date")["Quantity"]
        .reindex(dates)
        .ffill()
        .fillna(0)
    )
    portfolio_value += qty * prices[symbol]

# ===============================
# TWR HESABI
# ===============================
portfolio_df = pd.DataFrame({
    "PortfolioValue": portfolio_value
})

portfolio_df["CashFlow"] = cash_flows.reindex(dates).fillna(0)

portfolio_df["StartValue"] = (
    portfolio_df["PortfolioValue"].shift(1)
)

portfolio_df["DailyReturn"] = (
    (portfolio_df["PortfolioValue"] - portfolio_df["CashFlow"]) /
    portfolio_df["StartValue"]
)

portfolio_df = portfolio_df.dropna()

portfolio_df["TWR_Factor"] = 1 + portfolio_df["DailyReturn"]
portfolio_df["TWR"] = portfolio_df["TWR_Factor"].cumprod() - 1

# ===============================
# GÖSTER
# ===============================
st.title("Portföy Time-Weighted Return (TWR)")

st.metric(
    "Toplam TWR",
    f"%{portfolio_df['TWR'].iloc[-1] * 100:.2f}"
)

st.line_chart(portfolio_df["TWR"] * 100)
