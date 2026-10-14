import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from datetime import datetime, timezone

st.set_page_config(page_title="Futures Edge Scanner V5", page_icon="📈", layout="wide")

TF = {
    "1m":"1","3m":"3","5m":"5","15m":"15","30m":"30",
    "1H":"60","2H":"120","4H":"240","6H":"360","12H":"720","1D":"D"
}
BYBIT_BASE="https://api.bybit.com"
OKX_BASE="https://www.okx.com"
BINANCE_BASE="https://fapi.binance.com"

session=requests.Session()
session.headers.update({"User-Agent":"FuturesEdgeScanner/5.0"})

def get_json(url, params=None):
    r=session.get(url, params=params, timeout=12)
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=20)
def bybit_ohlcv(symbol, interval, limit=500):
    x=get_json(BYBIT_BASE+"/v5/market/kline",{
        "category":"linear","symbol":symbol.upper(),"interval":interval,"limit":min(limit,1000)
    })
    if x.get("retCode")!=0: raise RuntimeError(x.get("retMsg","Bybit error"))
    rows=x["result"]["list"]
    df=pd.DataFrame(rows,columns=["t","o","h","l","c","v","turnover"])
    for c in ["o","h","l","c","v","turnover"]: df[c]=pd.to_numeric(df[c],errors="coerce")
    df["t"]=pd.to_datetime(pd.to_numeric(df["t"]),unit="ms",utc=True)
    return df.sort_values("t").reset_index(drop=True)

@st.cache_data(ttl=20)
def okx_ohlcv(symbol, interval, limit=300):
    bar={"1":"1m","3":"3m","5":"5m","15":"15m","30":"30m","60":"1H","120":"2H","240":"4H","360":"6H","720":"12H","D":"1D"}[interval]
    inst=symbol.replace("USDT","-USDT-SWAP")
    x=get_json(OKX_BASE+"/api/v5/market/candles",{"instId":inst,"bar":bar,"limit":min(limit,300)})
    if x.get("code")!="0": raise RuntimeError(x.get("msg","OKX error"))
    rows=x["data"]
    df=pd.DataFrame(rows,columns=["t","o","h","l","c","vol","volCcy","volCcyQuote","confirm"])
    for c in ["o","h","l","c","vol","volCcyQuote"]: df[c]=pd.to_numeric(df[c],errors="coerce")
    df["t"]=pd.to_datetime(pd.to_numeric(df["t"]),unit="ms",utc=True)
    return df.sort_values("t").reset_index(drop=True)

@st.cache_data(ttl=20)
def binance_ohlcv(symbol, interval, limit=500):
    r=session.get(BINANCE_BASE+"/fapi/v1/klines",params={
        "symbol":symbol.upper(),"interval":{"1":"1m","3":"3m","5":"5m","15":"15m","30":"30m","60":"1h","120":"2h","240":"4h","360":"6h","720":"12h","D":"1d"}[interval],"limit":limit},timeout=12)
    r.raise_for_status()
    rows=r.json()
    df=pd.DataFrame(rows,columns=["t","o","h","l","c","v","ct","qv","n","tbv","tqv","x"])
    for c in ["o","h","l","c","v","tbv"]: df[c]=pd.to_numeric(df[c],errors="coerce")
    df["t"]=pd.to_datetime(df["t"],unit="ms",utc=True)
    return df[["t","o","h","l","c","v"]]

@st.cache_data(ttl=30)
def bybit_extras(symbol):
    oi=get_json(BYBIT_BASE+"/v5/market/open-interest",{
        "category":"linear","symbol":symbol,"intervalTime":"4h","limit":1
    })
    fr=get_json(BYBIT_BASE+"/v5/market/funding/history",{
        "category":"linear","symbol":symbol,"limit":1
    })
    oi_val=np.nan
    funding=np.nan
    if oi.get("retCode")==0 and oi["result"]["list"]:
        oi_val=float(oi["result"]["list"][0]["openInterest"])
    if fr.get("retCode")==0 and fr["result"]["list"]:
        funding=float(fr["result"]["list"][0]["fundingRate"])*100
    return oi_val,funding

@st.cache_data(ttl=30)
def okx_extras(symbol):
    inst=symbol.replace("USDT","-USDT-SWAP")
    oi=get_json(OKX_BASE+"/api/v5/public/open-interest",{"instType":"SWAP","instId":inst})
    fr=get_json(OKX_BASE+"/api/v5/public/funding-rate",{"instId":inst})
    oi_val=np.nan; funding=np.nan
    if oi.get("code")=="0" and oi["data"]:
        oi_val=float(oi["data"][0].get("oi",np.nan))
    if fr.get("code")=="0" and fr["data"]:
        funding=float(fr["data"][0].get("fundingRate",np.nan))*100
    return oi_val,funding

