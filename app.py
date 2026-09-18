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
    tickers = df['ticker'].unique()
    selected_ticker = st.selectbox("Pilih Saham / Indeks:", tickers)
    
    # Filter Data berdasarkan Ticker yang dipilih
    filtered_df = df[df['ticker'] == selected_ticker].sort_values("date")
    
    # Menampilkan Metric/Ringkasan Singkat
    latest_row = filtered_df.iloc[-1]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Tanggal Terakhir", latest_row['date'].strftime('%Y-%m-%d'))
    col2.metric("Open", f"{latest_row['open']:,}")
    col3.metric("Close", f"{latest_row['close']:,}")
    col4.metric("Volume", f"{latest_row['volume']:,}")
    
    st.markdown("---")
    
    # Grafik Line Chart Harga Close
    st.subheader(f"Grafik Harga Close - {selected_ticker}")
    st.line_chart(filtered_df.set_index("date")["close"])
    
    # Tabel Data OHLC
    st.subheader("Data Histori OHLC")
    st.dataframe(
        filtered_df[['date', 'open', 'high', 'low', 'close', 'volume']].sort_values("date", ascending=False),
        use_container_width=True
    )
else:
    st.info("Belum ada data di database Supabase atau tabel 'ihsg_daily' masih kosong. Jalankan GitHub Actions untuk mengisi data pertama kali.")