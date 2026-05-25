import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from google import genai
from google.genai import types

# =====================================================================
# 🔑 הגדרת מפתח API קבוע מראש
# =====================================================================
DEFAULT_GEMINI_KEY = "" 

st.set_page_config(page_title="מערכת AI לניטור פנסיה בזמן אמת", page_icon="🧓", layout="wide")

if "pension_page" not in st.session_state:
    st.session_state.pension_page = "page1"
if "user_info" not in st.session_state:
    st.session_state.user_info = {}
if "mix_data" not in st.session_state:
    st.session_state.mix_data = {}

def navigate_to(page_name):
    st.session_state.pension_page = page_name
    st.rerun()

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
COMPANY_TRACKS_REGISTRY = {
    "הראל פנסיה וגמל": {
        "מסלול מחקה S&P 500": {"S&P 500": 100, "TA 125": 0, "Nasdaq 100": 0, "Bonds": 0, "Cash": 0},
        "מסלול מנייתי כללי": {"S&P 500": 45, "TA 125": 25, "Nasdaq 100": 20, "Bonds": 5, "Cash": 5},
        "מסלול כללי / מאוזן": {"S&P 500": 20, "TA 125": 15, "Nasdaq 100": 10, "Bonds": 40, "Cash": 15},
        "מסלול אג\"ח סולידי": {"S&P 500": 0, "TA 125": 0, "Nasdaq 100": 0, "Bonds": 85, "Cash": 15}
    },
    "אלטשולר שחם": {
        "מסלול מנייתי חוץ לארץ": {"S&P 500": 60, "TA 125": 10, "Nasdaq 100": 20, "Bonds": 5, "Cash": 5},
        "מסלול מחקה מדדים": {"S&P 500": 50, "TA 125": 20, "Nasdaq 100": 30, "Bonds": 0, "Cash": 0},
        "מסלול כללי": {"S&P 500": 25, "TA 125": 15, "Nasdaq 100": 15, "Bonds": 35, "Cash": 10},
        "מסלול שקלי קצר": {"S&P 500": 0, "TA 125": 0, "Nasdaq 100": 0, "Bonds": 20, "Cash": 80}
    },
    "מנורה מבטחים": {
        "מנורה מנייתי": {"S&P 500": 40, "TA 125": 30, "Nasdaq 100": 15, "Bonds": 10, "Cash": 5},
        "מנורה מחקה S&P 500": {"S&P 500": 100, "TA 125": 0, "Nasdaq 100": 0, "Bonds": 0, "Cash": 0},
        "מנורה כללי": {"S&P 500": 20, "TA 125": 20, "Nasdaq 100": 10, "Bonds": 40, "Cash": 10}
    },
    "הפניקס": {
        "הפניקס מנייתי": {"S&P 500": 45, "TA 125": 25, "Nasdaq 100": 15, "Bonds": 10, "Cash": 5},
        "הפניקס מחקה S&P 500": {"S&P 500": 100, "TA 125": 0, "Nasdaq 100": 0, "Bonds": 0, "Cash": 0},
        "הפניקס מסלול לבני 50 ומטה": {"S&P 500": 30, "TA 125": 20, "Nasdaq 100": 15, "Bonds": 25, "Cash": 10}
    },
    "מיטב גמל ופנסיה": {
        "מיטב מנייתי": {"S&P 500": 50, "TA 125": 20, "Nasdaq 100": 20, "Bonds": 5, "Cash": 5},
        "מיטב מחקה S&P 500": {"S&P 500": 100, "TA 125": 0, "Nasdaq 100": 0, "Bonds": 0, "Cash": 0},
        "מיטב כללי": {"S&P 500": 25, "TA 125": 15, "Nasdaq 100": 10, "Bonds": 40, "Cash": 10}
    }
}

BENCHMARKS = {"S&P 500": "^SPX", "TA 125": "^TA125.TA", "Nasdaq 100": "^NDX", "Bonds": "AGG", "Cash": "BIL"}

def get_benchmark_returns():
    start_of_month = datetime(datetime.today().year, datetime.today().month, 1).strftime('%Y-%m-%d')
    returns = {}
    for name, ticker in BENCHMARKS.items():
        try:
            hist = yf.Ticker(ticker).history(start=start_of_month)
            if not hist.empty and len(hist) >= 2:
                returns[name] = ((float(hist['Close'].iloc[-1]) - float(hist['Close'].iloc)) / float(hist['Close'].iloc)) * 100
            else: returns[name] = 0.0
        except: returns[name] = 0.0
    return returns

