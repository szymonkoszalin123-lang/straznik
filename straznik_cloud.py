import os
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime

# === KONFIGURACJA ===
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# === TWOJE POZYCJE (EDYTUJ RĘCZNIE!) ===
MOJE_POZYCJE = {
    # "BTC-USD": "LONG",
    # "SI=F": "LONG",
    "^STOXX50E": "SHORT",
}

# ==================================================
# BAZA DANYCH RYNKÓW (TUTAJ BYŁ BŁĄD - TERAZ SĄ OBIE LISTY)
# ==================================================

# 1. PORTFOLIO TREND FOLLOWING (Wybicia + EMA)
# Format: "Symbol": [IN, OUT, EMA]
PORTFOLIO_TREND = {
    "BTC-USD": [60, 30, 100],
    "ETH-USD": [60, 10, 50],
    "SOL-USD": [15, 5, 50],
    "DOT-USD": [5, 30, 30],
    "KSM-USD": [10, 30, 30],
    "DOGE-USD":[5, 10, 100],
    "LE=F":    [40, 25, 30],
    "^NDX":    [40, 50, 50]
}

# 2. PORTFOLIO MEAN REVERSION (RSI + ATR)
# Format: "Symbol": [RSI_PER, RSI_BUY, RSI_SELL, RSI_EXIT_L, RSI_EXIT_S]
PORTFOLIO_MEANREV = {
    "CC=F":  [5, 10, 90, 50, 50],
    "CT=F":  [5, 30, 80, 50, 40],
    "GC=F":  [14, 30, 90, 60, 50],
    "CL=F":  [14, 10, 70, 60, 40],
    "BZ=F":  [14, 10, 70, 60, 40],
    "RB=F":  [14, 10, 70, 50, 50],
    "SI=F":   [5, 10, 90, 50, 50],
    "^FTSE":  [14, 30, 80, 50, 50],
    "ZW=F":   [14, 30, 80, 50, 50],
    "^GDAXI": [14, 30, 80, 60, 50],
    "^FCHI":  [5, 20, 90, 60, 50],
    "^STOXX50E": [5, 30, 90, 50, 40],
    "^NDX":   [3, 30, 90, 60, 40],
    "^GSPC":  [5, 20, 90, 50, 50],
    "^VIX":   [3, 30, 70, 60, 50],
    "^N225":  [5, 10, 90, 60, 40],
    "GBPPLN=X": [3, 20, 70, 60, 40],
    "GBPJPY=X": [14, 30, 90, 60, 50]
}

# ==================================================
# FUNKCJE POMOCNICZE
# ==================================================

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("BRAK TOKENÓW (Sprawdź Secrets w GitHub).")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=data)
    except Exception: pass

def get_market_data(symbol):
    try:
        # Dodano auto_adjust=False, żeby uciszyć ostrzeżenia yfinance
        df = yf.download(symbol, period="1y", interval="1d", progress=False, auto_adjust=False)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = [c[0].lower() for c in df.columns]
        else: df.columns = [c.lower() for c in df.columns]
        return df
    except: return None

# === LOGIKA TREND FOLLOWING ===
def check_trend(symbol, params, position_status):
    in_p, out_p, ema_p = params
    df = get_market_data(symbol)
    if df is None: return None

    df['ema'] = df['close'].ewm(span=ema_p, adjust=False).mean()
    high_in = df['high'].rolling(window=in_p).max().shift(1).iloc[-1]
    low_in  = df['low'].rolling(window=in_p).min().shift(1).iloc[-1]
    
    low_out = df['low'].rolling(window=out_p).min().shift(1).iloc[-1]
    high_out = df['high'].rolling(window=out_p).max().shift(1).iloc[-1]
    
    price = df['close'].iloc[-1]
    ema = df['ema'].iloc[-1]
    last_date = df.index[-1].strftime('%Y-%m-%d')
    
    msg = ""

    if position_status is None:
        if price > ema and price > high_in:
             msg += f"🌊 **TREND LONG!** [{last_date}]\n{symbol}: Wybicie {in_p}-dni ({high_in:.2f})\nCena: {price:.2f}\n\n"
        elif price < ema and price < low_in:
             msg += f"🌊 **TREND SHORT!** [{last_date}]\n{symbol}: Wybicie {in_p}-dni ({low_in:.2f})\nCena: {price:.2f}\n\n"
    elif position_status == "LONG":
        if price < low_out:
             msg += f"🚪 **ZAMKNIJ LONG (OUT)!** [{last_date}]\n{symbol}: Wybicie {out_p}-dni ({low_out:.2f})\n\n"
    elif position_status == "SHORT":
        if price > high_out:
             msg += f"🚪 **ZAMKNIJ SHORT (OUT)!** [{last_date}]\n{symbol}: Wybicie {out_p}-dni ({high_out:.2f})\n\n"

    return msg

# === LOGIKA MEAN REVERSION ===
def calculate_rsi(series, period):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def check_meanrev(symbol, params, position_status):
    rsi_p, r_buy, r_sell, ex_l, ex_s = params
    df = get_market_data(symbol)
    if df is None: return None

    rsi_series = calculate_rsi(df['close'], rsi_p)
    current_rsi = rsi_series.iloc[-1]
    price = df['close'].iloc[-1]
    last_date = df.index[-1].strftime('%Y-%m-%d')
    
    msg = ""
    
    if position_status is None:
        if current_rsi < r_buy:
            msg += f"🧲 **OKAZJA LONG!** [{last_date}]\n{symbol}: RSI {current_rsi:.1f} (< {r_buy})\nCena: {price:.2f}\n\n"
        elif current_rsi > r_sell:
            msg += f"🧲 **OKAZJA SHORT!** [{last_date}]\n{symbol}: RSI {current_rsi:.1f} (> {r_sell})\nCena: {price:.2f}\n\n"
    
    elif position_status == "LONG":
        if current_rsi > ex_l:
            msg += f"💰 **ZAMKNIJ LONGA!** [{last_date}]\n{symbol}: RSI {current_rsi:.1f} > {ex_l}\n\n"

    elif position_status == "SHORT":
        if current_rsi < ex_s:
            msg += f"💰 **ZAMKNIJ SHORTA!** [{last_date}]\n{symbol}: RSI {current_rsi:.1f} < {ex_s}\n\n"

    return msg

# === GŁÓWNA FUNKCJA ===
def main():
    report = ""
    
    # 1. Sprawdź TREND
    for symbol, params in PORTFOLIO_TREND.items():
        status = MOJE_POZYCJE.get(symbol, None)
        alert = check_trend(symbol, params, status)
        if alert: report += alert
            
    # 2. Sprawdź MEAN REVERSION (Teraz ta zmienna istnieje!)
    for symbol, params in PORTFOLIO_MEANREV.items():
        status = MOJE_POZYCJE.get(symbol, None)
        alert = check_meanrev(symbol, params, status)
        if alert: report += alert
            
    if report:
        header = f"🔔 **RAPORT PORTFELA** ({datetime.now().strftime('%Y-%m-%d %H:%M')} UTC)\n\n"
        send_telegram(header + report)

if __name__ == "__main__":
    main()
