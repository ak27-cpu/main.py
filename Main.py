import streamlit as st

# 1. Zentrale Konfiguration (Nur hier erlaubt!)
st.set_page_config(page_title="Mein Investment Dashboard", layout="wide")

# 2. Seiten definieren (Dateiname muss exakt stimmen)
page_1 = st.Page("watchlist_app.py", title="Aktien Watchlist", icon="⭐")
page_2 = st.Page("portfolio_app.py", title="Mein Portfolio", icon="💼")
page_3 = st.Page("scanner_app.py", title="Markt Scanner", icon="🔍")

# 3. Navigation erstellen
pg = st.navigation([page_1, page_2, page_3])

# 4. App ausführen
pg.run()
