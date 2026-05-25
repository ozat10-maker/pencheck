import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime
from google import genai
from google.genai import types

# =====================================================================
# 🔑 הגדרת מפתח API קבוע מראש
# =====================================================================
DEFAULT_GEMINI_KEY = "" 

# הגדרת תצורת דף רחבה
st.set_page_config(page_title="מערכת AI לניטור פנסיה בזמן אמת", page_icon="🧓", layout="wide")

# =====================================================================
# 🔄 אתחול מנגנון st.session_state לניהול השלבים והנתונים
# =====================================================================
if "pension_page" not in st.session_state:
    st.session_state.pension_page = "page1"  # דף ברירת המחדל באתחול
if "user_info" not in st.session_state:
    st.session_state.user_info = {}
if "mix_data" not in st.session_state:
    st.session_state.mix_data = {}

# פונקציית עזר לניווט מנוהל State
def navigate_to(page_name):
    st.session_state.pension_page = page_name
    st.rerun()

# --- תפריט צד ומנגנון טעינת מפתח API אוטומטי ---
st.sidebar.header("הגדרות מערכת ו-AI")

if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
    st.sidebar.success("מפתח API נטען אוטומטית מ-Secrets ✔️")
elif DEFAULT_GEMINI_KEY and DEFAULT_GEMINI_KEY.strip() != "":
    api_key = DEFAULT_GEMINI_KEY
    st.sidebar.success("מפתח API קבוע נטען בהצלחה מהקוד ✔️")
else:
    api_key = st.sidebar.text_input("הזן מפתח API של Gemini:", type="password")
    if not api_key:
        st.sidebar.warning("⚠️ יש להזין מפתח API כדי לקבל את דוח ה-AI בסיום.")

# --- פונקציה למשיכת תשואות מדדים מתחילת החודש ---
def get_benchmark_returns():
    # התיקון הסינטקטי באנגלית נקייה למניעת קריסות היפוך שפה בשרת:
    benchmarks = {
        "S&P 500": "^SPX",
        "TA 125": "^TA125.TA",
        "Nasdaq 100": "^NDX",
        "Bonds": "AGG",
        "Cash": "BIL"
    }
    
    today = datetime.today()
    start_of_month = datetime(today.year, today.month, 1).strftime('%Y-%m-%d')
    returns = {}
    
    for name, ticker in benchmarks.items():
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(start=start_of_month)
            if not hist.empty and len(hist) >= 2:
                initial_price = float(hist['Close'].iloc[0])
                current_price = float(hist['Close'].iloc[-1])
                month_return = ((current_price - initial_price) / initial_price) * 100
                returns[name] = month_return
            else:
                returns[name] = 0.0
        except:
            returns[name] = 0.0
            
    return returns

# 🗺️ תצוגת סרגל התקדמות ויזואלי בראש האפליקציה לפי ה-State הנוכחי
if st.session_state.pension_page == "page1":
    st.progress(33, text="שלב 1 מתוך 3: פרטי החוסך ודמי ניהול")
elif st.session_state.pension_page == "page2":
    st.progress(66, text="שלב 2 מתוך 3: הגדרת תמהיל נכסי הקופה")
elif st.session_state.pension_page == "analysis":
    st.progress(100, text="שלב 3 מתוך 3: מנוע ניתוח ודוח AI")

st.write("---")
# =====================================================================
# 📋 דף 1: פרטים אישיים, נתוני הקופה ודמי ניהול
# =====================================================================
if st.session_state.pension_page == "page1":
    st.title("🧓 שלב 1: הגדרת נתוני החוסך ודמי הניהול")
    st.write("אנא הזן את פרטי הקופה הנוכחית שלך ודמי הניהול המדויקים:")
    
    saved_info = st.session_state.user_info
    
    col1, col2 = st.columns(2)
    with col1:
        company_list = ["הראל פנסיה וגמל", "מנורה מבטחים", "אלטשולר שחם", "הפניקס", "מיטב גמל ופנסיה", "מגדל מקפת", "מור"]
        default_company_idx = company_list.index(saved_info["company"]) if "company" in saved_info else 0
        company_name = st.selectbox("שם החברה המנהלת:", company_list, index=default_company_idx)
        
        fund_name = st.text_input("שם הקופה / מסלול השקעה:", saved_info.get("fund", "מסלול מנייתי מוגבר"))
        user_age = st.number_input("גיל המשתמש:", min_value=18, max_value=100, value=saved_info.get("age", 35))
    
    with col2:
        total_balance = st.number_input("יתרה צבורה נוכחית בש\"ח:", min_value=0, value=saved_info.get("balance", 150000), step=10000)
        monthly_deposit = st.number_input("הפקדה חודשית שוטפת בש\"ח:", min_value=0, value=saved_info.get("monthly_deposit", 2500), step=100)
        
        st.markdown("**💸 דמי ניהול נוכחיים:**")
        sub_c1, sub_c2 = st.columns(2)
        fee_from_deposit = sub_c1.number_input("דמי ניהול מהפקדה (%):", min_value=0.0, max_value=6.0, value=saved_info.get("fee_deposit", 1.5), step=0.1)
        fee_from_balance = sub_c2.number_input("דמי ניהול מצבירה שנתית (%):", min_value=0.0, max_value=1.1, value=saved_info.get("fee_balance", 0.22), step=0.01)
        
    st.write("---")
    if st.button("המשך להגדרת תמהיל הקופה ➡️", type="primary"):
        st.session_state.user_info = {
            "company": company_name,
            "fund": fund_name,
            "age": user_age,
            "balance": total_balance,
            "monthly_deposit": monthly_deposit,
            "fee_deposit": fee_from_deposit,
            "fee_balance": fee_from_balance
        }
        navigate_to("page2")
