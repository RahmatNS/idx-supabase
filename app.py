import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from supabase import create_client

# Konfigurasi Halaman Dashboard
st.set_page_config(page_title="IHSG Daily Dashboard", layout="wide")
st.title("📈 IHSG Daily OHLC Dashboard")

# Membaca Kredensial Supabase dari Streamlit Secrets
try:
    url = str(st.secrets["SUPABASE_URL"])
    key = str(st.secrets["SUPABASE_KEY"])
    supabase = create_client(url, key)
except Exception as e:
    st.error(f"Gagal koneksi ke Supabase. Pastikan Secrets sudah disetel di Streamlit Cloud. Detail: {e}")
    st.stop()

# Fungsi untuk mengambil data dari Supabase
@st.cache_data(ttl=3600)
def load_data():
    try:
        response = supabase.table("ihsg_daily").select("*").order("date", desc=True).execute()
        df = pd.DataFrame(response.data)
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
        return df
    except Exception as e:
        st.error(f"Error mengambil data dari Supabase: {e}")
        return pd.DataFrame()

df = load_data()

def calculate_ma_signals(dataframe):
    """Add SMA/EMA values and crossover flags to an OHLC dataframe."""
    result = dataframe.sort_values("date").copy()
    close = pd.to_numeric(result["close"], errors="coerce")
    result["sma9"] = close.rolling(window=9, min_periods=9).mean()
    result["sma20"] = close.rolling(window=20, min_periods=20).mean()
    result["ema9"] = close.ewm(span=9, adjust=False, min_periods=1).mean()
    result["ema20"] = close.ewm(span=20, adjust=False, min_periods=1).mean()

    for prefix in ("ema", "sma"):
        difference = result[f"{prefix}9"] - result[f"{prefix}20"]
        result[f"golden_cross_{prefix}"] = (difference > 0) & (difference.shift(1) <= 0)
        result[f"death_cross_{prefix}"] = (difference < 0) & (difference.shift(1) >= 0)
    return result


def scan_market_signals(dataframe, days=35):
    """Find crossover events in the latest trading window for every ticker."""
    signals = []
    for ticker, ticker_data in dataframe.groupby("ticker"):
        calculated = calculate_ma_signals(ticker_data)
        recent = calculated.tail(days)
        signal_columns = {
            "golden_cross_ema": "🟢 Golden Cross EMA 9x20",
            "death_cross_ema": "🔴 Death Cross EMA 9x20",
            "golden_cross_sma": "🟢 Golden Cross MA 9x20",
            "death_cross_sma": "🔴 Death Cross MA 9x20",
        }
        for column, label in signal_columns.items():
            matches = recent[recent[column]]
            for _, row in matches.iterrows():
                signals.append({
                    "Ticker": ticker,
                    "Harga Terakhir": row["close"],
                    "Jenis Sinyal": label,
                    "Tanggal Sinyal": row["date"].strftime("%Y-%m-%d"),
                    "Volume": row["volume"],
                })
    return pd.DataFrame(signals)


def signal_status(calculated, prefix):
    latest = calculated.iloc[-1]
    if latest[f"golden_cross_{prefix}"]:
        return "Baru saja Golden Cross"
    if latest[f"death_cross_{prefix}"]:
        return "Baru saja Death Cross"
    return "Bullish" if latest[f"{prefix}9"] > latest[f"{prefix}20"] else "Bearish"


