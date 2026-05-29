import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
from google import genai
from google.genai import types

# הגדרת תצורת דף רחב למערכת
st.set_page_config(page_title="Macro AI Screener", layout="wide")
st.title("🎯 Macro AI Alpha Core - סורק מניות חכם")

# --- פונקציות ליבה מקומיות חסינות קריסה ---
def fetch_live_market_dashboard():
    indices = {"S&P 500": "^GSPC", "Nasdaq 100": "^IXIC", "תל אביב 35": "^TA35.TA"}
    dashboard = {}
    for name, ticker in indices.items():
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="2d")
            if len(hist) >= 2:
                current_price = hist['Close'].iloc[-1]
                pct_change = ((current_price - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
                dashboard[name] = (current_price, pct_change)
            elif not hist.empty:
                dashboard[name] = (hist['Close'].iloc[-1], 0.0)
            else:
                dashboard[name] = (None, None)
        except:
            dashboard[name] = (None, None)
    return dashboard

def fetch_fx_rates():
    fx_tickers = {"USD/ILS (דולר)": "ILS=X", "EUR/ILS (יורו)": "EURILS=X"}
    fx_rates = {}
    for name, ticker in fx_tickers.items():
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="2d")
            if not hist.empty:
                current_rate = hist['Close'].iloc[-1]
                if current_rate < 1.0: current_rate = 1 / current_rate
                change = current_rate - (hist['Close'].iloc[-2] if len(hist) >= 2 else current_rate)
                fx_rates[name] = (current_rate, change)
            else:
                fx_rates[name] = (None, None)
        except:
            fx_rates[name] = (None, None)
    return fx_rates
def scan_sector_fundamentals(tickers):
    """פונקציה חסינה למשיכת נתוני שוק וחישוב תשואות 6M ו-YTD"""
    scan_results = []
    current_year = datetime.now().year
    start_of_year = f"{current_year}-01-01"
    
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            
            # משיכת היסטוריה של שנה לצורך תשואה חצי שנתית וממוצע 200
            hist = stock.history(period="1y")
            if hist.empty: continue
            
            # משיכת נתונים מתחילת השנה הנוכחית לצורך חישוב YTD
            hist_ytd = stock.history(start=start_of_year)
            
            current_price = hist['Close'].iloc[-1]
            
            # 1. חישוב תשואה בחצי שנה האחרונה (6 חודשים)
            price_6m_ago = hist['Close'].iloc[-126] if len(hist) >= 126 else hist['Close'].iloc[0]
            return_6m = ((current_price - price_6m_ago) / price_6m_ago) * 100
            
            # 2. חישוב תשואה מתחילת השנה (YTD)
            if not hist_ytd.empty:
                price_start_year = hist_ytd['Close'].iloc[0]
                return_ytd = ((current_price - price_start_year) / price_start_year) * 100
            else:
                return_ytd = 0.0
            
            # 3. חישוב מרחק מממוצע נע 200 ימים
            ma200 = hist['Close'].rolling(window=200).mean().iloc[-1] if len(hist) >= 200 else hist['Close'].mean()
            dist_ma200 = ((current_price - ma200) / ma200) * 100
            
            # 4. נפח מסחר ממוצע לאחרונה
            avg_volume = hist['Volume'].tail(10).mean()
            
            scan_results.append({
                "מנייה": ticker,
                "מחיר נוכחי ($)": round(current_price, 2),
                "תשואה 6 חודשים": f"{return_6m:.1f}%",
                "תשואה מתחילת שנה (YTD)": f"{return_ytd:.1f}%",
                "מיקום מעל ממוצע 200": f"{dist_ma200:.1f}%",
                "מחזור מסחר ממוצע (10 ימים)": f"{avg_volume:,.0f}"
            })
        except:
            continue
    return pd.DataFrame(scan_results)

# --- הצגת לוח מחוונים עליון בזמן אמת ---
live_indices = fetch_live_market_dashboard()
live_fx = fetch_fx_rates()

all_metrics = {**live_indices, **live_fx}
idx_cols = st.columns(len(all_metrics))

for i, (name, data) in enumerate(all_metrics.items()):
    if data and data is not None:
        val, change = data
        if "ILS" in name:
            idx_cols[i].metric(label=name, value=f"{val:.3f} ש\"ח", delta=f"{change:.4f}")
        else:
            idx_cols[i].metric(label=name, value=f"{val:,.1f}", delta=f"{change:.2f}%")
    else:
        idx_cols[i].metric(label=name, value="N/A")

st.write("---")

# הגדרת סקטורים
SECTOR_MAP = {
    "Technology & AI Semiconductors": ["NVDA", "TSM", "AMD", "ASML"],
    "Energy & Global Infrastructure": ["XOM", "CVX", "SHEL", "NEXTERA"],
    "Commodities & Global Shipping": ["VALE", "CAT", "ZIM", "BHP"],
    "Biotech & Healthcare": ["LLY", "NVO", "PFE", "MRK"]
}

if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
else:
    api_key = st.sidebar.text_input("הזן מפתח API של Gemini:", type="password")
risk_profile = st.sidebar.selectbox("פרופיל סיכון יעד:", ["Conservative", "Moderate", "Aggressive"])

selected_sector = st.selectbox("בחר ענף שבו תרצה לאתר השקעות ופוטנציאל:", list(SECTOR_MAP.keys()))
if st.button("🔍 הפעל סורק ענפי מהיר", type="primary"):
    if not api_key:
        st.warning("אנא הזן מפתח API בתפריט הצד.")
    else:
        with st.spinner("מריץ סורק נתונים פונדמנטלי וטכני מקומי..."):
            tickers = SECTOR_MAP[selected_sector]
            df_sector = scan_sector_fundamentals(tickers)
            
            if df_sector.empty:
                st.error("שגיאה זמנית במשיכת נתוני המניות מ-Yahoo Finance. אנא נסה שוב בעוד מספר רגעים.")
            else:
                st.subheader(f"📊 ממצאי סינון וסריקה עבור ענף: {selected_sector}")
                st.dataframe(df_sector, use_container_width=True, hide_index=True)
                
                # 🎯 הוספת הערת גילוי נאות קבועה ובולטת (Disclaimer) לבקשת המשתמש
                st.caption("⚠️ **הערה חשובה:** התשואה המוצגת במערכת הינה מוערכת בלבד ומתבססת על נתוני נכסי הבסיס ההיסטוריים, וזאת בתנאי שלא בוצעו שינויי מסלולים או התאמות הקצאה מצד המשתמש במהלך תקופת החישוב.")
                
                st.write("")
                st.subheader("💡 אבחנת מנוע מהירה (איתור פוטנציאל)")
                
                prompt_quick = f"""
                You are a senior hedge fund screener. Look at this processed data table for the sector {selected_sector}:
                {df_sector.to_string()}
                Based strictly on these momentum metrics (6-month return, YTD return, position above MA200, average volume) and risk profile '{risk_profile}', identify WHICH stock has the highest investment potential right now.
                Provide a short, 3-sentence summary in Hebrew explaining why, and state a clear top pick.
                Respond strictly in Hebrew.
                """
                try:
                    client = genai.Client(api_key=api_key)
                    response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt_quick)
                    st.info(response.text)
                    st.session_state.active_tickers = tickers
                except Exception as e:
                    st.error(f"שגיאה בהפקת האבחנה המהירה: {str(e)}")

