# Futures Edge Scanner V4 — Web/PWA prototype

## Chạy thử
```bash
pip install -r requirements.txt
streamlit run app.py
```

Mở địa chỉ Streamlit trên Safari iPhone.

## Deploy
Có thể deploy repository này lên Streamlit Community Cloud hoặc một server Streamlit có HTTPS. Sau khi có URL, Safari có thể mở và chọn “Add to Home Screen”.

## Tính năng hiện tại
- H4 mặc định
- 1m / 3m / 5m / 15m / 30m / 1H / 2H / 4H / 6H / 12H / 1D
- Binance Futures public OHLCV
- EMA20/50/200, RSI, ATR
- taker-buy ratio / delta proxy
- LONG / SHORT / NO TRADE
- Entry / SL / TP theo ATR
- chart tương tác

## Quan trọng
“Score confidence” hiện chỉ là điểm heuristic, KHÔNG phải xác suất thắng đã calibrated. Không dùng nó để kết luận win-rate.

Bản production tiếp theo nên thêm OI, funding, liquidation, CVD, order book, cross-market data, news/event timestamps, execution simulator và walk-forward backtest.
