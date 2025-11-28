import os
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime

# === KONFIGURACJA ZMIENNYCH ŚRODOWISKOWYCH (SEKRETY) ===
# W chmurze nie wpisujemy haseł w kodzie! Pobieramy je z "sejf" GitHuba.
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# === TWOJE PORTFOLIO MEAN REVERSION ===
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
        print("BRAK TOKENÓW! Ustaw Secrets w GitHub.")
        return
        
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=data)
        print(f"Wysłano powiadomienie.")
    except Exception as e:
        print(f"Błąd wysyłania: {e}")

def calculate_rsi(series, period):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def check_market(symbol, params):
    rsi_p, r_buy, r_sell, ex_l, ex_s = params
    try:
        # Pobieramy historię
        df = yf.download(symbol, period="6mo", interval="1d", progress=False)
        if df.empty: return None
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0].lower() for c in df.columns]
        else:
            df.columns = [c.lower() for c in df.columns]

        rsi_series = calculate_rsi(df['close'], rsi_p)
        current_rsi = rsi_series.iloc[-1]
        current_price = df['close'].iloc[-1]
        
        msg = ""
        if current_rsi < r_buy:
            msg += f"🟢 **WEJŚCIE LONG!**\n{symbol}: RSI {current_rsi:.1f} (Próg {r_buy})\nCena: {current_price:.2f}\n\n"
        elif current_rsi > r_sell:
            msg += f"🔴 **WEJŚCIE SHORT!**\n{symbol}: RSI {current_rsi:.1f} (Próg {r_sell})\nCena: {current_price:.2f}\n\n"
        elif current_rsi > ex_l:
            msg += f"💰 **ZAMKNIJ LONG?**\n{symbol}: RSI {current_rsi:.1f} > Wyjście ({ex_l})\n\n"
        elif current_rsi < ex_s:
            msg += f"💰 **ZAMKNIJ SHORT?**\n{symbol}: RSI {current_rsi:.1f} < Wyjście ({ex_s})\n\n"

        return msg
    except Exception:
        return None

# --- GŁÓWNA FUNKCJA (Uruchamiana raz) ---
def main():
    print("--- Start Skanowania ---")
    report = ""
    for symbol, params in PORTFOLIO.items():
        alert = check_market(symbol, params)
        if alert:
            report += alert
            
    if report:
        header = f"🔔 **ALARM RYNKOWY** ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n\n"
        send_telegram(header + report)
    else:
        print("Brak sygnałów.")

if __name__ == "__main__":
    main()