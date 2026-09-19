import streamlit as st
import pandas as pd
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

# Fungsi untuk mengambil data ringkasan terbaru dari Supabase
@st.cache_data(ttl=3600)
def load_data():
    try:
        response = supabase.table("ihsg_daily").select("*").order("date", desc=True).limit(2000).execute()
        df = pd.DataFrame(response.data)
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
        return df
    except Exception as e:
        st.error(f"Error mengambil data dari Supabase: {e}")
        return pd.DataFrame()

# Fungsi untuk mengambil histori lengkap saham yang dipilih
@st.cache_data(ttl=3600)
def load_ticker_history(ticker: str):
    try:
        response = (
            supabase.table("ihsg_daily")
            .select("*")
            .eq("ticker", ticker)
            .order("date", desc=False)
            .execute()
        )
        df = pd.DataFrame(response.data)
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
        return df
    except Exception as e:
        st.error(f"Error mengambil data histori {ticker}: {e}")
        return pd.DataFrame()

df = load_data()

# Tampilan Utama Dashboard
if not df.empty:
    st.subheader("Daftar Semua Saham")
    latest_by_ticker = (
        df.sort_values(["ticker", "date"], ascending=[True, False])
        .drop_duplicates(subset="ticker")
        .sort_values("ticker")
    )
    page_size = st.selectbox("Jumlah saham per halaman", [25, 50, 100], index=0)
    page_count = max(1, (len(latest_by_ticker) + page_size - 1) // page_size)
    page_number = st.number_input(
        "Halaman",
        min_value=1,
        max_value=page_count,
        value=1,
        step=1,
    )
    start = (page_number - 1) * page_size
    page_df = latest_by_ticker.iloc[start:start + page_size]
    st.caption(f"Menampilkan {start + 1}-{start + len(page_df)} dari {len(latest_by_ticker)} saham")
    st.dataframe(
        page_df[["ticker", "date", "open", "high", "low", "close", "volume"]],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("---")
    # Dropdown Filter Ticker
    tickers = latest_by_ticker['ticker'].unique()
    selected_ticker = st.selectbox("Pilih Saham / Indeks:", tickers)
    
    # Filter Data berdasarkan Ticker yang dipilih dari Supabase secara lengkap
    filtered_df = load_ticker_history(selected_ticker)
    
    if not filtered_df.empty:
        # Menampilkan Metric/Ringkasan Singkat
        latest_row = filtered_df.iloc[-1]
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Tanggal Terakhir", latest_row['date'].strftime('%Y-%m-%d'))
        col1_delta = None
        col2.metric("Open", f"{latest_row['open']:,}")
        col3.metric("Close", f"{latest_row['close']:,}")
        col4.metric("Volume", f"{latest_row['volume']:,}")
        
        st.markdown("---")
        
        # Pengaturan Tampilan Chart
        st.subheader(f"📊 Pergerakan Harga - {selected_ticker}")
        
        chart_col1, chart_col2 = st.columns([1, 1])
        with chart_col1:
            chart_type = st.radio("Tipe Chart:", ["Candlestick", "Line Chart (Close)"], horizontal=True)
        with chart_col2:
            time_range = st.radio("Rentang Waktu:", ["1 Bulan", "3 Bulan", "6 Bulan", "1 Tahun", "Semua"], horizontal=True, index=4)

        chart_df = filtered_df.copy()
        if time_range == "1 Bulan":
            chart_df = chart_df[chart_df["date"] >= (chart_df["date"].max() - pd.Timedelta(days=30))]
        elif time_range == "3 Bulan":
            chart_df = chart_df[chart_df["date"] >= (chart_df["date"].max() - pd.Timedelta(days=90))]
        elif time_range == "6 Bulan":
            chart_df = chart_df[chart_df["date"] >= (chart_df["date"].max() - pd.Timedelta(days=180))]
        elif time_range == "1 Tahun":
            chart_df = chart_df[chart_df["date"] >= (chart_df["date"].max() - pd.Timedelta(days=365))]

        # Render Chart Interaktif
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots

            # Subplot: Baris 1 Harga (Candle/Line), Baris 2 Volume
            fig = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.08,
                row_heights=[0.75, 0.25],
                subplot_titles=(f"Harga {selected_ticker}", "Volume")
            )

            if chart_type == "Candlestick":
                fig.add_trace(
                    go.Candlestick(
                        x=chart_df['date'],
                        open=chart_df['open'],
                        high=chart_df['high'],
                        low=chart_df['low'],
                        close=chart_df['close'],
                        name="OHLC",
                        increasing_line_color="#26a69a",
                        decreasing_line_color="#ef5350"
                    ),
                    row=1, col=1
                )
            else:
                fig.add_trace(
                    go.Scatter(
                        x=chart_df['date'],
                        y=chart_df['close'],
                        mode='lines',
                        name="Close Price",
                        line=dict(color='#2962FF', width=2)
                    ),
                    row=1, col=1
                )

            # Bar chart volume dengan warna selaras pergerakan hari itu
            colors = [
                "#26a69a" if c >= o else "#ef5350"
                for c, o in zip(chart_df['close'], chart_df['open'])
            ]
            fig.add_trace(
                go.Bar(
                    x=chart_df['date'],
                    y=chart_df['volume'],
                    name="Volume",
                    marker_color=colors,
                    opacity=0.8
                ),
                row=2, col=1
            )

            # Cari hari-hari libur bursa yang tidak ada data perdagangannya di chart_df
            all_days = pd.date_range(start=chart_df['date'].min(), end=chart_df['date'].max(), freq='D')
            trading_days = set(chart_df['date'].dt.strftime('%Y-%m-%d'))
            holidays = [d.strftime('%Y-%m-%d') for d in all_days if d.strftime('%Y-%m-%d') not in trading_days and d.weekday() < 5]

            fig.update_layout(
                xaxis_rangeslider_visible=False,
                height=550,
                margin=dict(l=20, r=20, t=40, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                template="plotly_white"
            )

            # Sembunyikan akhir pekan (Sabtu & Minggu) dan hari libur non-trading
            rangebreak_rules = [dict(bounds=["sat", "mon"])] # hide weekend
            if holidays:
                rangebreak_rules.append(dict(values=holidays)) # hide public holidays

            fig.update_xaxes(rangebreaks=rangebreak_rules)
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            # Fallback jika plotly belum terinstall
            if chart_type == "Candlestick":
                st.line_chart(chart_df.set_index("date")[["open", "high", "low", "close"]])
            else:
                st.line_chart(chart_df.set_index("date")["close"])
            st.bar_chart(chart_df.set_index("date")["volume"])
        
        # Tabel Data OHLC
        st.subheader("Data Histori OHLC")
        st.dataframe(
            filtered_df[['date', 'open', 'high', 'low', 'close', 'volume']].sort_values("date", ascending=False),
            use_container_width=True
        )
else:
    st.info("Belum ada data di database Supabase atau tabel 'ihsg_daily' masih kosong. Jalankan GitHub Actions untuk mengisi data pertama kali.")