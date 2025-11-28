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
        df = yf.download(symbol, period="6mo", interval="1d", progress=False)
        if df.empty: return None
        
        if isinstance(df.columns, pd.MultiIndex): df.columns = [c[0].lower() for c in df.columns]
        else: df.columns = [c.lower() for c in df.columns]

        rsi_series = calculate_rsi(df['close'], rsi_p)
        current_rsi = rsi_series.iloc[-1]
        current_price = df['close'].iloc[-1]
        
        msg = ""
        
        # --- LOGIKA FILTROWANIA SYGNAŁÓW ---
        
        # 1. Jeśli NIE MAMY pozycji (status jest None) -> Szukamy tylko WEJŚCIA
        if position_status is None:
            if current_rsi < r_buy:
                msg += f"🟢 **OKAZJA LONG!**\n{symbol}: RSI {current_rsi:.1f} (Taniej niż {r_buy})\nCena: {current_price:.2f}\n\n"
            elif current_rsi > r_sell:
                msg += f"🔴 **OKAZJA SHORT!**\n{symbol}: RSI {current_rsi:.1f} (Drożej niż {r_sell})\nCena: {current_price:.2f}\n\n"
        
        # 2. Jeśli mamy LONGA -> Szukamy tylko WYJŚCIA z Longa
        elif position_status == "LONG":
            if current_rsi > ex_l:
                msg += f"💰 **ZAMKNIJ LONGA!**\n{symbol}: RSI {current_rsi:.1f} przebiło próg {ex_l}.\n\n"

        # 3. Jeśli mamy SHORTA -> Szukamy tylko WYJŚCIA z Shorta
        elif position_status == "SHORT":
            if current_rsi < ex_s:
                msg += f"💰 **ZAMKNIJ SHORTA!**\n{symbol}: RSI {current_rsi:.1f} przebiło próg {ex_s}.\n\n"

        return msg
    except Exception:
        return None

def main():
    report = ""
    
    # Iterujemy przez wszystkie rynki
    for symbol, params in PORTFOLIO.items():
        # Sprawdzamy, czy mamy otwartą pozycję w naszym rejestrze
        status = MOJE_POZYCJE.get(symbol, None) # Zwraca "LONG", "SHORT" lub None
        
        alert = check_market(symbol, params, status)
        if alert:
            report += alert
            
    if report:
        header = f"🔔 **ALARM PORTFELA** ({datetime.now().strftime('%H:%M')})\n\n"
        send_telegram(header + report)
    # Jeśli nie ma raportu, bot milczy (zgodnie z życzeniem)

if __name__ == "__main__":
    main()
