import os
import yfinance as yf
from supabase import create_client, Client

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
if not url or not key:
    raise RuntimeError("SUPABASE_URL dan SUPABASE_KEY/SUPABASE_SERVICE_ROLE_KEY wajib disetel")
supabase: Client = create_client(url, key)

TICKERS = ["^JKSE", "BBCA.JK", "BBRI.JK", "TLKM.JK", "ASII.JK"]

def main():
    for ticker in TICKERS:
        df = yf.Ticker(ticker).history(period="1d")
        if not df.empty:
            row = df.iloc[-1]
            date_str = df.index[-1].strftime('%Y-%m-%d')
            payload = {
                "ticker": ticker,
                "date": date_str,
                "open": float(row['Open']),
                "high": float(row['High']),
                "low": float(row['Low']),
                "close": float(row['Close']),
                "volume": int(row['Volume'])
            }
            response = supabase.table("ihsg_daily").upsert(
                payload, on_conflict="ticker,date"
            ).execute()
            if response.data:
                print(f"Disimpan: {ticker} ({date_str})")
            else:
                raise RuntimeError(f"Supabase tidak mengembalikan data untuk {ticker}")

if __name__ == "__main__":
    main()