import yfinance as yf
import pandas as pd

def test_fetch():
    symbol = "NQ=F"
    ticker = yf.Ticker(symbol)
    df = ticker.history(period="1mo", interval="1h")
    print(f"Symbol: {symbol}")
    print(f"Data found: {not df.empty}")
    if not df.empty:
        print(df.head())

if __name__ == "__main__":
    test_fetch()
