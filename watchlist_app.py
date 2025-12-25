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
    return ["AAPL", "MSFT", "GOOGL", "TSLA"]

def save_watchlist(tickers):
    pd.DataFrame(tickers, columns=['Ticker']).to_csv(WATCHLIST_FILE, index=False)

# --- AKTIENFINDER-LOGIK (FAIR VALUE BERECHNUNG) ---
def calculate_advanced_fair_value(info):
    """Berechnet den gemittelten fairen Wert aus EPS und Free Cashflow."""
    try:
        current_price = info.get('currentPrice')
        eps = info.get('trailingEps')
        fcf = info.get('freeCashflow')
        shares = info.get('sharesOutstanding')
        growth_rate = info.get('earningsGrowth', 0.1) # Fallback 10% Wachstum
        
        if growth_rate is None: growth_rate = 0.1

        # Dynamischer Multiplikator (Basis 15 + Wachstumskomponente)
        # Eine Aktie mit 20% Wachstum bekommt ein höheres faires KGV als eine mit 5%.
        fair_multiplier = 15 + (growth_rate * 50) 
        fair_multiplier = max(12, min(fair_multiplier, 30)) # Begrenzung zwischen 12 und 30

        # 1. Fair Value Gewinn (EPS)
        fv_eps = eps * fair_multiplier if eps and eps > 0 else None
        
        # 2. Fair Value Free Cashflow (FCF)
        fcf_per_share = (fcf / shares) if fcf and shares else None
        fv_fcf = fcf_per_share * fair_multiplier if fcf_per_share and fcf_per_share > 0 else None
        
        # 3. Mittelwert bilden (Vereinigter Fair Value)
        valid_models = [v for v in [fv_eps, fv_fcf] if v is not None]
        
        if not valid_models:
            return current_price, 0 # Fallback
            
        final_fv = sum(valid_models) / len(valid_models)
        return round(final_fv, 2), round(fair_multiplier, 1)
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
        
        # Technik: RSI
        df['RSI'] = ta.rsi(df['Close'], length=14)
        rsi = df['RSI'].iloc[-1]
        
        # Technik: Korrektur-Statistik (Drawdown)
        high_52w = df['Close'].max()
        current_dd = ((current_price / high_52w) - 1) * 100
        
        rolling_max = df['Close'].cummax()
        drawdowns = (df['Close'] / rolling_max - 1)
        avg_correction = drawdowns[drawdowns < -0.05].mean() * 100
        
        # Fundamentaler Fair Value (Aktienfinder-Stil)
        fair_value, used_mult = calculate_advanced_fair_value(info)
        margin_of_safety = (1 - (current_price / fair_value)) * 100
        
        # Signal-Logik
        is_cheap = current_price < (fair_value * 1.05) # 5% Puffer um den FV
        is_oversold = rsi < 45
        is_correction = current_dd <= (avg_correction * 0.8) # 80% der typischen Korrektur erreicht
        
        status = "Warten"
        if margin_of_safety > 10 and is_oversold and is_correction:
            status = "KAUFEN"
        elif margin_of_safety > 0:
            status = "Fair bewertet"
        elif margin_of_safety < -15:
            status = "Überhitzt"

        return {
            "Ticker": symbol,
            "Kurs": round(current_price, 2),
            "Fair Value (Aktienfinder)": fair_value,
            "Margin %": round(margin_of_safety, 2),
            "RSI (14)": round(rsi, 2),
            "Korrektur %": round(current_dd, 2),
            "Ø Korr. %": round(avg_correction, 2),
            "Mult.": used_mult,
            "Status": status
        }
    except Exception:
        return None

# --- UI DESIGN (STREAMLIT) ---
st.title("🚀 Aktienfinder Pro: Fair Value & Cashflow-Check")

# Sidebar
st.sidebar.header("Meine Watchlist")
current_tickers = load_watchlist()
new_ticker = st.sidebar.text_input("Ticker Symbol (z.B. MSFT):").upper()

if st.sidebar.button("Hinzufügen"):
    if new_ticker and new_ticker not in current_tickers:
        current_tickers.append(new_ticker)
        save_watchlist(current_tickers)
        st.rerun()

remove_ticker = st.sidebar.selectbox("Ticker entfernen:", [""] + current_tickers)
if st.sidebar.button("Entfernen"):
    if remove_ticker in current_tickers:
        current_tickers.remove(remove_ticker)
        save_watchlist(current_tickers)
        st.rerun()

# Hauptanzeige
if current_tickers:
    with st.spinner('Berechne fundamentale und technische Daten...'):
        data_list = [get_analysis_data(s) for s in current_tickers]
        results = [d for d in data_list if d is not None]
        df_results = pd.DataFrame(results)

    # Farbliche Formatierung
    def style_status(row):
        color = ''
        if row['Status'] == "KAUFEN":
            color = 'background-color: #1e8449; color: white;' # Dunkelgrün
        elif row['Status'] == "Fair bewertet":
            color = 'background-color: #2e86c1; color: white;' # Blau
        elif row['Status'] == "Überhitzt":
            color = 'background-color: #b03a2e; color: white;' # Rot
        return [color] * len(row)

    st.subheader("Watchlist Analyse")
    st.dataframe(
        df_results.style.apply(style_status, axis=1)
        .format({"Margin %": "{:.1f}%", "Korrektur %": "{:.1f}%", "Ø Korr. %": "{:.1f}%"}),
        use_container_width=True
    )

    # Erklärungsbereich
    with st.expander("ℹ️ Analyse-Methodik"):
        st.markdown("""
        - **Fair Value (Aktienfinder):** Gemittelter Wert aus dem fairen KGV (Gewinn) und dem fairen KCV (Free Cashflow).
        - **Mult.:** Der angewendete Multiplikator. Er berechnet sich dynamisch aus dem Gewinnwachstum (höheres Wachstum = höherer Multiplikator).
        - **Margin %:** Sicherheitsmarge. Positiv bedeutet, der Kurs liegt unter dem fairen Wert.
        - **Kauf-Signal:** Erscheint, wenn die Aktie **unterbewertet** ist, der **RSI** niedrig steht und die **Korrektur** historisch groß genug ist.
        """)
        
else:
    st.info("Deine Watchlist ist leer. Nutze die Sidebar, um Aktien hinzuzufügen.")
