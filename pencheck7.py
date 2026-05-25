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
# תוכל להדביק את המפתח שלך בין הגרשיים כאן למטה, למשל: "AIzaSy..."
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
if "chosen_tracks_data" not in st.session_state:
    st.session_state.chosen_tracks_data = {}

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
# מיפוי חברות הביטוח למסלולי ההשקעה ונתוני דיווח התשואות ההיסטוריות שלהן
COMPANY_TRACKS_REGISTRY = {
    "הראל פנסיה וגמל": {
        "מסלול מחקה S&P 500": {
            "allocation": {"S&P 500": 100, "TA 125": 0, "Nasdaq 100": 0, "Bonds": 0, "Cash": 0},
            "historical_returns": {"ינואר 2026": 2.1, "פברואר 2026": -1.4, "מרץ 2026": 3.2, "אפריל 2026": 1.8}
        },
        "מסלול מנייתי כללי": {
            "allocation": {"S&P 500": 45, "TA 125": 25, "Nasdaq 100": 20, "Bonds": 5, "Cash": 5},
            "historical_returns": {"ינואר 2026": 1.8, "פברואר 2026": -0.9, "מרץ 2026": 2.5, "אפריל 2026": 1.1}
        },
        "מסלול כללי / מאוזן": {
            "allocation": {"S&P 500": 20, "TA 125": 15, "Nasdaq 100": 10, "Bonds": 40, "Cash": 15},
            "historical_returns": {"ינואר 2026": 0.9, "פברואר 2026": 0.2, "מרץ 2026": 1.1, "אפריל 2026": 0.5}
        },
        "מסלול אג\"ח סולידי": {
            "allocation": {"S&P 500": 0, "TA 125": 0, "Nasdaq 100": 0, "Bonds": 85, "Cash": 15},
            "historical_returns": {"ינואר 2026": 0.2, "פברואר 2026": 0.5, "מרץ 2026": -0.1, "אפריל 2026": 0.3}
        }
    },
    "אלטשולר שחם": {
        "מסלול מנייתי חוץ לארץ": {
            "allocation": {"S&P 500": 60, "TA 125": 10, "Nasdaq 100": 20, "Bonds": 5, "Cash": 5},
            "historical_returns": {"ינואר 2026": 2.3, "פברואר 2026": -1.6, "מרץ 2026": 2.9, "אפריל 2026": 1.4}
        },
        "מסלול מחקה מדדים": {
            "allocation": {"S&P 500": 50, "TA 125": 20, "Nasdaq 100": 30, "Bonds": 0, "Cash": 0},
            "historical_returns": {"ינואר 2026": 2.0, "פברואר 2026": -1.2, "מרץ 2026": 3.4, "אפריל 2026": 1.9}
        },
        "מסלול כללי": {
            "allocation": {"S&P 500": 25, "TA 125": 15, "Nasdaq 100": 15, "Bonds": 35, "Cash": 10},
            "historical_returns": {"ינואר 2026": 0.8, "פברואר 2026": -0.1, "מרץ 2026": 1.4, "אפריל 2026": 0.7}
        },
        "מסלול שקלי קצר": {
            "allocation": {"S&P 500": 0, "TA 125": 0, "Nasdaq 100": 0, "Bonds": 20, "Cash": 80},
            "historical_returns": {"ינואר 2026": 0.3, "פברואר 2026": 0.3, "מרץ 2026": 0.4, "אפריל 2026": 0.3}
        }
    },
    "מנורה מבטחים": {
        "מנורה מנייתי": {
            "allocation": {"S&P 500": 40, "TA 125": 30, "Nasdaq 100": 15, "Bonds": 10, "Cash": 5},
            "historical_returns": {"ינואר 2026": 1.7, "פברואר 2026": -1.1, "מרץ 2026": 2.3, "אפריל 2026": 1.2}
        },
        "מנורה מחקה S&P 500": {
            "allocation": {"S&P 500": 100, "TA 125": 0, "Nasdaq 100": 0, "Bonds": 0, "Cash": 0},
            "historical_returns": {"ינואר 2026": 2.2, "פברואר 2026": -1.5, "מרץ 2026": 3.1, "אפריל 2026": 1.7}
        },
        "מנורה כללי": {
            "allocation": {"S&P 500": 20, "TA 125": 20, "Nasdaq 100": 10, "Bonds": 40, "Cash": 10},
            "historical_returns": {"ינואר 2026": 1.0, "פברואר 2026": 0.1, "מרץ 2026": 1.3, "אפריל 2026": 0.6}
        }
    },
    "הפניקס": {
        "הפניקס מנייתי": {
            "allocation": {"S&P 500": 45, "TA 125": 25, "Nasdaq 100": 15, "Bonds": 10, "Cash": 5},
            "historical_returns": {"ינואר 2026": 1.9, "פברואר 2026": -1.0, "מרץ 2026": 2.6, "אפריל 2026": 1.3}
        },
        "הפניקס מחקה S&P 500": {
            "allocation": {"S&P 500": 100, "TA 125": 0, "Nasdaq 100": 0, "Bonds": 0, "Cash": 0},
            "historical_returns": {"ינואר 2026": 2.1, "פברואר 2026": -1.4, "מרץ 2026": 3.2, "אפריל 2026": 1.8}
        },
        "הפניקס מסלול לבני 50 ומטה": {
            "allocation": {"S&P 500": 30, "TA 125": 20, "Nasdaq 100": 15, "Bonds": 25, "Cash": 10},
            "historical_returns": {"ינואר 2026": 1.2, "פברואר 2026": -0.4, "מרץ 2026": 1.8, "אפריל 2026": 0.8}
        }
    },
    "מיטב גמל ופנסיה": {
        "מיטב מנייתי": {
            "allocation": {"S&P 500": 50, "TA 125": 20, "Nasdaq 100": 20, "Bonds": 5, "Cash": 5},
            "historical_returns": {"ינואר 2026": 2.0, "פברואר 2026": -1.3, "מרץ 2026": 2.8, "אפריל 2026": 1.5}
        },
        "מיטב מחקה S&P 500": {
            "allocation": {"S&P 500": 100, "TA 125": 0, "Nasdaq 100": 0, "Bonds": 0, "Cash": 0},
            "historical_returns": {"ינואר 2026": 2.1, "פברואר 2026": -1.4, "מרץ 2026": 3.2, "אפריל 2026": 1.8}
        },
        "מיטב כללי": {
            "allocation": {"S&P 500": 25, "TA 125": 15, "Nasdaq 100": 10, "Bonds": 40, "Cash": 10},
            "historical_returns": {"ינואר 2026": 0.9, "פברואר 2026": 0.1, "מרץ 2026": 1.5, "אפריל 2026": 0.6}
        }
    }
}

