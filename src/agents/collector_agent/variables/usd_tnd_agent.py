import yfinance as yf

df = yf.download("USDTND=X", start="2023-01-01")
df = df[["Close"]].reset_index()
df.columns = ["date", "usd_tnd"]
df.to_csv("data/raw/usd_tnd.csv", index=False)