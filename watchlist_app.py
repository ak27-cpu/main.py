import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import os

# --- DATEI-MANAGEMENT ---
WATCHLIST_FILE = "my_watchlist.csv"

def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        return pd.read_csv(WATCHLIST_FILE)['Ticker'].tolist()
    return ["AAPL", "MSFT", "GOOGL", "AMZN"]

def save_watchlist(tickers):
    pd.DataFrame(tickers, columns=['Ticker']).to_csv(WATCHLIST_FILE, index=False)

# --- DCF MODELL LOGIK ---
def calculate_dcf(fcf, growth_rate, discount_rate=0.10, terminal_growth=0.02, years=10):
    """Berechnet den Barwert der zukünftigen Cashflows (DCF)."""
    try:
        if not fcf or fcf <= 0: return None
        
        cashflows = []
        # Projektionsphase (10 Jahre)
        current_fcf = fcf
        for year in range(1, years + 1):
            current_fcf *= (1 + growth_rate)
            # Diskontierung auf den heutigen Tag
            pv = current_fcf / ((1 + discount_rate) ** year)
            cashflows.append(pv)
        
        # Terminal Value (Wert nach 10 Jahren bis in die Ewigkeit)
        last_fcf = cashflows[-1] * ((1 + discount_rate) ** years)
        tv = (last_fcf * (1 + terminal_growth)) / (discount_rate - terminal_growth)
        pv_tv = tv / ((1 + discount_rate) ** years)
        
        return sum(cashflows) + pv_tv
    except:
        return None

# --- AKTIENFINDER PRO LOGIK ---
def calculate_pro_fair_value(info):
    try:
        current_price = info.get('currentPrice')
        eps = info.get('trailingEps')
        fcf = info.get('freeCashflow')
        shares = info.get('sharesOutstanding')
        # Erwartetes Wachstum (Analystenschätzung oder Fallback 10%)
        growth_estimate = info.get('earningsGrowth', 0.10)
        if growth_estimate is None or growth_estimate < 0: growth_estimate = 0.08
        
        # 1. Fair Value Multiplikator-Modell (EPS & FCF)
        fair_mult = 15 + (growth_estimate * 40)
        fair_mult = max(12, min(fair_mult, 28))
        
        fv_eps = eps * fair_mult if eps and eps > 0 else None
        
        fcf_per_share = (fcf / shares) if fcf and shares else None
        fv_fcf = fcf_per_share * fair_mult if fcf_per_share and fcf_per_share > 0 else None
        
        # 2. DCF Modell (Intrinsischer Wert)
        total_dcf_value = calculate_dcf(fcf, growth_estimate)
        fv_dcf = (total_dcf_value / shares) if total_dcf_value and shares else None
        
        # 3. Vereinigter Fair Value (Mittelwert aus allen validen Modellen)
        models = [v for v in [fv_eps, fv_fcf, fv_dcf] if v is not None and v > 0]
        
        if not models: return current_price, 15
        
        final_fv = sum(models) / len(models)
        return round(final_fv, 2), round(fair_mult, 1)
    except:
        return info.get('currentPrice'), 15

# --- DATEN-ANALYSE ---
def get_analysis_data(symbol):
    try:
        stock = yf.Ticker(symbol)
        info = stock.info
        df = stock.history(period="1y")
        if df.empty: return None
        
        current_price = info.get('currentPrice', df['Close'].iloc[-1])
        
        # Technik: RSI & Korrektur
        df['RSI'] = ta.rsi(df['Close'], length=14)
        rsi = df['RSI'].iloc[-1]
        
        high_52w = df['Close'].max()
        current_dd = ((current_price / high_52w) - 1) * 100
        avg_correction = (df['Close'] / df['Close'].cummax() - 1)[lambda x: x < -0.05].mean() * 100
        
        # Fundamentaldaten
        fair_value, mult = calculate_pro_fair_value(info)
        margin = (1 - (current_price / fair_value)) * 100
        
        # Status-Logik
        status = "Halten"
        if margin > 15 and rsi < 40 and current_dd <= avg_correction:
            status = "STARKER KAUF"
        elif margin > 5:
            status = "Kaufenswert"
        elif margin < -15:
            status = "Überbewertet"

        return {
            "Ticker": symbol,
            "Kurs": round(current_price, 2),
            "Fair Value (DCF+)": fair_value,
            "Margin %": round(margin, 2),
            "RSI (14)": round(rsi, 2),
            "Korrektur %": round(current_dd, 2),
            "Ø Korr. %": round(avg_correction, 2),
            "Status": status
        }
    except:
        return None

# --- UI (STREAMLIT) ---
st.set_page_config(layout="wide") # Falls separat genutzt
st.title("💎 Ultimative Aktien-Bewertung (DCF & Cashflow)")

# Sidebar
st.sidebar.header("Watchlist")
current_tickers = load_watchlist()
new_ticker = st.sidebar.text_input("Ticker Symbol:").upper()

if st.sidebar.button("Hinzufügen"):
    if new_ticker and new_ticker not in current_tickers:
        current_tickers.append(new_ticker)
        save_watchlist(current_tickers)
        st.rerun()

remove_ticker = st.sidebar.selectbox("Entfernen:", [""] + current_tickers)
if st.sidebar.button("Löschen"):
    if remove_ticker in current_tickers:
        current_tickers.remove(remove_ticker)
        save_watchlist(current_tickers)
        st.rerun()

# Tabelle anzeigen
if current_tickers:
    with st.spinner('Analysiere Fundamentaldaten und berechne DCF...'):
        results = [d for d in [get_analysis_data(s) for s in current_tickers] if d]
        df = pd.DataFrame(results)

    def style_status(row):
        color = ''
        if row['Status'] == "STARKER KAUF": color = 'background-color: #00ff00; color: black; font-weight: bold;'
        elif row['Status'] == "Kaufenswert": color = 'background-color: #90ee90; color: black;'
        elif row['Status'] == "Überbewertet": color = 'background-color: #ffcccb; color: black;'
        return [color] * len(row)

    st.dataframe(df.style.apply(style_status, axis=1).format({"Margin %": "{:.1f}%"}), use_container_width=True)

    with st.expander("🔬 Wie wir den fairen Wert berechnen"):
        st.markdown("""
        Wir nutzen eine **3-Säulen-Bewertung**:
        1. **Gewinn-Modell (FV EPS):** Bewertet die Aktie nach ihrem bereinigten Gewinn und Wachstum.
        2. **Cashflow-Modell (FV FCF):** Bewertet die Aktie nach dem tatsächlich generierten Bargeld.
        3. **DCF-Modell:** Berechnet den Barwert aller Cashflows der nächsten 10 Jahre plus Terminal Value.
        
        Die **Margin %** zeigt dir den Rabatt zum fairen Durchschnittswert. Ein 'STARKER KAUF' Signal erfordert Unterbewertung PLUS technische Überverkauftheit (RSI).
        """)
else:
    st.info("Füge Ticker in der Sidebar hinzu.")