def get_benchmark_returns():
    benchmarks = {"S&P 500": "^SPX", "TA 125": "^TA125.TA", "Nasdaq 100": "^NDX", "Bonds": "AGG", "Cash": "BIL"}
    start_of_month = datetime(datetime.today().year, datetime.today().month, 1).strftime('%Y-%m-%d')
    returns = {}
    for name, ticker in benchmarks.items():
        try:
            hist = yf.Ticker(ticker).history(start=start_of_month)
            if not hist.empty and len(hist) >= 2:
                returns[name] = ((float(hist['Close'].iloc[-1]) - float(hist['Close'].iloc)) / float(hist['Close'].iloc)) * 100
            else:
                returns[name] = 0.0
        except:
            returns[name] = 0.0
    return returns

# 🗺️ תצוגת סרגל התקדמות ויזואלי מעודכן ל-4 שלבים
if st.session_state.pension_page == "page1":
    st.progress(25, text="שלב 1 מתוך 4: פרטי החוסך ודמי ניהול")
elif st.session_state.pension_page == "page2":
    st.progress(50, text="שלב 2 מתוך 4: הגדרת חלוקת מסלולים משולבת")
elif st.session_state.pension_page == "analysis":
    st.progress(75, text="שלב 3 מתוך 4: מנוע ניתוח, תשואות היסטוריות ודוח AI")
