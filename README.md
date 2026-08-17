# Deriv Synthetic Indices Analyzer PRO

Features:
- Live/historical Deriv tick data
- EMA 9/21, RSI, MACD, Bollinger Bands
- Composite bullish/bearish/wait score
- Last-digit frequency analysis
- Same-digit streak statistics
- Simple historical signal backtest
- Interactive charts
- Auto refresh
- No automatic trading

## Run

pip install -r requirements.txt
streamlit run app.py

The app uses Deriv's public market-data endpoints. No trading token is required for the analysis features.

Important: this is a research/statistical tool. It does not guarantee future outcomes and the backtest does not model actual contract payouts, execution, or trading costs.
