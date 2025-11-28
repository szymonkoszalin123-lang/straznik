import os
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime

# === KONFIGURACJA ===
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# === TWOJE POZYCJE (EDYTUJ RĘCZNIE!) ===
# Tutaj wpisujesz, co masz otwarte.
# Dostępne opcje: "LONG", "SHORT" lub brak wpisu (puste).
# Przykład: "BTC-USD": "LONG",
MOJE_POZYCJE = {
    # Wpisz tutaj aktywa, na których masz otwarte pozycje:
    # "SI=F": "LONG",      <-- Przykład (odkomentuj i zmień, gdy otworzysz)
    # "GBPPLN=X": "SHORT", <-- Przykład
    "^STOXX50E": "SHORT",
}

# === BAZA DANYCH RYNKÓW ===
# Format: [RSI_PER, RSI_BUY, RSI_SELL, RSI_EXIT_L, RSI_EXIT_S]
PORTFOLIO = {
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

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("BRAK TOKENÓW.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=data)
    except Exception: pass

def calculate_rsi(series, period):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def check_market(symbol, params, position_status):
    rsi_p, r_buy, r_sell, ex_l, ex_s = params
    
    try:
        # Pobieramy dane
        df = yf.download(symbol, period="6mo", interval="1d", progress=False)
        if df.empty: return None
        
        if isinstance(df.columns, pd.MultiIndex): df.columns = [c[0].lower() for c in df.columns]
        else: df.columns = [c.lower() for c in df.columns]

        # Obliczenia
        rsi_series = calculate_rsi(df['close'], rsi_p)
        current_rsi = rsi_series.iloc[-1]
        current_price = df['close'].iloc[-1]
        
        # --- DATA SYGNAŁU ---
        # Pobieramy datę ostatniej świecy i formatujemy na YYYY-MM-DD
        last_date = df.index[-1].strftime('%Y-%m-%d')

        msg = ""
        
        # --- LOGIKA ---
        
        # 1. Szukamy WEJŚCIA (tylko gdy nie ma pozycji)
        if position_status is None:
            if current_rsi < r_buy:
                msg += f"🟢 **OKAZJA LONG!** [{last_date}]\n{symbol}: RSI {current_rsi:.1f} (< {r_buy})\nCena: {current_price:.2f}\n\n"
            elif current_rsi > r_sell:
                msg += f"🔴 **OKAZJA SHORT!** [{last_date}]\n{symbol}: RSI {current_rsi:.1f} (> {r_sell})\nCena: {current_price:.2f}\n\n"
        
        # 2. Szukamy WYJŚCIA Z LONGA
        elif position_status == "LONG":
            if current_rsi > ex_l:
                msg += f"💰 **ZAMKNIJ LONGA!** [{last_date}]\n{symbol}: RSI {current_rsi:.1f} przebiło {ex_l}.\n\n"

        # 3. Szukamy WYJŚCIA Z SHORTA
        elif position_status == "SHORT":
            if current_rsi < ex_s:
                msg += f"💰 **ZAMKNIJ SHORTA!** [{last_date}]\n{symbol}: RSI {current_rsi:.1f} przebiło {ex_s}.\n\n"

        return msg
    except Exception:
        return None

def main():
    report = ""
    
    # Iterujemy przez rynki
    for symbol, params in PORTFOLIO.items():
        status = MOJE_POZYCJE.get(symbol, None)
        alert = check_market(symbol, params, status)
        if alert:
            report += alert
            
    if report:
        # Dodajemy czas wysłania raportu (czas serwera UTC)
        header = f"🔔 **ALARM RYNKOWY**\nData sprawdzenia: {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC\n\n"
        send_telegram(header + report)

if __name__ == "__main__":
    main()
