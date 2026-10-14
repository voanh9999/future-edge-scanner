# Futures Edge Scanner V5 Multi-Exchange

Sources:
- Bybit Linear Futures public REST
- OKX SWAP public REST
- Binance USDⓈ-M Futures public REST (graceful failure if the hosting IP receives HTTP 451)

Features:
- H4 default; selectable 1m, 3m, 5m, 15m, 30m, 1H, 2H, 4H, 6H, 12H, 1D
- Multi-exchange price/RSI/trend consensus
- Bybit/OKX open interest + funding where available
- Graceful per-exchange failure
- No API keys required for public market data

Deploy main file: app.py