# חישוב ביצועי חודשים קודמים
def get_historical_months_returns():
    data_list = []
    today = datetime.today()
    for i in range(1, 4): # 3 חודשים אחרונים
        first_of_past = datetime(today.year, today.month, 1) - timedelta(days=i*30)
        start_date = datetime(first_of_past.year, first_of_past.month, 1)
        end_date = datetime(first_of_past.year, first_of_past.month, 28)
        month_label = start_date.strftime('%m/%Y')
        
        month_data = {"חודש": month_label}
        for name, ticker in BENCHMARKS.items():
            try:
                hist = yf.Ticker(ticker).history(start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))
                if not hist.empty and len(hist) >= 2:
                    month_data[name] = f"{((hist['Close'].iloc[-1] - hist['Close'].iloc) / hist['Close'].iloc) * 100:+.2f}%"
                else: month_data[name] = "0.00%"
            except: month_data[name] = "0.00%"
        data_list.append(month_data)
    return data_list

if st.session_state.pension_page == "page1": st.progress(25, text="שלב 1 מתוך 4: פרטי החוסך ודמי ניהול")
elif st.session_state.pension_page == "page2": st.progress(50, text="שלב 2 מתוך 4: הגדרת חלוקת מסלולים משולבת")
elif st.session_state.pension_page == "analysis": st.progress(75, text="שלב 3 מתוך 4: מנוע ניתוח ודוח AI")
elif st.session_state.pension_page == "projection": st.progress(100, text="שלב 4 מתוך 4: סימולציית פרישה לגיל 65")
st.write("---")
# =====================================================================
# 📋 דף 1: פרטים אישיים ודמי ניהול
# =====================================================================
if st.session_state.pension_page == "page1":
    st.title("🧓 שלב 1: הגדרת נתוני החוסך ודמי הניהול")
    st.write("אנא הזן את פרטי החברה המנהלת, מצב השכר הנוכחי והצפי לעתיד:")
    
    saved_info = st.session_state.user_info
    col1, col2 = st.columns(2)
    with col1:
        company_list = list(COMPANY_TRACKS_REGISTRY.keys())
        default_company_idx = company_list.index(saved_info["company"]) if "company" in saved_info else 0
        company_name = st.selectbox("שם החברה המנהלת:", company_list, index=default_company_idx)
        user_age = st.number_input("גיל המשתמש הנוכחי:", min_value=18, max_value=100, value=saved_info.get("age", 35))
        total_balance = st.number_input("יתרה צבורה נוכחית בש\"ח:", min_value=0, value=saved_info.get("balance", 150000), step=10000)
    
    with col2:
        st.markdown("**💼 נתוני שכר והפקדות חודשיות:**")
        current_salary = st.number_input("משכורת חודשית נוכחית (ברוטו בש\"ח):", min_value=0, value=saved_info.get("current_salary", 15000), step=1000)
        target_salary = st.number_input("משכורת חודשית משוערת לקראת הפרישה (בש\"ח):", min_value=0, value=saved_info.get("target_salary", 25000), step=1000)
        suggested_deposit = int(current_salary * 0.185)
        monthly_deposit = st.number_input("סך הפקדה חודשית נוכחית לקופה (ברוטו בש\"ח):", min_value=0, value=saved_info.get("monthly_deposit", suggested_deposit), step=100)
        
        st.markdown("**💸 דמי ניהול נוכחיים:**")
        sub_c1, sub_c2 = st.columns(2)
        fee_from_deposit = sub_c1.number_input("דמי ניהול מהפקדה (%):", min_value=0.0, max_value=6.0, value=saved_info.get("fee_deposit", 1.5), step=0.1)
        fee_from_balance = sub_c2.number_input("דמי ניהול מצבירה שנתית (%):", min_value=0.0, max_value=1.1, value=saved_info.get("fee_balance", 0.22), step=0.01)
        
    st.write("---")
    if st.button("המשך לבחירת מסלולי ההשקעה ➡️", type="primary"):
        st.session_state.user_info = {
            "company": company_name, "age": user_age, "balance": total_balance,
            "current_salary": current_salary, "target_salary": target_salary,
            "monthly_deposit": monthly_deposit, "fee_deposit": fee_from_deposit, "fee_balance": fee_from_balance
        }
        navigate_to("page2")
