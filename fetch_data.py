import os
import yfinance as yf
from supabase import create_client, Client

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
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
            supabase.table("ihsg_daily").upsert(payload, on_conflict="ticker, date").execute()
            print(f"Disimpan: {ticker} ({date_str})")

if __name__ == "__main__":
    main()