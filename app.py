import pandas as pd
import numpy as np
import streamlit as st
import yfinance as yf

st.set_page_config(layout="wide")
st.title("📊 Portfolio Performance – Time Weighted Return (TWR)")

# =========================
# 1️⃣ GOOGLE SHEETS OKU
# =========================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

df = pd.read_csv(SHEET_URL)
df["Date"] = pd.to_datetime(df["Date"])
df = df.sort_values("Date")

# =========================
# 2️⃣ SEMBOLLER
# =========================
symbols = sorted(df.loc[df["Symbol"] != "CASH", "Symbol"].unique())

start = df["Date"].min()
end = df["Date"].max()

# =========================
# 3️⃣ FİYATLAR (ROBUST)
# =========================
raw_prices = yf.download(
    symbols,
    start=start,
    end=end,
    progress=False,
    auto_adjust=False
)

if isinstance(raw_prices.columns, pd.MultiIndex):
    prices = raw_prices["Adj Close"] if "Adj Close" in raw_prices.columns.levels[0] else raw_prices["Close"]
else:
    prices = raw_prices.to_frame(name=symbols[0])

prices = prices.ffill()

# =========================
# 4️⃣ GÜNLÜK POZİSYONLAR
# =========================
positions = (
    df[df["Symbol"] != "CASH"]
    .pivot_table(index="Date", columns="Symbol", values="Quantity", aggfunc="sum")
    .fillna(0)
    .cumsum()
)

positions = positions.reindex(prices.index).ffill().fillna(0)

# =========================
# 5️⃣ PORTFÖY DEĞERİ
# =========================
portfolio_value = (positions * prices).sum(axis=1)

# =========================
# 6️⃣ EXTERNAL CASH FLOWS
# =========================
cash_flows = (
    df.groupby("Date")["Cash"].sum()
    .reindex(portfolio_value.index)
    .fillna(0)
)

# =========================
# 7️⃣ TWR HESABI
# =========================
twr_returns = []

prev_value = None

for date in portfolio_value.index:
    V = portfolio_value.loc[date]
    CF = cash_flows.loc[date]

    if prev_value is None:
        prev_value = V
        continue

    if prev_value != 0:
        r = (V - CF) / prev_value - 1
        twr_returns.append(r)

    prev_value = V

twr = np.prod([1 + r for r in twr_returns]) - 1

# =========================
# 8️⃣ BENCHMARK (SPY)
# =========================
spy = yf.download("SPY", start=start, end=end, progress=False)["Adj Close"].ffill()
spy_return = spy.iloc[-1] / spy.iloc[0] - 1

# =========================
# 9️⃣ GRAFİK
# =========================
st.subheader("📈 Performance Comparison")

perf = pd.DataFrame({
    "Portfolio (TWR)": (1 + pd.Series(twr_returns, index=portfolio_value.index[1:])).cumprod(),
    "SPY": (spy / spy.iloc[0])
})

st.line_chart(perf)

# =========================
# 🔟 SONUÇLAR
# =========================
st.subheader("📌 Summary")

st.metric("Portfolio TWR", f"%{twr*100:.2f}")
st.metric("SPY Return", f"%{spy_return*100:.2f}")
