# --- GRAFİK SEÇENEKLERİ (SIDEBAR) ---
chart_mode = st.sidebar.selectbox("Grafik Türü", ["Candlestick", "Heiken Ashi", "Line"])

# --- GRAFİK ÇİZİMİ ---
fig = go.Figure()

# 1. Mum Tipi Seçimi (Candlestick veya Heiken Ashi)
if chart_mode == "Heiken Ashi":
    # Heiken Ashi Hesaplama
    ha_close = (df_nav['Open'] + df_nav['High'] + df_nav['Low'] + df_nav['Close']) / 4
    ha_open = [(df_nav['Open'].iloc[0] + df_nav['Close'].iloc[0]) / 2]
    for i in range(1, len(df_nav)):
        ha_open.append((ha_open[i-1] + ha_close.iloc[i-1]) / 2)
    
    df_nav['HA_Open'] = ha_open
    df_nav['HA_Close'] = ha_close
    # High ve Low değerleri HA mantığına göre normalize edilir
    df_nav['HA_High'] = df_nav[['High', 'HA_Open', 'HA_Close']].max(axis=1)
    df_nav['HA_Low'] = df_nav[['Low', 'HA_Open', 'HA_Close']].min(axis=1)

    fig.add_trace(go.Candlestick(
        x=df_nav['Date_Str'],
        open=df_nav['HA_Open'], high=df_nav['HA_High'], 
        low=df_nav['HA_Low'], close=df_nav['HA_Close'],
        increasing_line_color=up_color, decreasing_line_color=down_color,
        name="Heiken Ashi"
    ))
else:
    fig.add_trace(go.Candlestick(
        x=df_nav['Date_Str'],
        open=df_nav['Open'], high=df_nav['High'], 
        low=df_nav['Low'], close=df_nav['Close'],
        increasing_line_color=up_color, decreasing_line_color=down_color,
        name="Candlestick"
    ))

# 2. Son Fiyat Çizgisi (Kırmızı Noktalı)
last_price = df_nav['Close'].iloc[-1]
fig.add_hline(
    y=last_price, 
    line_dash="dot", 
    line_color="red", 
    line_width=1.5,
    annotation_text=f"${last_price:,.2f}", 
    annotation_position="right",
    annotation_font_color="white",
    annotation_bgcolor="red"
)

fig.update_layout(
    height=650, template="plotly_white",
    yaxis=dict(side="right", tickformat=",.0f", tickprefix="$", gridcolor="#f0f0f0"),
    xaxis=dict(type='category', nticks=10, gridcolor="#f0f0f0"),
    xaxis_rangeslider_visible=False,
    hovermode="x unified",
    margin=dict(l=0, r=80, t=30, b=10) # Sağ taraftaki fiyat etiketi için boşluk artırıldı
)