if "active_tickers" in st.session_state:
    st.write("---")
    st.markdown("### 🚀 העמקה ומודיעין עמוק (לפי דרישה בלבד)")
    chosen_ticker = st.selectbox("בחר מנייה ספציפית מהסורק כדי להפיק עליה דוח מלא מהאינטרנט:", st.session_state.active_tickers)
    
    if st.button("🌐 הפק דוח מקיף ומלא (Bloomberg & TradingView)", type="secondary"):
        with st.spinner(f"סוכן הרשת יוצא כעת ל-Bloomberg ו-TradingView לחקור את {chosen_ticker}..."):
            prompt_deep = f"""
            Generate a full Alpha Convergence Report for the stock {chosen_ticker} (Risk: {risk_profile}).
            Use Google Search tool to prioritize insights from site:bloomberg.com and site:tradingview.com.
            Cover: Executive Macro summary, Technical consensus from TradingView, and Geopolitical supply chain indicators from Bloomberg.
            Provide a final Alpha Convergence Score (0-100).
            Respond strictly and entirely in Hebrew.
            """
            try:
                client = genai.Client(api_key=api_key)
                deep_response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt_deep,
                    config=types.GenerateContentConfig(
                        temperature=0.3,
                        tools=[types.Tool(google_search=types.GoogleSearch())]
                    )
                )
                st.write("---")
                st.markdown(deep_response.text)
            except Exception as e:
                st.error(f"שגיאה בהפקת הדוח המלא: {str(e)}")
