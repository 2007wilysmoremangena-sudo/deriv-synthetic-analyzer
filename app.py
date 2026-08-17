import json
import time
from collections import Counter

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from websocket import create_connection

WS_URL = "wss://ws.binaryws.com/websockets/v3"


st.set_page_config(
    page_title="Deriv Synthetic Analyzer Pro",
    layout="wide"
)


def make_request(payload, timeout=15):
    ws = create_connection(
        WS_URL,
        timeout=timeout,
        origin="https://deriv.com"
    )
    try:
        ws.send(json.dumps(payload))
        response = json.loads(ws.recv())
    finally:
        ws.close()

    if "error" in response:
        error = response["error"]
        raise RuntimeError(
            error.get("message", "Deriv API error")
        )

    return response


@st.cache_data(ttl=300)
def get_symbols():
    response = make_request({
        "active_symbols": "brief",
        "product_type": "basic"
    })

    return response.get("active_symbols", [])


def fetch_ticks(symbol, count=1000):
    response = make_request({
        "ticks_history": symbol,
        "count": count,
        "end": "latest",
        "style": "ticks"
    })

    history = response.get("history", {})

    return pd.DataFrame({
        "time": pd.to_datetime(
            history.get("times", []),
            unit="s"
        ),
        "price": pd.to_numeric(
            history.get("prices", []),
            errors="coerce"
        )
    }).dropna()WS_URL = "wss://ws.binaryws.com/websockets/v3"


st.set_page_config(
    page_title="Deriv Synthetic Analyzer Pro",
    layout="wide"
)


def make_request(payload, timeout=15):
    ws = create_connection(
        WS_URL,
        timeout=timeout,
        origin="https://deriv.com"
    )
    try:
        ws.send(json.dumps(payload))
        response = json.loads(ws.recv())
    finally:
        ws.close()

    if "error" in response:
        error = response["error"]
        raise RuntimeError(
            error.get("message", "Deriv API error")
        )

    return response


@st.cache_data(ttl=300)
def get_symbols():
    response = make_request({
        "active_symbols": "brief",
        "product_type": "basic"
    })

    return response.get("active_symbols", [])


def fetch_ticks(symbol, count=1000):
    response = make_request({
        "ticks_history": symbol,
        "count": count,
        "end": "latest",
        "style": "ticks"
    })

    history = response.get("history", {})

    return pd.DataFrame({
        "time": pd.to_datetime(
            history.get("times", []),
            unit="s"
        ),
        "price": pd.to_numeric(
            history.get("prices", []),
            errors="coerce"
        )
    }).dropna()