# =====================================================================
# 📊 דף 2: הגדרת תמהיל הנכסים בקופה
# =====================================================================
elif st.session_state.pension_page == "page2":
    if not st.session_state.user_info:
        navigate_to("page1")
        
    st.title("📊 שלב 2: הגדרת תמהיל הנכסים בקופה")
    st.write(f"הקופה: **{st.session_state.user_info['fund']}** בחברת **{st.session_state.user_info['company']}**")
    st.info("הזן את אחוזי החשיפה של המסלול שלך. סך כל האחוזים חייב להסתכם ל-100%.")
    
    saved_mix = st.session_state.mix_data
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("חלוקת אפיקי השקעה")
        p_sp500 = st.slider("מניות חוייל S&P 500 - %", 0, 100, saved_mix.get("S&P 500", 50))
        p_tlv = st.slider("מניות ישראל תא 125 - %", 0, 100, saved_mix.get("TA 125", 20))
        p_nasdaq = st.slider("טכנולוגיה Nasdaq 100 - %", 0, 100, saved_mix.get("Nasdaq 100", 10))
        p_bonds = st.slider("איגרות חוב Bonds - %", 0, 100, saved_mix.get("Bonds", 15))
        p_cash = st.slider("מזומן ואחר Cash - %", 0, 100, saved_mix.get("Cash", 5))
        
        total_pct = p_sp500 + p_tlv + p_nasdaq + p_bonds + p_cash
        
    with col2:
        st.subheader("פילוח ויזואלי של התיק המוצע")
        mix_df = pd.DataFrame({
            "אפיק השקעה": ["S&P 500", "TA 125", "Nasdaq 100", "Bonds", "Cash"],
            "אחוז": [p_sp500, p_tlv, p_nasdaq, p_bonds, p_cash]
        })
        fig = px.pie(mix_df, values="אחוז", names="אפיק השקעה", hole=0.4, title="תמהיל נכסי הפנסיה")
        st.plotly_chart(fig, use_container_width=True)

    if total_pct == 100:
        st.success(f"תמהיל תקין! הסכום שווה ל-{total_pct}%")
    else:
        st.error(f"שים לב: סך האחוזים הנוכחי הוא {total_pct}%. עליך להגיע ל-100% בדיוק כדי להמשיך.")

    st.write("---")
    c_back, c_next = st.columns(2)
    
    if c_back.button("↩️ חזור לפרטים אישיים"):
        navigate_to("page1")
        
    if c_next.button("בצע ניתוח ביצועים ודוח AI! 🚀", type="primary", disabled=(total_pct != 100)):
        st.session_state.mix_data = {
            "S&P 500": p_sp500,
            "TA 125": p_tlv,
            "Nasdaq 100": p_nasdaq,
            "Bonds": p_bonds,
            "Cash": p_cash
        }
        navigate_to("analysis")
