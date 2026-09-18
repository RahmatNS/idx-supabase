import streamlit as st
import pandas as pd
from supabase import create_client

st.set_page_config(page_title="IHSG Daily Dashboard", layout="wide")
st.title("📈 IHSG Daily OHLC Dashboard")

# Gunakan str() untuk memastikan tipe data string murni dari secrets
try:
    url = str(st.secrets["SUPABASE_URL"])
    key = str(st.secrets["SUPABASE_KEY"])
    supabase = create_client(url, key)
except Exception as e:
    st.error(f"Gagal koneksi ke Supabase. Periksa Secrets kamu. Error: {e}")
    st.stop()

@st.cache_data(ttl=3600)
def load_data():
    try:
        response = supabase.table("ihsg_daily").select("*").order("date", desc=True).execute()
        df = pd.DataFrame(response.data)
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
        return df
    except Exception as e:
        st.error(f"Error mengambil data dari database: {e}")
        return pd.DataFrame()

df = load_data()

if not df.empty:
    selected_ticker = st.selectbox("Pilih Saham/Indeks:", df['ticker'].unique())
    filtered_df = df[df['ticker'] == selected_ticker].sort_values("date")
    
    st.subheader(f"Grafik Harga Close {selected_ticker}")
    st.line_chart(filtered_df.set_index("date")["close"])
    
    st.dataframe(filtered_df[['date', 'open', 'high', 'low', 'close', 'volume']], use_container_width=True)
else:
    st.info("Belum ada data di database atau tabel masih kosong.")