# =====================================================================
# 📊 דף 2: הגדרת חלוקת מסלולים משולבת ומרובה (מתוקן)
# =====================================================================
elif st.session_state.pension_page == "page2":
    if not st.session_state.user_info: navigate_to("page1")
        
    selected_company = st.session_state.user_info["company"]
    st.title("📊 שלב 2: הגדרת חלוקת מסלולים משולבת")
    st.write(f"החברה המנהלת: **{selected_company}**")
    
    available_tracks = COMPANY_TRACKS_REGISTRY[selected_company]
    
    # 🛠️ התיקון הקריטי: הסרת הסוגריים המרובעים המיותרים ב-default למניעת השגיאה מהצילום מסך
    chosen_tracks = st.multiselect(
        "בחר את מסלולי ההשקעה הפעילים בקופה שלך:", 
        list(available_tracks.keys()), 
        default=list(available_tracks.keys())
    )
    
    track_split_data = {}
    total_split_pct = 0
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🛠️ קביעת משקלים למסלולים")
        if not chosen_tracks: st.warning("אנא בחר לפחות מסלול אחד.")
        else:
            for track in chosen_tracks:
                default_w = max(0, 100 // len(chosen_tracks)) if len(chosen_tracks) > 1 else 100
                weight_input = st.number_input(f"משקל מסלול '{track}' בתיק (%):", min_value=0, max_value=100, value=default_w, step=5)
                track_split_data[track] = weight_input
                total_split_pct += weight_input
            st.write("---")
            if total_split_pct == 100: st.success(f"✔️ חלוקה תקינה! {total_split_pct}%")
            else: st.error(f"❌ סך משקלי המסלול עומד על {total_split_pct}%. עליך להגיע ל-100% בדיוק.")

    aggregated_mix = {"S&P 500": 0.0, "TA 125": 0.0, "Nasdaq 100": 0.0, "Bonds": 0.0, "Cash": 0.0}
    if total_split_pct == 100 and chosen_tracks:
        for track, track_weight in track_split_data.items():
            for asset, asset_pct in available_tracks[track].items():
                aggregated_mix[asset] += asset_pct * (track_weight / 100)

    with col2:
        st.subheader("🔮 פילוח נכסים משוקלל סופי")
        if total_split_pct == 100:
            mix_df = pd.DataFrame({"אפיק השקעה": list(aggregated_mix.keys()), "אחוז": list(aggregated_mix.values())})
            fig = px.pie(mix_df, values="אחוז", names="אפיק השקעה", hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
        else: st.info("הגרף יוצג לאחר איזון ל-100%.")

    st.write("---")
    c_back, c_next = st.columns(2)
    if c_back.button("↩️ חזור"): navigate_to("page1")
    if c_next.button("בצע ניתוח ביצועים ודוח AI! 🚀", type="primary", disabled=(total_split_pct != 100)):
        st.session_state.user_info["fund"] = " | ".join([f"{t} ({w}%)" for t, w in track_split_data.items()])
        st.session_state.mix_data = aggregated_mix
        navigate_to("analysis")
# =====================================================================
# 🔮 דף 3: מנוע ניתוח ביצועי פנסיה, היסטוריה ודוח AI
# =====================================================================
elif st.session_state.pension_page == "analysis":
    if not st.session_state.mix_data or not st.session_state.user_info: navigate_to("page1")
        
    st.title("🔮 מנוע ניתוח ביצועי פנסיה ודוח AI")
    u = st.session_state.user_info
    st.subheader(f"אומדן ביצועים עבור: {u['fund']} ({u['company']})")
    
    if st.button("↩️ חזור לעריכת תמהיל התיק"): navigate_to("page2")
        
    st.write("---")
    with st.spinner("מחשב נתונים בזמן אמת והיסטוריית דיווחים..."):
        benchmark_returns = get_benchmark_returns()
        total_gross_return = sum(benchmark_returns.get(asset, 0.0) * (weight / 100) for asset, weight in st.session_state.mix_data.items())
        
        total_monthly_fees_nis = (u["monthly_deposit"] * (u["fee_deposit"] / 100)) + (u["balance"] * ((u["fee_balance"] / 100) / 12))
        total_net_return = total_gross_return - ((total_monthly_fees_nis / u["balance"]) * 100 if u["balance"] > 0 else 0.0)
        money_change_net = u["balance"] * (total_net_return / 100)
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("תשואה מוערכת (נטו החודש)", f"{total_net_return:+.2f}%")
        m2.metric("סה\"כ דמי ניהול החודש", f"{total_monthly_fees_nis:,.2f} ₪")
        m3.metric("שינוי כספי מוערך (נטו)", f"{money_change_net:+,.2f} ₪")
        m4.metric("שווי תיק מעודכן", f"{u['balance'] + money_change_net:,.2f} ₪")
        
        # 📊 הוספת טבלת תשואות היסטוריות של חודשים קודמים
        st.write("### 📅 היסטוריית תשואות מדדי הקופה בחודשים הקודמים")
        history_data = get_historical_months_returns()
        st.dataframe(pd.DataFrame(history_data), use_container_width=True)
        
        st.write("---")
        if not api_key: st.info("💡 הזן מפתח API בתפריט הצד לקבלת דוח AI.")
        else:
            with st.spinner("מנוע ה-AI מנתח את נתוני הפנסיה וההיסטוריה..."):
                user_context = f"Company: {u['company']}, Split Tracks: {u['fund']}, Balance: {u['balance']} NIS, Combined Net Return: {total_net_return}%, History: {history_data}"
                system_instruction = "אתה מומחה פנסיוני ואקטואר בכיר. נתח את ביצועי החודש וההיסטוריה וספק דוח מקצועי בעברית בלבד."
                try:
                    client = genai.Client(api_key=api_key)
                    response = client.models.generate_content(model='gemini-2.5-flash', contents=user_context, config=types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.2))
                    st.markdown(response.text)
                except Exception as e: st.error(f"שגיאה בהפקת הדוח: {str(e)}")
                    
    if st.button("המשך לסימולציית גיל פרישה (65) 🚀", type="primary"): navigate_to("projection")

# =====================================================================
# 📈 שלב 4: סימולציית פרישה - שכר דינמי וריבית דריבית
# =====================================================================
elif st.session_state.pension_page == "projection":
    if not st.session_state.user_info: navigate_to("page1")
    st.title("📈 שלב 4: סימולציית הון וקצבה צפויה בגיל 65")
    if st.button("↩️ חזור לדוח הניתוח"): navigate_to("analysis")
        
    u = st.session_state.user_info
    years_to_retire = 65 - u["age"]
    if years_to_retire <= 0: st.warning("גיל המשתמש גבוה או שווה ל-65.")
    else:
        salary_growth_rate = (u["target_salary"] / u["current_salary"]) ** (1 / years_to_retire) - 1 if u["target_salary"] > u["current_salary"] else 0.0
        st.info(f"💡 מודל הסימולציה מניח קידום שכר שנתי ממוצע של **{salary_growth_rate*100:.2f}%**.")
        annual_return_input = st.number_input("הנחת תשואה שנתית ממוצעת (%):", min_value=1.0, max_value=15.0, value=6.5, step=0.5)
        conversion_coefficient = st.number_input("מקדם המרה צפוי לקצבה:", min_value=150, max_value=250, value=200)
        
        deposit_ratio = u["monthly_deposit"] / u["current_salary"]
        balance, age_axis, balance_axis, salary_axis = u["balance"], [], [], []
        active_salary = u["current_salary"]
        
        for year in range(1, years_to_retire + 1):
            active_salary *= (1 + salary_growth_rate)
            balance += (active_salary * deposit_ratio * 12) * (1 - (u["fee_deposit"]/100))
            balance *= (1 + (annual_return_input/100)) * (1 - (u["fee_balance"]/100))
            age_axis.append(u["age"] + year)
            balance_axis.append(round(balance))
            salary_axis.append(round(active_salary))
            
        st.write("---")
        st.subheader("📊 תוצאות שיערוך מבוסס גידול שכר דינמי")
        p1, p2, p3 = st.columns(3)
        p1.metric("משכורת פרישה משוערת", f"{salary_axis[-1]:,} ₪")
        p2.metric("סכום צבורה בפרישה", f"{balance_axis[-1]:,.0f} ₪")
        p3.metric("קצבה חודשית צפויה", f"{balance_axis[-1] / conversion_coefficient:,.0f} ₪ / חודש")
        
        fig_line = px.line(pd.DataFrame({"גיל": age_axis, "צבורה משוערת": balance_axis}), x="גיל", y="צבורה משוערת", title="צמיחת חסכון הפנסיה המצטבר", markers=True)
        st.plotly_chart(fig_line, use_container_width=True)
