import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import os

# --- KONFIGURATION & SPEICHERUNG ---
WATCHLIST_FILE = "my_watchlist.csv"

def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        return pd.read_csv(WATCHLIST_FILE)['Ticker'].tolist()
    return ["AAPL", "MSFT", "GOOGL"]

def save_watchlist(tickers):
    pd.DataFrame(tickers, columns=['Ticker']).to_csv(WATCHLIST_FILE, index=False)

# --- FAIR VALUE LOGIK ---
def calculate_fair_value(info, current_price):
    """Berechnet einen gewichteten fairen Wert aus mehreren Modellen."""
    try:
        eps = info.get('trailingEps', 0)
        bvps = info.get('bookValue', 0)
        target = info.get('targetMeanPrice')
        
        # 1. Graham-Zahl (Wurzel aus 22,5 * EPS * Buchwert) - Fokus auf Substanz
        graham = (22.5 * eps * bvps)**0.5 if (eps and bvps and eps > 0 and bvps > 0) else None
        
        # 2. Ertragswert-Modell (KGV 18 als fairer Multiplikator für Qualität)
        pe_fair = eps * 18 if eps and eps > 0 else None
        
        # 3. Analysten-Konsens (Markterwartung)
        # target ist bereits definiert
        
        # Gewichteter Durchschnitt der verfügbaren Modelle
        models = [v for v in [graham, pe_fair, target] if v is not None and v > 0]
        
        if not models:
            return current_price # Fallback
        
        return sum(models) / len(models)
    except:
        return current_price

# --- DATEN-ANALYSE ---
def get_analysis_data(symbol):
    try:
        stock = yf.Ticker(symbol)
        info = stock.info
        df = stock.history(period="1y")
        if df.empty: return None
        
        current_price = df['Close'].iloc[-1]
        
        # Technik: RSI
        df['RSI'] = ta.rsi(df['Close'], length=14)
        rsi = df['RSI'].iloc[-1]
        
        # Technik: Korrektur-Statistik
        high_52w = df['Close'].max()
        current_dd = ((current_price / high_52w) - 1) * 100
        
        rolling_max = df['Close'].cummax()
        drawdowns = (df['Close'] / rolling_max - 1)
        avg_correction = drawdowns[drawdowns < -0.05].mean() * 100
        
        # Fundamentaler Fair Value
        fair_value = calculate_fair_value(info, current_price)
        margin_of_safety = (1 - (current_price / fair_value)) * 100
        
        # Signal-Logik
        # Kaufenswert wenn: RSI niedrig (<40) UND Preis unter Fair Value UND deutlicher Rücksetzer
        is_cheap = current_price < fair_value
        is_oversold = rsi < 40
        is_correction = current_dd <= avg_correction
        
        status = "Warten"
        if is_cheap and is_oversold and is_correction:
            status = "KAUFEN"
        elif is_cheap and (is_oversold or is_correction):
            status = "Beobachten"

        return {
            "Ticker": symbol,
            "Preis": round(current_price, 2),
            "Fair Value (Ø)": round(fair_value, 2),
            "Margin of Safety %": round(margin_of_safety, 2),
            "RSI (14)": round(rsi, 2),
            "Akt. Korrektur %": round(current_dd, 2),
            "Ø Korrektur %": round(avg_correction, 2),
            "Status": status
        }
    except Exception as e:
        return None

# --- UI DESIGN ---
st.title("📈 Smart Watchlist: Fair Value & Timing")

# Sidebar
st.sidebar.header("Watchlist Management")
current_tickers = load_watchlist()
new_ticker = st.sidebar.text_input("Ticker Symbol:").upper()

if st.sidebar.button("Hinzufügen"):
    if new_ticker and new_ticker not in current_tickers:
        current_tickers.append(new_ticker)
        save_watchlist(current_tickers)
        st.rerun()

remove_ticker = st.sidebar.selectbox("Ticker entfernen:", [""] + current_tickers)
if st.sidebar.button("Löschen"):
    if remove_ticker in current_tickers:
        current_tickers.remove(remove_ticker)
        save_watchlist(current_tickers)
        st.rerun()

# Analyse-Tabelle
if current_tickers:
    with st.spinner('Berechne faire Werte...'):
        data_list = [get_analysis_data(s) for s in current_tickers]
        results = [d for d in data_list if d is not None]
        df_results = pd.DataFrame(results)

    def style_status(row):
        color = ''
        if row['Status'] == "KAUFEN":
            color = 'background-color: #27ae60; color: white;' # Sattes Grün
        elif row['Status'] == "Beobachten":
            color = 'background-color: #f1c40f; color: black;' # Gelb
        return [color] * len(row)

    st.subheader("Marktbewertung")
    st.dataframe(
        df_results.style.apply(style_status, axis=1)
        .format({"Margin of Safety %": "{:.2f}%", "Akt. Korrektur %": "{:.2f}%"}),
        use_container_width=True
    )

    # Strategie-Guide
    with st.expander("Wie wird der 'Fair Value' berechnet?"):
        st.write("""
        Der faire Wert ist ein Durchschnitt aus drei Modellen:
        1. **Graham-Zahl:** Bewertet das Unternehmen nach Sachwerten und aktuellem Gewinn.
        2. **Ertrags-KGV:** Nutzt den Gewinn pro Aktie (EPS) mit einem Qualitäts-Multiplikator von 18.
        3. **Analysten-Target:** Berücksichtigt die mittlere Schätzung der Bank-Analysten.
        
        **Kauf-Signal:** Erscheint nur, wenn die Aktie unter dem fairen Wert liegt, der RSI unter 40 ist und der Rücksetzer statistisch groß genug ist.
        """)
else:
    st.info("Füge Ticker in der Sidebar hinzu, um die Analyse zu starten.")