elif st.session_state.pension_page == "projection":
    st.progress(100, text="שלב 4 מתוך 4: סימולציית פרישה לגיל 65")
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
        
        st.markdown("**💸 דמי ניהול נוכחי:**")
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
# 📊 דף 2: הגדרת חלוקת מסלולים משולבת ומרובה
# =====================================================================
elif st.session_state.pension_page == "page2":
    if not st.session_state.user_info:
        navigate_to("page1")
        
    selected_company = st.session_state.user_info["company"]
    st.title("📊 שלב 2: הגדרת חלוקת מסלולים משולבת")
    st.write(f"החברה המנהלת: **{selected_company}**")
    st.info("באפשרותך לבחור מסלול אחד או יותר ולחלק ביניהם את אחוזי החיסכון. סך המסלולים חייב להסתכם ל-100%.")
    
    available_tracks = COMPANY_TRACKS_REGISTRY[selected_company]
    chosen_tracks = st.multiselect("בחר את מסלולי ההשקעה הפעילים בקופה שלך:", list(available_tracks.keys()), default=[list(available_tracks.keys())])
    
    track_split_data = {}
    total_split_pct = 0
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🛠️ קביעת משקלים למסלולים שנבחרו")
        if not chosen_tracks:
            st.warning("אנא בחר לפחות מסלול השקעה אחד כדי להמשיך.")
        else:
            for track in chosen_tracks:
                default_w = max(0, 100 // len(chosen_tracks)) if len(chosen_tracks) > 1 else 100
                weight_input = st.number_input(f"משקל מסלול '{track}' בתיק (%):", min_value=0, max_value=100, value=default_w, step=5)
                track_split_data[track] = weight_input
                total_split_pct += weight_input
            
            st.write("---")
            if total_split_pct == 100:
                st.success(f"✔️ חלוקת מסלולים תקינה! הסכום שווה ל-{total_split_pct}%")
            else:
                st.error(f"❌ שגיאה: סך משקלי המסלול עומד על {total_split_pct}%. עליך להגיע ל-100% בדיוק.")

    # שקלול מתמטי של נכסי הבסיס בהתאם לאחוזי המסלולים שהוגדרו
    aggregated_mix = {"S&P 500": 0.0, "TA 125": 0.0, "Nasdaq 100": 0.0, "Bonds": 0.0, "Cash": 0.0}
    if total_split_pct == 100 and chosen_tracks:
        for track, track_weight in track_split_data.items():
            track_profile = available_tracks[track]["allocation"]
            for asset, asset_pct in track_profile.items():
                aggregated_mix[asset] += asset_pct * (track_weight / 100)

    with col2:
        st.subheader("🔮 פילוח נכסים משוקלל סופי")
        if total_split_pct == 100:
            st.write("שילוב נכסי הבסיס הסופי בתיק הפנסיה שלך:")
            mix_df = pd.DataFrame({"אפיק השקעה": list(aggregated_mix.keys()), "אחוז": list(aggregated_mix.values())})
            fig = px.pie(mix_df, values="אחוז", names="אפיק השקעה", hole=0.4, title="פילוח משוקלל משולב")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("הגרף יוצג לאחר איזון משקלי המסלולים ל-100%.")

    st.write("---")
    c_back, c_next = st.columns(2)
    if c_back.button("↩️ חזור לפרטים אישיים"):
        navigate_to("page1")
        
    if c_next.button("בצע ניתוח ביצועים ודוח AI! 🚀", type="primary", disabled=(total_split_pct != 100)):
        track_summary_str = " | ".join([f"{t} ({w}%)" for t, w in track_split_data.items()])
        st.session_state.user_info["fund"] = track_summary_str
        st.session_state.mix_data = aggregated_mix
        st.session_state.chosen_tracks_data = track_split_data  # שמירת חלוקת המסלולים הספציפית לחישוב ההיסטורי
        navigate_to("analysis")
# =====================================================================
# 🔮 דף 3: מנוע ניתוח ביצועי פנסיה, תשואות היסטוריות ודוח AI
# =====================================================================
elif st.session_state.pension_page == "analysis":
    if not st.session_state.mix_data or not st.session_state.user_info:
        navigate_to("page1")
        
    st.title("🔮 מנוע ניתוח ביצועי פנסיה ודוח AI")
    u = st.session_state.user_info
    selected_company = u["company"]
    st.subheader(f"אומדן ביצועים עבור שילוב המסלולים: {u['fund']} בחברת {selected_company}")
    
    if st.button("↩️ חזור לעריכת תמהיל התיק"):
        navigate_to("page2")
        
    st.write("---")
    with st.spinner("שולף נתוני שוק ומחשב עלויות דמי ניהול..."):
        benchmark_returns = get_benchmark_returns()
        total_gross_return = sum(benchmark_returns.get(asset, 0.0) * (weight / 100) for asset, weight in st.session_state.mix_data.items())
        
        rows = [{"אפיק השקעה": a, "משקל משוקלל": f"{w:.1f}%", "תשואת האפיק החודש": f"{benchmark_returns.get(a,0.0):+.2f}%"} for a, w in st.session_state.mix_data.items()]
        
        total_monthly_fees_nis = (u["monthly_deposit"] * (u["fee_deposit"] / 100)) + (u["balance"] * ((u["fee_balance"] / 100) / 12))
        total_net_return = total_gross_return - ((total_monthly_fees_nis / u["balance"]) * 100 if u["balance"] > 0 else 0.0)
        money_change_net = u["balance"] * (total_net_return / 100)
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("תשואה מוערכת (נטו)", f"{total_net_return:+.2f}%")
        m2.metric("סה\"כ דמי ניהול החודש", f"{total_monthly_fees_nis:,.2f} ₪")
        m3.metric("שינוי כספי מוערך (נטו)", f"{money_change_net:+,.2f} ₪")
        m4.metric("שווי תיק מעודכן", f"{u['balance'] + money_change_net:,.2f} ₪")
        
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
        
        # =====================================================================
        # 📊 חלק חדש: חישוב והצגת טבלת תשואות היסטוריות מדווחות
        # =====================================================================
        st.write("---")
        st.subheader("📋 טבלת דיווחי תשואות היסטוריות של התיק המשולב (חודשים קודמים)")
        st.write("נתונים אלו מבוססים על דיווחי החברה הרשמיים לרשות שוק ההון עבור המסלולים שנבחרו:")
        
        available_tracks = COMPANY_TRACKS_REGISTRY[selected_company]
        history_summary = {}
        
        # חישוב התשואה המשוקללת לכל חודש עבר בנפרד
        for track, track_weight in st.session_state.chosen_tracks_data.items():
            track_history = available_tracks[track]["historical_returns"]
            for month, month_return in track_history.items():
                if month not in history_summary:
                    history_summary[month] = 0.0
                history_summary[month] += month_return * (track_weight / 100)
                
        # בניית הטבלה הויזואלית למשתמש
        history_rows = [{"חודש דיווח": m, "תשואה היסטורית משוקללת לתיק שלך": f"{r:+.2f}%"} for m, r in history_summary.items()]
        st.dataframe(pd.DataFrame(history_rows), use_container_width=True)
        
        # דוח ה-AI המורחב
        st.write("---")
        if not api_key:
            st.info("💡 הזן מפתח API בתפריט הצד לקבלת דוח AI.")
        else:
            with st.spinner("מנוע ה-AI מנתח את נתוני הפנסיה והביצועים ההיסטוריים..."):
                user_context = (
                    f"Company: {selected_company}, Profile: {u['fund']}, Age: {u['age']}, Balance: {u['balance']} NIS, "
                    f"Current Month Live Return: {total_net_return:.2f}%, Historical Months Reported Data: {history_summary}"
                )
                system_instruction = "אתה מומחה פנסיוני ואקטואר בכיר. נתח את נתוני האמת החיים ואת דיווחי החודשים הקודמים, וספק דוח ייעוץ פנסיוני מקצועי ומקיף בעברית."
                try:
                    client = genai.Client(api_key=api_key)
                    response = client.models.generate_content(model='gemini-2.5-flash', contents=user_context, config=types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.2))
                    st.markdown(response.text)
                except Exception as e:
                    st.error(f"שגיאה בהפקת הדוח: {str(e)}")
                    
    if st.button("המשך לסימולציית גיל פרישה (65) 🚀", type="primary"):
        navigate_to("projection")

