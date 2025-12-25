import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import os
import json

# --- DATEI-MANAGEMENT ---
# Wir nutzen JSON, um auch die manuellen KGVs zu speichern
WATCHLIST_FILE = "watchlist_data.json"

def load_watchlist_data():
    if os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, 'r') as f:
            return json.load(f)
    return {"AAPL": 20.0, "MSFT": 25.0} # Standard-Beispiele

def save_watchlist_data(data):
    with open(WATCHLIST_FILE, 'w') as f:
        json.dump(data, f)

# --- DCF MODELL ---
def calculate_dcf(fcf, growth_rate, discount_rate=0.08, terminal_growth=0.02, years=10):
    try:
        if not fcf or fcf <= 0: return None
        growth_rate = max(0, min(growth_rate, 0.25)) # Plausibilitäts-Check
        cashflows = []
        current_fcf = fcf
        for year in range(1, years + 1):
            current_fcf *= (1 + growth_rate)
            pv = current_fcf / ((1 + discount_rate) ** year)
            cashflows.append(pv)
        last_fcf = cashflows[-1] * ((1 + discount_rate) ** years)
        tv = (last_fcf * (1 + terminal_growth)) / (discount_rate - terminal_growth)
        pv_tv = tv / ((1 + discount_rate) ** years)
        return sum(cashflows) + pv_tv
    except: return None

# --- FAIR VALUE BERECHNUNG ---
def calculate_pro_fair_value(info, manual_pe=None):
    try:
        current_price = info.get('currentPrice')
        eps = info.get('trailingEps')
        fcf = info.get('freeCashflow')
        shares = info.get('sharesOutstanding')
        growth = info.get('earningsGrowth', 0.10) or 0.10
        
        # KGV Multiplikator festlegen
        if manual_pe and manual_pe > 0:
            fair_mult = manual_pe
        else:
            # Automatik: Basis 15 + Wachstumskomponente
            fair_mult = 15 + (growth * 40)
            fair_mult = max(10, min(fair_mult, 30))

        # 1. Fair Value EPS
        fv_eps = eps * fair_mult if eps and eps > 0 else None
        
        # 2. Fair Value FCF
        fcf_per_share = (fcf / shares) if fcf and shares else None
        fv_fcf = fcf_per_share * fair_mult if fcf_per_share and fcf_per_share > 0 else None
        
        # 3. DCF Modell
        total_dcf = calculate_dcf(fcf, growth)
        fv_dcf = (total_dcf / shares) if total_dcf and shares else None
        
        # Mittelwert (Aktienfinder-Stil: EPS & FCF fokus)
        models = [v for v in [fv_eps, fv_fcf] if v is not None]
        if fv_dcf: models.append(fv_dcf)
        
        if not models: return current_price, fair_mult
        
        final_fv = sum(models) / len(models)
        return round(final_fv, 2), round(fair_mult, 1)
    except:
        return info.get('currentPrice'), 15.0

# --- DATEN-ANALYSE ---
def get_analysis_data(symbol, manual_pe):
    try:
        stock = yf.Ticker(symbol)
        info = stock.info
        df = stock.history(period="1y")
        if df.empty: return None
        
        current_price = info.get('currentPrice', df['Close'].iloc[-1])
        
        # Technik
        df['RSI'] = ta.rsi(df['Close'], length=14)
        rsi = df['RSI'].iloc[-1]
        
        high_52w = df['Close'].max()
        current_dd = ((current_price / high_52w) - 1) * 100
        avg_correction = (df['Close'] / df['Close'].cummax() - 1)[lambda x: x < -0.05].mean() * 100
        
        # Bewertung
        fair_value, used_mult = calculate_pro_fair_value(info, manual_pe)
        margin = (1 - (current_price / fair_value)) * 100
        
        status = "Halten"
        if margin > 15 and rsi < 40: status = "STARKER KAUF"
        elif margin > 0: status = "Fair/Günstig"
        elif margin < -15: status = "Überteuert"

        return {
            "Ticker": symbol,
            "Kurs": round(current_price, 2),
            "Faires KGV": used_mult,
            "Fair Value": fair_value,
            "Margin %": round(margin, 2),
            "RSI (14)": round(rsi, 2),
            "Korrektur %": round(current_dd, 2),
            "Ø Korr %": round(avg_correction, 2),
            "Status": status
        }
    except: return None

# --- UI (STREAMLIT) ---
st.set_page_config(layout="wide")
st.title("🎯 Aktienfinder Klon mit RSI-Timing")

# Sidebar
st.sidebar.header("Watchlist & Einstellungen")
data = load_watchlist_data()

# Ticker hinzufügen
with st.sidebar.expander("➕ Aktie hinzufügen", expanded=True):
    new_t = st.text_input("Ticker Symbol:").upper()
    new_pe = st.number_input("Faires KGV (optional):", value=0.0, step=0.5)
    if st.button("Hinzufügen"):
        if new_t:
            data[new_t] = new_pe if new_pe > 0 else 0.0
            save_watchlist_data(data)
            st.rerun()

# Ticker bearbeiten/löschen
with st.sidebar.expander("⚙️ Liste verwalten"):
    for t in list(data.keys()):
        col1, col2 = st.columns([2, 1])
        with col1:
            # Möglichkeit das KGV nachträglich zu ändern
            new_val = st.number_input(f"KGV {t}", value=float(data[t]), key=f"pe_{t}")
            if new_val != data[t]:
                data[t] = new_val
                save_watchlist_data(data)
        with col2:
            if st.button("🗑️", key=f"del_{t}"):
                del data[t]
                save_watchlist_data(data)
                st.rerun()

# Haupttabelle
if data:
    with st.spinner('Berechne Daten...'):
        results = [get_analysis_data(s, pe) for s, pe in data.items()]
        results = [r for r in results if r]
        df = pd.DataFrame(results)

    def style_table(row):
        color = ''
        if row['Status'] == "STARKER KAUF": color = 'background-color: #1e8449; color: white;'
        elif row['Status'] == "Überteuert": color = 'background-color: #922b21; color: white;'
        return [color] * len(row)

    st.subheader("Deine Watchlist Analyse")
    st.dataframe(df.style.apply(style_table, axis=1).format({"Margin %": "{:.1f}%", "Kurs": "{:.2f} €", "Fair Value": "{:.2f} €"}), use_container_width=True)

    st.info("💡 **Tipp:** Wenn du das faire KGV in der Sidebar auf '0.0' lässt, berechnet die App den Wert automatisch basierend auf dem Wachstum.")
else:
    st.info("Deine Watchlist ist leer.")
