import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from io import BytesIO

# --- CONFIG & STYLE ---
st.set_page_config(page_title="Quick Checker", layout="wide")

st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 1.6rem !important; font-weight: bold; }
    .stAlert { border-radius: 12px; }
    .stTabs [data-baseweb="tab-list"] { gap: 20px; }
    .stTabs [data-baseweb="tab"] { 
        height: 50px; white-space: pre-wrap; background-color: #1e1e1e; 
        border-radius: 5px; color: white; padding: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- CACHING FUNKTION (Repariert) ---
@st.cache_data(ttl=3600)
def get_clean_stock_data(query):
    """Extrahiert nur serialisierbare Daten, um Caching-Fehler zu vermeiden."""
    try:
        s = yf.Ticker(query)
        info = s.info
        
        # Falls Ticker nicht direkt gefunden wird, Name-Suche simulieren
        if 'currentPrice' not in info:
            return None
            
        hist = s.history(period="1y")
        hist_all = s.history(period="max")
        
        # Nur einfache Datentypen zurückgeben (kein yf.Ticker Objekt!)
        return {
            "info": info,
            "hist": hist,
            "hist_all": hist_all,
            "ticker": query
        }
    except:
        return None

# --- ANALYSE LOGIK ---
def calculate_metrics(data):
    info = data["info"]
    hist = data["hist"]
    
    # RSI
    delta = hist['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / (loss + 1e-9)
    rsi = 100 - (100 / (1 + rs))
    
    # AAQS (10 Punkte)
    score = 0
    if info.get('revenueGrowth', 0) > 0.05: score += 2
    if info.get('returnOnEquity', 0) > 0.15: score += 2
    if info.get('debtToEquity', 100) < 60: score += 2
    if info.get('profitMargins', 0) > 0.10: score += 2
    if info.get('forwardPE', 100) < 25: score += 2
    
    # Fair Value & MoS
    fair_val = info.get('forwardEps', 0) * min(info.get('forwardPE', 20), 25)
    curr_price = info.get('currentPrice')
    mos = ((fair_val - curr_price) / fair_val * 100) if fair_val > 0 else -100
    
    return score, rsi.iloc[-1], fair_val, mos

# --- MAIN APP ---
st.title("🛡️ Investment Intelligence Pro")

tab1, tab2, tab3 = st.tabs(["🔍 Einzel-Check", "⚔️ Aktien-Duell", "🕵️ Sektor-Screener"])

# --- TAB 1: EINZEL-CHECK ---
with tab1:
    query = st.text_input("Name oder Ticker:", placeholder="z.B. Apple oder AAPL", key="s1").upper()
    if query:
        data = get_clean_stock_data(query)
        if data:
            score, rsi_val, fair_val, mos = calculate_metrics(data)
            info = data["info"]
            curr_price = info.get('currentPrice')
            
            st.header(info.get('shortName', query))
            c1, c2, c3 = st.columns(3)
            c1.metric("Kurs", f"{curr_price} {info.get('currency')}")
            c2.metric("RSI (14T)", round(rsi_val, 1), "Überkauft" if rsi_val > 70 else "Günstig" if rsi_val < 35 else "Neutral")
            c3.metric("Qualität (AAQS)", f"{score}/10")
            
            # Disziplin-Ampel
            if score >= 8 and mos > 0 and rsi_val < 60:
                st.success("### ✅ SIGNAL: KAUFZONE")
            elif score >= 8:
                st.info("### ⏳ SIGNAL: QUALITÄT WARTELISTE")
            else:
                st.error("### ❌ SIGNAL: KEIN INVESTMENT")
            
            st.write(f"**Fair Value:** {round(fair_val, 2)} | **Sicherheitsmarge:** {round(mos, 1)}%")
            st.line_chart(data["hist"]['Close'])
        else:
            st.error("Aktie nicht gefunden. Nutze Ticker wie 'AAPL' oder 'SAP.DE'.")

# --- TAB 2: DUELL ---
with tab2:
    col_a, col_b = st.columns(2)
    t1 = col_a.text_input("Aktie A", "AAPL", key="t1").upper()
    t2 = col_b.text_input("Aktie B", "MSFT", key="t2").upper()
    
    if st.button("🚀 Duell starten"):
        d1 = get_clean_stock_data(t1)
        d2 = get_clean_stock_data(t2)
        if d1 and d2:
            s1, r1, f1, m1 = calculate_metrics(d1)
            s2, r2, f2, m2 = calculate_metrics(d2)
            
            res = pd.DataFrame({
                "Merkmal": ["Qualität", "RSI", "Fair Value", "MoS %"],
                d1['info']['shortName']: [f"{s1}/10", round(r1,1), round(f1,2), f"{round(m1,1)}%"],
                d2['info']['shortName']: [f"{s2}/10", round(r2,1), round(f2,2), f"{round(m2,1)}%"]
            })
            st.table(res)
            
            # Normalisierter Chart
            c_data = pd.DataFrame({
                d1['info']['shortName']: d1['hist']['Close'] / d1['hist']['Close'].iloc[0] * 100,
                d2['info']['shortName']: d2['hist']['Close'] / d2['hist']['Close'].iloc[0] * 100
            })
            st.line_chart(c_data)

# --- TAB 3: SCREENER ---
with tab3:
    sect = st.selectbox("Sektor wählen:", ["Technologie", "Automobil", "Finanzen", "Konsum"])
    presets = {
        "Technologie": ["AAPL", "MSFT", "NVDA", "ASML", "SAP.DE"],
        "Automobil": ["TSLA", "MBG.DE", "BMW.DE", "VOW3.DE", "F"],
        "Finanzen": ["ALV.DE", "JPM", "GS", "DBK.DE"],
        "Konsum": ["KO", "PEP", "PG", "LVMH.PA"]
    }
    
    if st.button(f"Scan {sect} starten"):
        results = []
        for t in presets[sect]:
            d = get_clean_stock_data(t)
            if d:
                sc, rs, fv, ms = calculate_metrics(d)
                results.append({
                    "Ticker": t, "Name": d['info']['shortName'], 
                    "AAQS": sc, "RSI": round(rs, 1), "MoS %": round(ms, 1)
                })
        
        df_scan = pd.DataFrame(results).sort_values(by="AAQS", ascending=False)
        st.dataframe(df_scan, use_container_width=True)
        
        # Excel Export
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_scan.to_excel(writer, index=False)
        st.download_button("📥 Excel Export", output.getvalue(), "Screener.xlsx")
