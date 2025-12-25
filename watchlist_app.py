import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
from finvizfinance.quote import finvizfinance
import os

# --- KONFIGURATION & SPEICHERUNG ---
WATCHLIST_FILE = "my_watchlist.csv"

def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        return pd.read_csv(WATCHLIST_FILE)['Ticker'].tolist()
    return ["AAPL", "MSFT", "TSLA"] # Standard-Werte

def save_watchlist(tickers):
    pd.DataFrame(tickers, columns=['Ticker']).to_csv(WATCHLIST_FILE, index=False)

# --- DATEN-LOGIK ---
def get_analysis_data(symbol):
    try:
        # Berechnung der Graham-Zahl (Wurzel aus 22,5 * EPS * Buchwert pro Aktie)
# 22,5 ist der Graham-Standardfaktor (KGV 15 * KBV 1,5)
def calculate_graham_number(eps, bvps):
    if eps > 0 and bvps > 0:
        return (22.5 * eps * bvps) ** 0.5
    return None

# Integration in die Daten-Abfrage
info = stock.info
eps = info.get('trailingEps', 0)
bvps = info.get('bookValue', 0)
hist_pe = info.get('trailingPE', 20) # Aktuelles KGV als Basis
avg_pe_5y = 20 # Hier könnte man den 5-Jahres-Schnitt von yfinance laden

# Fair Value Modellierung
graham = calculate_graham_number(eps, bvps)
pe_fair_value = eps * 18 # Beispiel: Fairer Wert bei KGV 18
analyst_target = info.get('targetMeanPrice')

# Durchschnitt bilden
fair_values = [v for v in [graham, pe_fair_value, analyst_target] if v is not None]
final_fair_value = sum(fair_values) / len(fair_values) if fair_values else current_price

def get_analysis_data(symbol):
    try:
        stock = yf.Ticker(symbol)
        info = stock.info
        df = stock.history(period="1y")
        
        current_price = df['Close'].iloc[-1]
        
        # --- FUNDAMENTALER FAIR VALUE ---
        eps = info.get('trailingEps', 0)
        bvps = info.get('bookValue', 0)
        
        # 1. Graham Zahl (sehr konservativ)
        graham = (22.5 * eps * bvps)**0.5 if eps > 0 and bvps > 0 else None
        # 2. Analysten Target
        target = info.get('targetMeanPrice')
        # 3. KGV-Basis (Historisch faire Bewertung ca. 15-20x Gewinn)
        pe_fair = eps * 18 
        
        # Kombinierter Fair Value (Gewichtet)
        valid_values = [v for v in [graham, target, pe_fair] if v and v > 0]
        fair_value = sum(valid_values) / len(valid_values) if valid_values else current_price
        
        # --- TECHNIK ---
        df['RSI'] = ta.rsi(df['Close'], length=14)
        rsi = df['RSI'].iloc[-1]
        
        # Abstände & Signale
        discount = (current_price / fair_value - 1) * 100
        
        return {
            "Ticker": symbol,
            "Preis": round(current_price, 2),
            "Fair Value (Ø)": round(fair_value, 2),
            "Margin of Safety %": round(-discount, 2), # Wie viel Rabatt kriege ich?
            "RSI (14)": round(rsi, 2),
            "Status": "STARKER KAUF" if discount < -15 and rsi < 35 else "Beobachten"
        }
    except:
        return None

        
        # 1. Kursdaten via yfinance
        stock = yf.Ticker(symbol)
        df = stock.history(period="1y")
        if df.empty: return None
        
        current_price = df['Close'].iloc[-1]
        
        # RSI Berechnung mit pandas_ta
        df['RSI'] = ta.rsi(df['Close'], length=14)
        rsi = df['RSI'].iloc[-1]
        
        # Korrektur-Berechnung (Drawdown vom 52-Wochen Hoch)
        high_52w = df['Close'].max()
        current_dd = ((current_price / high_52w) - 1) * 100
        
        # Durchschnittliche Korrekturgröße (vereinfacht: Mittlere Tiefe der Rücksetzer)
        # Wir nehmen die letzten 3 großen lokalen Minima
        rolling_max = df['Close'].cummax()
        drawdowns = (df['Close'] / rolling_max - 1)
        avg_correction = drawdowns[drawdowns < -0.05].mean() * 100 # Nur Rücksetzer > 5%

        # 2. Fundamentaldaten via Finviz
        fv_data = finvizfinance(symbol).ticker_fundament()
        target_price = fv_data.get('Target Price')
        try:
            target_price = float(target_price)
        except:
            target_price = current_price # Fallback
            
        return {
            "Ticker": symbol,
            "Preis": round(current_price, 2),
            "Fair Value (Target)": target_price,
            "Abstand FV %": round(((current_price / target_price) - 1) * 100, 2),
            "RSI (14)": round(rsi, 2),
            "Akt. Korrektur %": round(current_dd, 2),
            "Ø Korrektur %": round(avg_correction, 2),
            "Status": "KAUFEN" if rsi < 35 and current_dd <= avg_correction else "Warten"
        }
    except Exception as e:
        return None

# --- UI DESIGN ---
st.set_page_config(page_title="Stock Watchlist Pro", layout="wide")
st.title("📊 Profi-Watchlist: Timing & Bewertung")

# Sidebar: Management der Watchlist
st.sidebar.header("Watchlist Verwaltung")
current_tickers = load_watchlist()

new_ticker = st.sidebar.text_input("Ticker hinzufügen (z.B. NVDA):").upper()
if st.sidebar.button("Hinzufügen"):
    if new_ticker and new_ticker not in current_tickers:
        current_tickers.append(new_ticker)
        save_watchlist(current_tickers)
        st.sidebar.success(f"{new_ticker} hinzugefügt!")
        st.rerun()

remove_ticker = st.sidebar.selectbox("Ticker entfernen:", [""] + current_tickers)
if st.sidebar.button("Löschen"):
    if remove_ticker in current_tickers:
        current_tickers.remove(remove_ticker)
        save_watchlist(current_tickers)
        st.rerun()

# Hauptbereich: Analyse
if current_tickers:
    with st.spinner('Analysiere Marktdaten...'):
        results = []
        for s in current_tickers:
            data = get_analysis_data(s)
            if data:
                results.append(data)
        
        df_results = pd.DataFrame(results)

    # Styling der Tabelle
    def style_rows(row):
        color = ''
        if row['Status'] == "KAUFEN":
            color = 'background-color: #2ecc71; color: white;' # Grün
        elif row['RSI (14)'] > 70:
            color = 'background-color: #e74c3c; color: white;' # Rot
        return [color] * len(row)

    st.subheader("Deine Favoriten im Check")
    st.dataframe(df_results.style.apply(style_rows, axis=1), use_container_width=True)

    # Legende
    st.markdown("""
    ---
    **Strategie-Check:**
    * **Fair Value:** Nutzt das mittlere Analysten-Kursziel von Finviz.
    * **Ø Korrektur:** Berechnet, wie tief die Aktie im letzten Jahr im Schnitt bei Rücksetzern gefallen ist.
    * **Kauf-Signal:** Erscheint, wenn der **RSI < 35** ist UND der aktuelle Rücksetzer größer/gleich der **Ø Korrektur** ist.
    """)
else:
    st.info("Deine Watchlist ist noch leer. Füge links Ticker hinzu.")
