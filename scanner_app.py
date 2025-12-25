import streamlit as st
import pandas as pd
from finvizfinance.screener.overview import Overview

# --- SEITENKONFIGURATION ---
st.set_page_config(page_title="Pro Stock Screener", layout="wide")

st.title("📈 Stabiler Profi-Screener")
st.markdown("Die Regler sind auf die offiziellen Finviz-Schritte optimiert, um Fehler zu vermeiden.")

# --- SIDEBAR: STRATEGIE & PARAMETER ---
st.sidebar.header("1. Strategie wählen")
strategy = st.sidebar.selectbox("Basis-Strategie", 
    ["Wachstumsaktien ", 
     "Dividendenaktien ", 
     "Technisches Momentum "])

st.sidebar.divider()
st.sidebar.header("2. Feinjustierung")

# Wir definieren hier Listen mit Werten, die Finviz sicher akzeptiert
if strategy == "Wachstumsaktien ":
    # Finviz bietet: Over 5%, 10%, 15%, 20%, 25%, 30%
    eps_options = [5, 10, 15, 20, 25, 30]
    eps_growth = st.sidebar.select_slider("Min. EPS Wachstum 5J (%)", options=eps_options, value=20)
    
    # Finviz bietet: Under 10%, 20%, 30%, 40%, 50%...
    payout_options = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    payout = st.sidebar.select_slider("Max. Payout Ratio (%)", options=payout_options, value=50)
    
    # FCF Optionen
    fcf_options = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
    p_fcf = st.sidebar.select_slider("Max. Price/Free Cash Flow", options=fcf_options, value=20)
    
elif strategy == "Dividendenaktien ":
     # Finviz bietet: Over 5%, 10%, 15%, 20%, 25%, 30%
    eps_options = [5, 10, 15, 20, 25, 30]
    eps_growth = st.sidebar.select_slider("Min. EPS Wachstum 5J (%)", options=eps_options, value=5)
   
    # Finviz bietet: Over 1% bis 10%
    yield_options = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    div_yield = st.sidebar.select_slider("Min. Dividendenrendite (%)", options=yield_options, value=4)
    
    payout_options = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    payout = st.sidebar.select_slider("Max. Payout Ratio (%)", options=payout_options, value=70)

elif strategy == "Technisches Momentum ":
     # Finviz bietet: Over 5%, 10%, 15%, 20%, 25%, 30%
    eps_options = [5, 10, 15, 20, 25, 30]
    eps_growth = st.sidebar.select_slider("Min. EPS Wachstum 5J (%)", options=eps_options, value=15)
    
     # Finviz bietet: Under 10%, 20%, 30%, 40%, 50%...
    payout_options = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    payout = st.sidebar.select_slider("Max. Payout Ratio (%)", options=payout_options, value=60)
    
    st.sidebar.info("Momentum nutzt die fixen SMA-Filter aus deinen Unterlagen.")

sector = st.sidebar.selectbox("Sektor", ['Any', 'Basic Materials', 'Communication Services', 'Consumer Cyclical', 'Consumer Defensive', 'Energy', 'Financial', 'Healthcare', 'Industrials', 'Technology', 'Utilities'])

# --- LOGIK: FILTER-BAU ---
def get_filters():
    filters = {"Price": "Over $1", "Average Volume": "Over 200K"}
    if sector != 'Any':
        filters['Sector'] = sector

    if strategy == "Wachstumsaktien ":
        filters.update({
            "Market Cap.": "+Large (over $10bln)",
            "EPS growthpast 5 years": f"Over {eps_growth}%",
            "Debt/Equity": "Under 0.5",
            "Payout Ratio": f"Under {payout}%",
            "Price/Free Cash Flow": f"Over {p_fcf}"
        })
    elif strategy == "Dividendenaktien ":
        filters.update({
            "Market Cap.": "+Mid (over $2bln)",
            "EPS growthpast 5 years": f"Over {eps_growth}%",
            "Dividend Yield": f"Over {div_yield}%",
            "Debt/Equity": "Under 0.5",
            "Payout Ratio": f"Under {payout}%"
        })
    elif strategy == "Technisches Momentum ":
        filters.update({
            "Index": "S&P 500",
            "Market Cap.": "+Mid (over $2bln)",
            "Debt/Equity": "Under 0.5",
            "EPS growthpast 5 years": f"Over {eps_growth}%",
            "Payout Ratio": f"Under {payout}%",
            "200-Day Simple Moving Average": "Price above SMA200",
            "50-Day Simple Moving Average": "Price 10% above SMA50",
            "20-Day Simple Moving Average": "Price above SMA20",
            "Option/Short": "Optionable and shortable"
        })
    return filters

# --- AUSFÜHRUNG ---
if st.sidebar.button("Screener starten"):
    active_filters = get_filters()
    
    with st.spinner('Daten werden abgerufen...'):
        try:
            foverview = Overview()
            foverview.set_filter(filters_dict=active_filters)
            df = foverview.screener_view()
            
            if df is not None and not df.empty:
                st.subheader(f"Ergebnisse ({len(df)})")
                st.dataframe(df, use_container_width=True)
                
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("Liste als CSV speichern", csv, "screener_export.csv", "text/csv")
            else:
                st.warning("Keine Treffer. Die Filterkombination ist zu streng.")
        except Exception as e:
            st.error(f"Fehler: {e}")
            st.info("Dieser Fehler tritt auf, wenn ein gewählter Wert nicht exakt so bei Finviz existiert.")
else:
    st.info("Wähle eine Strategie und klicke auf 'Screener starten'.")