# =====================================================================
# 📈 שלב 4: סימולציית פרישה - שכר דינמי וריבית דריבית
# =====================================================================
elif st.session_state.pension_page == "projection":
    if not st.session_state.user_info:
        navigate_to("page1")
    st.title("📈 שלב 4: סימולציית הון וקצבה צפויה בגיל 65")
    if st.button("↩️ חזור לדוח הניתוח"):
        navigate_to("analysis")
        
    u = st.session_state.user_info
    years_to_retire = 65 - u["age"]
    if years_to_retire <= 0:
        st.warning("גיל המשתמש גבוה או שווה ל-65.")
    else:
        salary_growth_rate = (u["target_salary"] / u["current_salary"]) ** (1 / years_to_retire) - 1 if u["target_salary"] > u["current_salary"] else 0.0
        st.info(f"💡 מודל הסימולציה מניח קידום שכר שנתי ממוצע של **{salary_growth_rate*100:.2f}%**.")
        
        annual_return_input = st.number_input("הנחת תשואה שנתית ממוצעת של שוק ההון (%):", min_value=1.0, max_value=15.0, value=6.5, step=0.5)
        conversion_coefficient = st.number_input("מקדם המרה צפוי לקצבה:", min_value=150, max_value=250, value=200)
        
        deposit_ratio = u["monthly_deposit"] / u["current_salary"]
        balance, age_axis, balance_axis, salary_