def build_price_chart(calculated, show_ema, show_sma):
    figure = go.Figure()
    figure.add_trace(go.Candlestick(
        x=calculated["date"], open=calculated["open"], high=calculated["high"],
        low=calculated["low"], close=calculated["close"], name="Harga",
    ))
    line_styles = {
        "ema9": ("EMA 9", "#d89b27", "solid"),
        "ema20": ("EMA 20", "#65b7d6", "solid"),
        "sma9": ("SMA 9", "#d89b27", "dash"),
        "sma20": ("SMA 20", "#65b7d6", "dash"),
    }
    for name, (label, color, dash) in line_styles.items():
        if (name.startswith("ema") and show_ema) or (name.startswith("sma") and show_sma):
            figure.add_trace(go.Scatter(
                x=calculated["date"], y=calculated[name], name=label,
                mode="lines", line={"color": color, "dash": dash},
            ))
    for prefix, label, color, symbol in [
        ("ema", "EMA", "#16a34a", "triangle-up"),
        ("ema", "EMA", "#dc2626", "triangle-down"),
        ("sma", "MA", "#16a34a", "triangle-up"),
        ("sma", "MA", "#dc2626", "triangle-down"),
    ]:
        event = "golden_cross" if symbol == "triangle-up" else "death_cross"
        points = calculated[calculated[f"{event}_{prefix}"]]
        if not points.empty:
            figure.add_trace(go.Scatter(
                x=points["date"], y=points["low"], mode="markers",
                name=f"{label} {'Golden' if event == 'golden_cross' else 'Death'} Cross",
                marker={"color": color, "symbol": symbol, "size": 12},
            ))
    figure.update_layout(height=600, xaxis_rangeslider_visible=False, hovermode="x unified")
    return figure


def select_screener_ticker(ticker):
    st.session_state["selected_ticker"] = ticker


# Tampilan Utama Dashboard
if not df.empty:
    df["date"] = pd.to_datetime(df["date"])
    tickers = sorted(df["ticker"].dropna().unique())
    if "selected_ticker" not in st.session_state:
        st.session_state["selected_ticker"] = tickers[0]

    analysis_tab, screener_tab = st.tabs(["📈 Analisis Saham & Chart", "🎯 Sinyal Screener (Golden & Death Cross)"])
    with analysis_tab:
        selected_ticker = st.selectbox("Pilih Saham / Indeks", tickers, key="selected_ticker")
        filtered_df = df[df["ticker"] == selected_ticker].sort_values("date")
        calculated = calculate_ma_signals(filtered_df)
        latest_row = calculated.iloc[-1]
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Tanggal Terakhir", latest_row["date"].strftime("%Y-%m-%d"))
        col2.metric("Open", f"{latest_row['open']:,.0f}")
        col3.metric("Close", f"{latest_row['close']:,.0f}")
        col4.metric("Volume", f"{latest_row['volume']:,.0f}")
        status1, status2 = st.columns(2)
        status1.metric("Status EMA 9x20", signal_status(calculated, "ema"))
        status2.metric("Status MA 9x20", signal_status(calculated, "sma"))
        show_ema = st.checkbox("Tampilkan EMA 9 & EMA 20", value=True)
        show_sma = st.checkbox("Tampilkan SMA 9 & SMA 20", value=False)
        st.plotly_chart(build_price_chart(calculated, show_ema, show_sma), use_container_width=True)
        st.subheader("Data Histori OHLC")
        st.dataframe(calculated[["date", "open", "high", "low", "close", "volume"]].sort_values("date", ascending=False), use_container_width=True, hide_index=True)

    with screener_tab:
        market_signals = scan_market_signals(df)
        signal_options = ["Semua Sinyal", "🟢 Golden Cross EMA 9x20", "🔴 Death Cross EMA 9x20", "🟢 Golden Cross MA 9x20", "🔴 Death Cross MA 9x20"]
        selected_signal = st.selectbox("Filter Sinyal", signal_options)
        if selected_signal != "Semua Sinyal" and not market_signals.empty:
            market_signals = market_signals[market_signals["Jenis Sinyal"] == selected_signal]
        if market_signals.empty:
            st.info("Tidak ada sinyal crossover dalam 35 hari perdagangan terakhir.")
        else:
            st.dataframe(market_signals.sort_values("Tanggal Sinyal", ascending=False), use_container_width=True, hide_index=True)
            screener_ticker = st.selectbox("Pilih ticker untuk chart", sorted(market_signals["Ticker"].unique()))
            st.button(
                "Buka di tab analisis",
                on_click=select_screener_ticker,
                args=(screener_ticker,),
            )
else:
    st.info("Belum ada data di database Supabase atau tabel 'ihsg_daily' masih kosong. Jalankan GitHub Actions untuk mengisi data pertama kali.")