import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go

st.set_page_config(page_title="Futures Edge Scanner V4", page_icon="📈", layout="wide")

TF = {"1m":"1m","3m":"3m","5m":"5m","15m":"15m","30m":"30m","1H":"1h","2H":"2h","4H":"4h","6H":"6h","12H":"12h","1D":"1d"}
LIMIT=500

@st.cache_data(ttl=30)
def candles(symbol, interval, limit=500):
    url="https://fapi.binance.com/fapi/v1/klines"
    r=requests.get(url, params={"symbol":symbol.upper(),"interval":interval,"limit":limit}, timeout=10)
    r.raise_for_status()
    x=r.json()
    df=pd.DataFrame(x, columns=["t","o","h","l","c","v","ct","qv","n","tbv","tqv","x"])
    for c in ["o","h","l","c","v","tbv"]: df[c]=pd.to_numeric(df[c])
    df["t"]=pd.to_datetime(df["t"],unit="ms")
    return df

def indicators(df):
    d=df.copy()
    d["ema20"]=d.c.ewm(span=20,adjust=False).mean()
    d["ema50"]=d.c.ewm(span=50,adjust=False).mean()
    d["ema200"]=d.c.ewm(span=200,adjust=False).mean()
    delta=d.c.diff()
    gain=delta.clip(lower=0).ewm(alpha=1/14,adjust=False).mean()
    loss=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean()
    d["rsi"]=100-(100/(1+gain/loss.replace(0,np.nan)))
    tr=pd.concat([d.h-d.l,(d.h-d.c.shift()).abs(),(d.l-d.c.shift()).abs()],axis=1).max(axis=1)
    d["atr"]=tr.ewm(alpha=1/14,adjust=False).mean()
    d["taker_ratio"]=d.tbv/d.v.replace(0,np.nan)
    d["delta_proxy"]=2*d.tbv-d.v
    return d

def score(d):
    x=d.iloc[-1]; s=0; reasons=[]
    if x.c>x.ema20>x.ema50: s+=22; reasons.append("Trend tăng")
    elif x.c<x.ema20<x.ema50: s-=22; reasons.append("Trend giảm")
    if x.rsi>55: s+=12; reasons.append("RSI bullish")
    elif x.rsi<45: s-=12; reasons.append("RSI bearish")
    if x.taker_ratio>.52: s+=15; reasons.append("Taker buy mạnh")
    elif x.taker_ratio<.48: s-=15; reasons.append("Taker sell mạnh")
    if x.delta_proxy>0: s+=8
    else: s-=8
    if x.c>x.ema200: s+=8
    else: s-=8
    # Proxy probability; intentionally labeled score-based, not calibrated probability.
    confidence=min(95,max(5,50+0.55*s))
    side="LONG" if s>=20 else "SHORT" if s<=-20 else "NO TRADE"
    return s,confidence,side,reasons

st.title("📈 Futures Edge Scanner V4")
st.caption("Web/PWA prototype • H4 mặc định • dữ liệu Binance Futures public API • score chưa phải xác suất win-rate đã hiệu chuẩn")

with st.sidebar:
    symbol=st.text_input("Coin Futures","BTCUSDT").upper().strip()
    tf_name=st.selectbox("Timeframe",list(TF.keys()),index=7)
    mode=st.selectbox("Mode",["Live Signal","Backtest (demo)"])
    rr=st.slider("Risk / Reward",1.0,5.0,2.0,0.5)
    run=st.button("🔄 Quét tín hiệu",use_container_width=True)

try:
    df=indicators(candles(symbol,TF[tf_name],LIMIT))
    s,conf,side,reasons=score(df)
    last=df.iloc[-1]
    atr=float(last.atr)
    entry=float(last.c)
    sl=entry-atr if side=="LONG" else entry+atr if side=="SHORT" else np.nan
    tp=entry+rr*atr if side=="LONG" else entry-rr*atr if side=="SHORT" else np.nan

    c1,c2,c3,c4=st.columns(4)
    c1.metric("Signal",side)
    c2.metric("Score",f"{s:+.0f}")
    c3.metric("Score confidence",f"{conf:.0f}%")
    c4.metric("Price",f"{entry:,.2f}")

    if side!="NO TRADE":
        st.info(f"Entry {entry:,.2f}  |  SL {sl:,.2f}  |  TP {tp:,.2f}  |  R:R {rr:.1f}")
    else:
        st.warning("NO TRADE — chưa đủ lợi thế theo bộ lọc hiện tại.")

    st.write("**Lý do chính:**", " • ".join(reasons) if reasons else "Không có")

    fig=go.Figure()
    fig.add_trace(go.Candlestick(x=df.t,open=df.o,high=df.h,low=df.l,close=df.c,name="Price"))
    fig.add_trace(go.Scatter(x=df.t,y=df.ema20,name="EMA20"))
    fig.add_trace(go.Scatter(x=df.t,y=df.ema50,name="EMA50"))
    fig.add_trace(go.Scatter(x=df.t,y=df.ema200,name="EMA200"))
    fig.update_layout(height=520,xaxis_rangeslider_visible=False,margin=dict(l=10,r=10,t=30,b=10))
    st.plotly_chart(fig,use_container_width=True)

    a,b,c=st.columns(3)
    a.metric("RSI",f"{last.rsi:.1f}")
    b.metric("Taker buy ratio",f"{last.taker_ratio:.1%}")
    c.metric("ATR",f"{atr:,.2f}")

    st.subheader("Recent candles")
    st.dataframe(df[["t","o","h","l","c","v","rsi","taker_ratio"]].tail(20).iloc[::-1],use_container_width=True,hide_index=True)

except Exception as e:
    st.error(f"Không tải được dữ liệu: {e}")
    st.info("Nếu Binance Futures bị chặn theo khu vực/mạng, thử lại sau hoặc dùng VPN/server deploy.")