def add_indicators(df):
    x = df.copy()
    x["ema9"] = x.price.ewm(span=9, adjust=False).mean()
    x["ema21"] = x.price.ewm(span=21, adjust=False).mean()
    d = x.price.diff()
    gain = d.clip(lower=0).rolling(14).mean()
    loss = (-d.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    x["rsi"] = 100 - (100 / (1 + rs))
    e12 = x.price.ewm(span=12, adjust=False).mean()
    e26 = x.price.ewm(span=26, adjust=False).mean()
    x["macd"] = e12 - e26
    x["macd_signal"] = x.macd.ewm(span=9, adjust=False).mean()
    x["bb_mid"] = x.price.rolling(20).mean()
    sd = x.price.rolling(20).std()
    x["bb_upper"] = x.bb_mid + 2 * sd
    x["bb_lower"] = x.bb_mid - 2 * sd
    x["momentum"] = x.price.pct_change(10) * 100
    return x

def digit_analysis(df, window):
    # Decimal last digit of the displayed quote.
    vals = df.price.tail(window)
    digits = [int(str(v).replace(".", "").replace("-", "")[-1]) for v in vals]
    counts = Counter(digits)
    table = pd.DataFrame({"Digit": range(10),
                          "Count": [counts[d] for d in range(10)]})
    table["Frequency %"] = table["Count"] / len(digits) * 100
    return table

def streak_stats(df):
    vals = [int(str(v).replace(".", "").replace("-", "")[-1]) for v in df.price]
    if not vals:
        return {}
    out = {}
    for d in range(10):
        current = 0
        for v in reversed(vals):
            if v == d:
                current += 1
            else:
                break
        out[d] = current
    return out

def signal_for_row(x, i):
    if i < 30:
        return 0
    r = x.iloc[i]
    score = 0
    score += 1 if r.ema9 > r.ema21 else -1
    if pd.notna(r.rsi):
        if 50 < r.rsi < 70: score += 1
        elif 30 < r.rsi < 50: score -= 1
    score += 1 if r.macd > r.macd_signal else -1
    score += 1 if r.price > r.bb_mid else -1
    return score

def backtest(df, horizon, threshold):
    x = add_indicators(df).dropna().reset_index(drop=True)
    rows = []
    for i in range(30, len(x) - horizon):
        score = signal_for_row(x, i)
        if abs(score) < threshold:
            continue
        direction = 1 if score > 0 else -1
        entry = x.loc[i, "price"]
        exitp = x.loc[i + horizon, "price"]
        move = (exitp - entry) * direction
        rows.append({
            "time": x.loc[i, "time"],
            "direction": "UP" if direction > 0 else "DOWN",
            "score": score,
            "entry": entry,
            "exit": exitp,
            "move": move,
            "win": move > 0
        })
    result = pd.DataFrame(rows)
    if result.empty:
        return result, 0.0
    return result, float(result.win.mean() * 100)

st.title("📊 Deriv Synthetic Indices Analyzer PRO")
st.caption("Research/analysis tool. It does not place trades or guarantee outcomes.")

try:
    symbols = get_symbols()
except Exception as e:
    st.error(f"Unable to load symbols: {e}")
    st.stop()

synthetic = [s for s in symbols if str(s.get("market","")).lower() in
             {"synthetic_index", "synthetic indices", "synthetic"} or
             "synthetic" in str(s.get("submarket","")).lower() or
             str(s.get("underlying_symbol_type","")).lower() in {"synthetic_index","synthetic"}]
if not synthetic:
    synthetic = symbols

symbol_map = {}
for s in synthetic:
    code = s.get("underlying_symbol", s.get("symbol", ""))
    name = s.get("underlying_symbol_name", s.get("display_name", code))
    if code:
        symbol_map[f"{name} ({code})"] = code

st.sidebar.header("Market")
selected = st.sidebar.selectbox("Synthetic Index", list(symbol_map.keys()))
count = st.sidebar.slider("Ticks to analyze", 200, 3000, 1000, 100)
digit_window = st.sidebar.slider("Digit-analysis window", 50, 1000, 200, 50)
horizon = st.sidebar.slider("Backtest horizon (ticks)", 1, 20, 5)
threshold = st.sidebar.slider("Minimum signal score", 1, 4, 3)
auto = st.sidebar.checkbox("Auto refresh", False)
refresh_seconds = st.sidebar.slider("Refresh seconds", 2, 30, 5)

symbol = symbol_map[selected]

try:
    raw = fetch_ticks(symbol, count)
    df = add_indicators(raw)
except Exception as e:
    st.error(f"Unable to retrieve market data: {e}")
    st.stop()

latest = df.iloc[-1]
score = signal_for_row(df, len(df)-1)
signal = "BULLISH" if score >= threshold else "BEARISH" if score <= -threshold else "WAIT / MIXED"
confidence = min(100, abs(score) * 25)

c1,c2,c3,c4,c5 = st.columns(5)
c1.metric("Price", f"{latest.price:.5f}")
c2.metric("RSI", "—" if pd.isna(latest.rsi) else f"{latest.rsi:.1f}")
c3.metric("Signal", signal)
c4.metric("Score", f"{score:+d}")
c5.metric("Strength", f"{confidence}%")

tabs = st.tabs(["📈 Chart", "🔢 Digit Lab", "🧪 Backtest", "📋 Data"])

with tabs[0]:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.time, y=df.price, name="Price"))
    fig.add_trace(go.Scatter(x=df.time, y=df.ema9, name="EMA 9"))
    fig.add_trace(go.Scatter(x=df.time, y=df.ema21, name="EMA 21"))
    fig.add_trace(go.Scatter(x=df.time, y=df.bb_upper, name="BB Upper", line=dict(dash="dot")))
    fig.add_trace(go.Scatter(x=df.time, y=df.bb_lower, name="BB Lower", line=dict(dash="dot")))
    fig.update_layout(height=560, margin=dict(l=10,r=10,t=30,b=10))
    st.plotly_chart(fig, use_container_width=True)

    a,b = st.columns(2)
    with a:
        rf = go.Figure(go.Scatter(x=df.time, y=df.rsi, name="RSI"))
        rf.add_hline(y=70, line_dash="dash")
        rf.add_hline(y=30, line_dash="dash")
        rf.update_yaxes(range=[0,100])
        rf.update_layout(height=300)
        st.plotly_chart(rf, use_container_width=True)
    with b:
        mf = go.Figure()
        mf.add_trace(go.Scatter(x=df.time, y=df.macd, name="MACD"))
        mf.add_trace(go.Scatter(x=df.time, y=df.macd_signal, name="Signal"))
        mf.update_layout(height=300)
        st.plotly_chart(mf, use_container_width=True)

with tabs[1]:
    st.subheader("Last-digit distribution")
    digits = digit_analysis(raw, digit_window)
    st.dataframe(digits, hide_index=True, use_container_width=True)
    figd = go.Figure(go.Bar(x=digits.Digit, y=digits["Frequency %"]))
    figd.update_layout(xaxis_title="Last digit", yaxis_title="Frequency %", height=350)
    st.plotly_chart(figd, use_container_width=True)

    streaks = streak_stats(raw)
    current = max(streaks.items(), key=lambda kv: kv[1])
    st.write(f"Current longest same-digit streak: **digit {current[0]} × {current[1]}**")
    st.caption("Digit frequencies describe the observed sample; they do not imply that a digit is due next.")

with tabs[2]:
    st.subheader("Historical signal test")
    results, winrate = backtest(raw, horizon, threshold)
    if results.empty:
        st.warning("Not enough qualifying signals in this sample. Lower the score threshold or increase tick history.")
    else:
        b1,b2,b3 = st.columns(3)
        b1.metric("Signals tested", len(results))
        b2.metric("Historical win rate", f"{winrate:.1f}%")
        b3.metric("Average signed move", f"{results.move.mean():.6g}")
        st.dataframe(results.tail(100), hide_index=True, use_container_width=True)
        st.caption("This backtest is a simple research test and excludes spread/payout/contract pricing, execution effects, and other trading costs.")

with tabs[3]:
    st.dataframe(df.tail(200).sort_values("time", ascending=False), hide_index=True, use_container_width=True)

st.warning(
    "Synthetic-index statistics can change over time. A high historical frequency or backtest result "
    "is not a guarantee of the next outcome. Use demo testing and risk controls before considering real-money use."
)

if auto:
    time.sleep(refresh_seconds)
    st.rerun()