def tech(df):
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
    d["ret"]=d.c.pct_change()
    return d

def fetch_all(symbol, interval):
    out={}
    errors={}
    for name,fn in [("Bybit",bybit_ohlcv),("OKX",okx_ohlcv),("Binance",binance_ohlcv)]:
        try: out[name]=fn(symbol,interval)
        except Exception as e: errors[name]=str(e)
    return out,errors

def consensus(frames):
    rows=[]
    for ex,d in frames.items():
        if len(d)<50: continue
        x=tech(d).iloc[-1]
        trend=1 if x.c>x.ema20>x.ema50 else -1 if x.c<x.ema20<x.ema50 else 0
        mom=1 if x.rsi>55 else -1 if x.rsi<45 else 0
        score=trend*22+mom*12+(8 if x.c>x.ema200 else -8)
        side="LONG" if score>=20 else "SHORT" if score<=-20 else "NO TRADE"
        rows.append([ex,float(x.c),float(x.rsi),float(score),side])
    return pd.DataFrame(rows,columns=["Exchange","Price","RSI","Score","Signal"])

st.title("📈 Futures Edge Scanner V5 — Multi-Exchange")
st.caption("H4 mặc định • Bybit + OKX + Binance • public market data • consensus signal")

with st.sidebar:
    symbol=st.text_input("Coin Futures","BTCUSDT").upper().strip()
    tf_name=st.selectbox("Timeframe",list(TF.keys()),index=7)
    exchanges=st.multiselect("Sàn",["Bybit","OKX","Binance"],["Bybit","OKX","Binance"])
    rr=st.slider("Risk / Reward",1.0,5.0,2.0,0.5)
    st.button("🔄 Refresh",use_container_width=True)

frames,errors=fetch_all(symbol,TF[tf_name])
frames={k:v for k,v in frames.items() if k in exchanges}
if not frames:
    st.error("Không lấy được dữ liệu từ sàn nào.")
    for k,v in errors.items(): st.warning(f"{k}: {v}")
    st.stop()

tab1,tab2,tab3=st.tabs(["📊 Consensus","🏦 Exchanges","📈 Chart"])

with tab1:
    cons=consensus(frames)
    long_n=int((cons.Signal=="LONG").sum()); short_n=int((cons.Signal=="SHORT").sum())
    if long_n>short_n and long_n>=2: overall="LONG"
    elif short_n>long_n and short_n>=2: overall="SHORT"
    else: overall="NO TRADE"
    agreement=max(long_n,short_n)/max(len(cons),1)*100
    c1,c2,c3=st.columns(3)
    c1.metric("Multi-exchange signal",overall)
    c2.metric("Agreement",f"{agreement:.0f}%")
    c3.metric("Exchanges online",len(cons))
    st.dataframe(cons,use_container_width=True,hide_index=True)

    if overall!="NO TRADE":
        prices=cons.Price
        entry=float(prices.mean())
        # Use ATR from first available exchange as execution proxy.
        base=tech(next(iter(frames.values())))
        atr=float(base.iloc[-1].atr)
        sl=entry-atr if overall=="LONG" else entry+atr
        tp=entry+rr*atr if overall=="LONG" else entry-rr*atr
        st.info(f"Entry consensus {entry:,.2f} | SL {sl:,.2f} | TP {tp:,.2f} | R:R {rr:.1f}")

with tab2:
    rows=[]
    for ex,d in frames.items():
        oi=funding=np.nan
        try:
            if ex=="Bybit": oi,funding=bybit_extras(symbol)
            elif ex=="OKX": oi,funding=okx_extras(symbol)
        except Exception: pass
        x=tech(d).iloc[-1]
        rows.append({"Exchange":ex,"Price":x.c,"RSI":x.rsi,"ATR":x.atr,"OI":oi,"Funding %":funding})
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    if errors:
        st.caption("Sàn không truy cập được trong lần quét này:")
        for k,v in errors.items(): st.write(f"- {k}: {v}")

with tab3:
    fig=go.Figure()
    for ex,d in frames.items():
        fig.add_trace(go.Scatter(x=d.t,y=d.c,name=ex))
    fig.update_layout(height=520,margin=dict(l=10,r=10,t=30,b=10),xaxis_title="UTC",yaxis_title="Price")
    st.plotly_chart(fig,use_container_width=True)
    st.caption("Giá được lấy riêng từ từng sàn; chênh lệch giữa các sàn là một tín hiệu/risks khác nhau, không phải lỗi.")
