import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def show():
    st.subheader("📈 Portfolio Chart (No-Gap TradingView Style)")

    # --- SIDEBAR ---
    chart_type = st.sidebar.selectbox("Portfolio Chart Type", ["Candlestick", "Line", "Heiken Ashi"])
    ema1_days = st.sidebar.number_input("EMA 1 (Short)", min_value=1, max_value=200, value=50)
    ema2_days = st.sidebar.number_input("EMA 2 (Long)", min_value=1, max_value=200, value=100)
    show_rsi = st.sidebar.checkbox("Show RSI", value=True)

    SHEET_URL = "https://docs.google.com/spreadsheets/d/1O_-QZBaISwueXmFB33wkljlXi_KQNPE2aEmtHOXoyyw/export?format=csv"

    @st.cache_data(ttl=300)
    def load_data():
        df = pd.read_csv(SHEET_URL)
        return df[df["Symbol"] != "CASH"].copy()

    df_stocks = load_data()
    symbols = df_stocks["Symbol"].unique().tolist()

    if not symbols:
        st.info("No stocks found in portfolio.")
        return

    # --- DATA FETCHING ---
    with st.spinner('Downloading Market Data...'):
        try:
            # 15dk veri için en güvenli aralık 59 gündür.
            data = yf.download(symbols, period="59d", interval="15m", group_by='ticker', progress=False)
        except Exception as e:
            st.error(f"API Error: {e}")
            return

    if data.empty:
        st.warning("Yahoo Finance returned no data. Check symbols or period.")
        return

    # --- PORTFOLIO CALCULATION ---
    portfolio_val = pd.Series(0.0, index=data.index)
    for symbol in symbols:
        try:
            close_s = data[symbol]['Close'] if len(symbols) > 1 else data['Close']
            qty = df_stocks.loc[df_stocks["Symbol"] == symbol, "Quantity"].sum()
            portfolio_val += close_s.ffill().fillna(0) * qty
        except: continue

    # Resample to 15m to ensure grid consistency
    df_plot = portfolio_val.resample('15T').ohlc().dropna()

    # --- INDICATORS ---
    df_plot["EMA1"] = df_plot["close"].ewm(span=ema1_days, adjust=False).mean()
    df_plot["EMA2"] = df_plot["close"].ewm(span=ema2_days, adjust=False).mean()

    if show_rsi:
        delta = df_plot["close"].diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        df_plot["RSI"] = 100 - (100 / (1 + (gain/loss)))

    # --- PLOTLY CATEGORICAL AXIS ---
    # Tarihi string formatına çeviriyoruz ki Plotly aradaki boşlukları "zaman" olarak algılamasın
    df_plot['time_label'] = df_plot.index.strftime('%d %b %H:%M')

    rows = 2 if show_rsi else 1
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_heights=[0.75, 0.25] if show_rsi else [1])

    # Chart Selection
    if chart_type == "Candlestick":
        fig.add_trace(go.Candlestick(x=df_plot['time_label'], open=df_plot['open'], high=df_plot['high'], low=df_plot['low'], close=df_plot['close'], name="Price"), row=1, col=1)
    elif chart_type == "Heiken Ashi":
        # Heiken Ashi hesaplama
        ha_c = (df_plot['open'] + df_plot['high'] + df_plot['low'] + df_plot['close']) / 4
        ha_o = (df_plot['open'].shift(1) + df_plot['close'].shift(1)) / 2
        ha_o.iloc[0] = df_plot['open'].iloc[0]
        fig.add_trace(go.Candlestick(x=df_plot['time_label'], open=ha_o, high=df_plot['high'], low=df_plot['low'], close=ha_c, name="HA"), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(x=df_plot['time_label'], y=df_plot['close'], line=dict(color='#2962FF', width=2), name="Value"), row=1, col=1)

    # EMA
    fig.add_trace(go.Scatter(x=df_plot['time_label'], y=df_plot["EMA1"], line=dict(color='orange', width=1), name=f"EMA{ema1_days}"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_plot['time_label'], y=df_plot["EMA2"], line=dict(color='blue', width=1), name=f"EMA{ema2_days}"), row=1, col=1)

    # RSI
    if show_rsi:
        fig.add_trace(go.Scatter(x=df_plot['time_label'], y=df_plot["RSI"], line=dict(color='purple', width=1.5), name="RSI"), row=2, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

    # --- FIXING THE GAPS FOREVER ---
    fig.update_xaxes(
        type='category', # BU SATIR TÜM BOŞLUKLARI SİLER
        nticks=10,       # Eksenin çok kalabalık olmaması için etiket sayısını sınırla
        tickangle=0
    )

    fig.update_layout(
        height=750,
        xaxis_rangeslider_visible=False,
        template="plotly_white",
        margin=dict(l=20, r=20, t=20, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    show()
