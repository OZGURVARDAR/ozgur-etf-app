import streamlit as st
import pandas as pd
import yfinance as yf

# -------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------
st.set_page_config(layout="wide")
st.title("📈 Portfolio Dashboard (Core + Contribution)")

# -------------------------------------------------
# GOOGLE SHEETS CSV LINK
# -------------------------------------------------
SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"
)

# -------------------------------------------------
# LOAD & CLEAN DATA
# -------------------------------------------------
df = pd.read_csv(SHEET_URL)

df["Date"] = pd.to_datetime(df["Date"])
df["Quantity"] = pd.to_numeric(df["Quantity"], errors="raise")
df["Price"] = pd.to_numeric(df["Price"], errors="raise")

# CASH işlemleri portföy hesaplarına dahil edilmez
df = df[df["Symbol"] != "CASH"]


# -------------------------------------------------
# CORE PORTFOLIO CALCULATION ENGINE (LOCKED)
# -------------------------------------------------
def calculate_portfolio_metrics(df: pd.DataFrame) -> dict:
    """
    Core portfolio calculation engine.
    This logic is locked to preserve historical correctness (%11.48).
    """

    df = df.copy()

    # --- INVESTED CAPITAL ---
    df["Cost"] = df["Quantity"] * df["Price"]
    invested_capital = df.loc[df["Quantity"] > 0, "Cost"].sum()

    # --- CURRENT VALUE ---
    symbols = df["Symbol"].unique().tolist()

    prices = yf.download(
        symbols,
        period="5d",
        progress=False
    )["Close"]

    if isinstance(prices, pd.Series):
        prices = prices.to_frame()

    def get_last_price(symbol: str) -> float:
        return prices[symbol].dropna().iloc[-1]

    current_value = 0.0
    symbol_data = []

    for symbol in symbols:
        net_quantity = df.loc[df["Symbol"] == symbol, "Quantity"].sum()
        last_price = get_last_price(symbol)
        value = net_quantity * last_price

        current_value += value

        symbol_data.append({
            "Symbol": symbol,
            "Net Quantity": net_quantity,
            "Last Price": last_price,
            "Current Value": value
        })

    # --- RETURN ---
    total_return_pct = (
        (current_value - invested_capital) / invested_capital * 100
    )

    return {
        "invested_capital": invested_capital,
        "current_value": current_value,
        "total_return_pct": total_return_pct,
        "symbol_breakdown": pd.DataFrame(symbol_data)
    }


# -------------------------------------------------
# RUN CORE ENGINE
# -------------------------------------------------
metrics = calculate_portfolio_metrics(df)

invested_capital = metrics["invested_capital"]
current_value = metrics["current_value"]
total_return_pct = metrics["total_return_pct"]
symbol_breakdown = metrics["symbol_breakdown"]

# -------------------------------------------------
# CONTRIBUTION ANALYSIS
# -------------------------------------------------
symbol_breakdown["Weight (%)"] = (
    symbol_breakdown["Current Value"] / current_value * 100
)

symbol_breakdown = symbol_breakdown.sort_values(
    "Weight (%)", ascending=False
)

# -------------------------------------------------
# OUTPUT — CORE METRICS
# -------------------------------------------------
col1, col2, col3 = st.columns(3)

col1.metric("Invested Capital ($)", f"{invested_capital:,.2f}")
col2.metric("Current Value ($)", f"{current_value:,.2f}")
col3.metric("Total Portfolio Return (%)", f"{total_return_pct:.2f}%")

st.divider()

# -------------------------------------------------
# OUTPUT — CONTRIBUTION TABLE
# -------------------------------------------------
st.subheader("📊 Stock Contribution Analysis")

st.dataframe(
    symbol_breakdown.style.format({
        "Last Price": "{:.2f}",
        "Current Value": "{:,.2f}",
        "Weight (%)": "{:.2f}%"
    }),
    use_container_width=True
)

# -------------------------------------------------
# OUTPUT — CONTRIBUTION CHART
# -------------------------------------------------
st.subheader("🥧 Portfolio Weight Distribution")

st.plotly_chart(
    {
        "data": [{
            "labels": symbol_breakdown["Symbol"],
            "values": symbol_breakdown["Weight (%)"],
            "type": "pie",
            "hole": 0.4
        }],
        "layout": {
            "showlegend": True
        }
    },
    use_container_width=True
)
