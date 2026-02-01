import pandas as pd
import yfinance as yf

# --- LOAD DATA ---
df = pd.read_csv("portfolio.csv")
df["Date"] = pd.to_datetime(df["Date"])
df = df.sort_values("Date")

INITIAL_CASH = 30000

# --- CASH BALANCE ---
df["cash_flow"] = df["Cash"]
df["cash_balance"] = INITIAL_CASH + df["cash_flow"].cumsum()

# --- POSITION TRACKING ---
positions = {}
rows = []

for _, row in df.iterrows():
    symbol = row["Symbol"]

    if symbol != "CASH":
        positions[symbol] = positions.get(symbol, 0) + row["Quantity"]

    rows.append({
        "Date": row["Date"],
        "CashFlow": row["Cash"],
        "CashBalance": row["cash_balance"],
        "Positions": positions.copy()
    })

daily = pd.DataFrame(rows)

# --- MARKET VALUE ---
def market_value(date, positions):
    total = 0
    for sym, qty in positions.items():
        price = yf.download(sym, start=date, end=date + pd.Timedelta(days=1))["Adj Close"]
        if not price.empty:
            total += qty * price.iloc[0]
    return total

daily["MarketValue"] = daily.apply(
    lambda x: market_value(x["Date"], x["Positions"]), axis=1
)

daily["PortfolioValue"] = daily["MarketValue"] + daily["CashBalance"]

# --- TWR CALCULATION ---
returns = []

for i in range(1, len(daily)):
    if daily.loc[i, "CashFlow"] == 0:
        r = (daily.loc[i, "PortfolioValue"] /
             daily.loc[i-1, "PortfolioValue"]) - 1
        returns.append(1 + r)

TWR = pd.Series(returns).prod() - 1

print(f"TWR: %{TWR * 100:.2f}")