# =====================================================================
# 🔮 דף 3: מנוע ניתוח ביצועי פנסיה ודוח AI
# =====================================================================
elif st.session_state.pension_page == "analysis":
    if not st.session_state.mix_data or not st.session_state.user_info:
        navigate_to("page1")
        
    st.title("🔮 מנוע ניתוח ביצועי פנסיה ודוח AI")
    current_month_name = datetime.today().strftime('%B %Y')
    st.subheader(f"אומדן ביצועים ועלויות עבור חודש: {current_month_name}")
    
    if st.button("↩️ חזור לעריכת תמהיל התיק"):
        navigate_to("page2")
        
    st.write("---")
    
    with st.spinner("שולף נתוני שוק ומחשב עלויות דמי ניהול..."):
        benchmark_returns = get_benchmark_returns()
        
        total_gross_return = 0.0
        rows = []
        for asset, weight in st.session_state.mix_data.items():
            asset_return = benchmark_returns.get(asset, 0.0)
            weighted_contribution = asset_return * (weight / 100)
            total_gross_return += weighted_contribution
            
            rows.append({
                "אפיק השקעה": asset,
                "משקל בקופה": f"{weight}%",
                "תשואת האפיק החודש": f"{asset_return:+.2f}%",
                "תרומה לתשואת הקופה": f"{weighted_contribution:+.2f}%"
            })
            
        u = st.session_state.user_info
        monthly_deposit_fee_nis = u["monthly_deposit"] * (u["fee_deposit"] / 100)
        monthly_balance_fee_nis = u["balance"] * ((u["fee_balance"] / 100) / 12)
        total_monthly_fees_nis = monthly_deposit_fee_nis + monthly_balance_fee_nis
        
        fee_impact_percentage = (total_monthly_fees_nis / u["balance"]) * 100 if u["balance"] > 0 else 0.0
        total_net_return = total_gross_return - fee_impact_percentage
        
        money_change_net = u["balance"] * (total_net_return / 100)
        new_balance_net = u["balance"] + money_change_net
        
        st.write("### 📈 סיכום ביצועים ועלויות לחודש הנוכחי (נטו)")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("תשואה מוערכת (נטו)", f"{total_net_return:+.2f}%", f"ברוטו: {total_gross_return:+.2f}%")
        m2.metric("סה\"כ דמי ניהול החודש", f"{total_monthly_fees_nis:,.2f} ₪", f"מצבירה: {monthly_balance_fee_nis:.1f}₪ | מהפקדה: {monthly_deposit_fee_nis:.1f}₪", delta_color="inverse")
        m3.metric("שינוי כספי מוערך (נטו)", f"{money_change_net:+,.2f} ₪")
        m4.metric("שווי תיק מעודכן", f"{new_balance_net:,.2f} ₪")
        
        st.write("### 📋 פירוט תרומת האפיקים לתשואה המצטברת")
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
        
        st.write("---")
        st.subheader("🤖 דוח ניתוח והמלצות אסטרטגיות מה-AI")
        
        if not api_key:
            st.info("💡 הזן את מפתח ה-API של Gemini בתפריט הצד או בקוד על מנת להפיק דוח המלצות מקצועי ומותאם אישית.")
        else:
            with st.spinner("מנוע ה-AI מנתח את נתוני הפנסיה ודמי הניהול שלך..."):
                total_stocks = st.session_state.mix_data["S&P 500"] + st.session_state.mix_data["TA 125"] + st.session_state.mix_data["Nasdaq 100"]
                
                user_context = (
                    f"[נתוני החוסך והקופה]\n"
                    f"חברה מנהלת: {u['company']}\nמסלול: {u['fund']}\nגיל: {u['age']}\n"
                    f"צבירה נוכחית: {u['balance']:,} ₪\nהפקדה חודשית: {u['monthly_deposit']:,} ₪\n\n"
                    f"[נתוני דמי ניהול]\n"
                    f"דמי ניהול מהפקדה: {u['fee_deposit']:.2f}%\nדמי ניהול מצבירה שנתית: {u['fee_balance']:.2f}%\n"
                    f"עלות חודשית בשקלים: {total_monthly_fees_nis:.2f} ₪\n\n"
                    f"[נתוני שוק ותשואות החודש]\n"
                    f"חשיפה מנייתית כוללת בתיק: {total_stocks}%\n"
                    f"תשואת התיק המשוערת ברוטו החודש: {total_gross_return:+.2f}%\n"
                    f"תשואת התיק נטו (לאחר ניכוי דמי ניהול): {total_net_return:+.2f}%\n"
                    f"פירוט ביצועי מדדים החודש: {benchmark_returns}\n"
                )
                
                system_instruction = (
                    "אתה מומחה פנסיוני, אקטואר ומנהל סיכונים בכיר בשוק ההון הישראלי. "
                    "נתח את הנתונים שסופקו לך והפק דוח מקצועי, חד ומעמיק בעברית בלבד. "
                    "הדוח חייב לכלול את הסעיפים הבאים:\n"
                    "1. ניתוח דמי ניהול: קבע האם דמי הניהול של המשתמש יקרים, ממוצעים או זולים ביחס לממוצע בשוק הפנסיה הישראלי, ומה הנזק המצטבר שלהם.\n"
                    "2. תאימות גיל ומסלול: האם אחוז המניות בקופה (חשיפת הסיכון) תואם את גיל החוסך לפי המודל הצ'יליאני (תלוי גיל) הנהוג בארץ?\n"
                    "3. השפעת ביצועי השוק החודש: הסבר קצר מה הניע את התשואה החודש.\n"
                    "4. שורה תחתונה והמלצות לפעולה: המלצות אופרטיביות (כמו מיקוח על דמי הניהול, בחינת מעבר מסלול, או שינוי פיזור המדדים).\n"
                    "שמור על טון כתיבה מקצועי, אובייקטיבי, ברור ונגיש לחוסך הציבורי."
                )
                
                try:
                    client = genai.Client(api_key=api_key)
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=user_context,
                        config=types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.2)
                    )
                    st.markdown(response.text)
                except Exception as e:
                    st.error(f"שגיאה בהפקת הדוח מה-AI: {str(e)}")
