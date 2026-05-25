import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from google import genai
from google.genai import types

# =====================================================================
# הגדרת מפתח API קבוע מראש (אם יש)
# =====================================================================
DEFAULT_GEMINI_KEY = "" 

st.set_page_config(page_title="מערכת AI בזמן אמת לניטור פנסיה", page_icon="💰", layout="wide")

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
        "הפניקס מנייתי": {"S&P 500": 45, "TA 125": 25, "Nasdaq 100": 20, "Bonds": 5, "Cash": 5},
        "הפניקס מחקה S&P 500": {"S&P 500": 100, "TA 125": 0, "Nasdaq 100": 0, "Bonds": 0, "Cash": 0},
        "הפניקס מסלול לבני 50 ומטה": {"S&P 500": 30, "TA 125": 20, "Nasdaq 100": 15, "Bonds": 25, "Cash": 10}
    },
    "מיטב גמל ופנסיה": {
        "מיטב מנייתי": {"S&P 500": 50, "TA 125": 20, "Nasdaq 100": 20, "Bonds": 5, "Cash": 5},
        "מיטב מחקה S&P 500": {"S&P 500": 100, "TA 125": 0, "Nasdaq 100": 0, "Bonds": 0, "Cash": 0},
        "מיטב כללי": {"S&P 500": 25, "TA 125": 15, "Nasdaq 100": 10, "Bonds": 40, "Cash": 10}
    },
    "מגדל מקפת": {
        "מגדל מקפת מנייתי": {"S&P 500": 45, "TA 125": 20, "Nasdaq 100": 20, "Bonds": 10, "Cash": 5},
        "מגדל מקפת מחקה S&P 500": {"S&P 500": 100, "TA 125": 0, "Nasdaq 100": 0, "Bonds": 0, "Cash": 0},
        "מגדל מקפת כללי לקבוצות": {"S&P 500": 22, "TA 125": 18, "Nasdaq 100": 10, "Bonds": 35, "Cash": 15}
    }
}

BENCHMARKS = {"S&P 500": "^SPX", "TA 125": "^TA125.TA", "Nasdaq 100": "^NDX", "Bonds": "AGG", "Cash": "BIL"}
def get_benchmark_returns():
    returns = {}
    for name, ticker in BENCHMARKS.items():
        try:
            hist = yf.Ticker(ticker).history(period="1mo")
            if not hist.empty and len(hist) >= 2:
                initial_price = float(hist['Close'].iloc[0])
                current_price = float(hist['Close'].iloc[-1])
                returns[name] = ((current_price - initial_price) / initial_price) * 100
            else:
                returns[name] = 0.0
        except:
            returns[name] = 0.0
            
    # חישוב השפעת שער הדולר (USD/ILS) מתחילת החודש
    usd_effect = 0.0
    try:
        usd_hist = yf.Ticker("ILS=X").history(period="1mo")
        if not usd_hist.empty and len(usd_hist) >= 2:
            usd_initial = float(usd_hist['Close'].iloc[0])
            usd_current = float(usd_hist['Close'].iloc[-1])
            usd_effect = ((usd_current - usd_initial) / usd_initial) * 100
    except:
        pass

    # עדכון מסלולים החשופים לדולר
    usd_exposed = ["S&P 500", "Nasdaq 100"]
    for asset in usd_exposed:
        if asset in returns:
            returns[asset] += usd_effect

    return returns

def get_historical_tracks_returns(chosen_tracks, available_tracks):
    data_list = []
    cached_histories = {}
    for name, ticker in BENCHMARKS.items():
        try:
            df = yf.Ticker(ticker).history(period="6mo")
            if not df.empty and len(df) >= 80:
                cached_histories[name] = list(df['Close'].values)
        except: 
            pass
            
    if not cached_histories or len(list(cached_histories.values())) < 1:
        return [{"חודש": "Month - 1"}]
        
    for i in range(1, 4):
        start_idx = -(i + 1) * 21
        end_idx = -i * 21
        month_label = f"Month - {i}"
        
        raw_index_returns = {}
        for name in BENCHMARKS.keys():
            if name in cached_histories:
                prices = cached_histories[name]
                try: 
                    raw_index_returns[name] = ((prices[end_idx] - prices[start_idx]) / prices[start_idx]) * 100
                except: 
                    raw_index_returns[name] = 0.0
            else: 
                raw_index_returns[name] = 0.0
        
        month_row = {"חודש": month_label}
        for track in chosen_tracks:
            track_components = available_tracks[track]
            weighted_track_return = 0.0
            for asset, asset_pct in track_components.items():
                weighted_track_return += raw_index_returns.get(asset, 0.0) * (asset_pct / 100)
            month_row[track] = f"{weighted_track_return:+.2f}%"
        data_list.append(month_row)
    return data_list

# בר פרוגרס עליון קבוע לחווית משתמש
if st.session_state.pension_page == "page1": 
    st.progress(25, text="שלב 1 מתוך 4: פרטי החוסך ודמי ניהול")
elif st.session_state.pension_page == "page2": 
    st.progress(50, text="שלב 2 מתוך 4: הגדרת חלוקת מסלולים משולבת")
elif st.session_state.pension_page == "analysis": 
    st.progress(75, text="שלב 3 מתוך 4: מנוע ניתוח ודוח AI")
elif st.session_state.pension_page == "projection": 
    st.progress(100, text="שלב 4 מתוך 4: סימולציית פרישה לגיל 65")
st.write("---")
if st.session_state.pension_page == "page1":
    st.title("שלב 1: הגדרת נתוני החוסך ודמי הניהול")
    st.write("אנא הזן את פרטי החברה המנהלת, מצב השכר הנוכחי והצפי לעתיד:")
    
    saved_info = st.session_state.user_info
    col1, col2 = st.columns(2)
    
    with col1:
        company_list = list(COMPANY_TRACKS_REGISTRY.keys())
        default_company_idx = company_list.index(saved_info["company"]) if "company" in saved_info else 0
        company_name = st.selectbox("שם החברה המנהלת:", company_list, index=default_company_idx)
        user_age = st.number_input("גיל המשתמש הנוכחי:", min_value=18, max_value=100, value=saved_info.get("age", 30))
        total_balance = st.number_input("יתרה צבורה נוכחית בחשבון (ש\"ח):", min_value=0, value=saved_info.get("balance", 200000), step=10000)
    
    with col2:
        st.markdown("**נתוני שכר והפקדות חודשיות:**")
        current_salary = st.number_input("משכורת חודשית ברוטו נוכחית (ש\"ח):", min_value=0, value=saved_info.get("current_salary", 15000), step=1000)
        target_salary = st.number_input("משכורת חודשית משוערת לקראת הפרישה (ש\"ח):", min_value=0, value=saved_info.get("target_salary", 22000), step=1000)
        suggested_deposit = int(current_salary * 0.185)
        deposit_monthly = st.number_input("סך הפקדה חודשית נוכחית לקופה (ברוטו בש\"ח):", min_value=0, value=saved_info.get("monthly_deposit", suggested_deposit), step=100)
        
        st.markdown("**דמי ניהול נוכחיים:**")
        sub_c1, sub_c2 = st.columns(2)
        fee_from_deposit = sub_c1.number_input("דמי ניהול מהפקדה (%):", min_value=0.0, max_value=6.0, value=saved_info.get("fee_deposit", 1.5), step=0.1)
        fee_from_balance = sub_c2.number_input("דמי ניהול משנתית מצבירה (%):", min_value=0.0, max_value=1.1, value=saved_info.get("fee_balance", 0.22), step=0.01)
    
    st.write("---")
    if st.button("המשך לבחירת מסלולי ההשקעה", type="primary"):
        st.session_state.user_info = {
            "company": company_name, "age": user_age, "balance": total_balance,
            "current_salary": current_salary, "target_salary": target_salary,
            "monthly_deposit": deposit_monthly, "fee_deposit": fee_from_deposit, "fee_balance": fee_from_balance
        }
        navigate_to("page2")
elif st.session_state.pension_page == "page2":
    if not st.session_state.user_info: 
        navigate_to("page1")
    
    selected_company = st.session_state.user_info["company"]
    st.title("שלב 2: הגדרת חלוקת מסלולים משולבת")
    st.write(f"החברה המנהלת: **{selected_company}**")
    
    available_tracks = COMPANY_TRACKS_REGISTRY[selected_company]
    chosen_tracks = st.multiselect(
        "בחר את מסלולי ההשקעה הפעילים בקופה שלך:",
        list(available_tracks.keys()), 
        default=list(available_tracks.keys())[:1]
    )
    
    track_split_data = {}
    total_split_pct = 0
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("קביעת משקלים למסלולים")
        if not chosen_tracks: 
            st.warning("אנא בחר לפחות מסלול אחד.")
        else:
            for track in chosen_tracks:
                default_w = max(0, 100 // len(chosen_tracks)) if len(chosen_tracks) > 1 else 100
                weight_input = st.number_input(f"משקל מסלול {track} בתיק (%):", min_value=0, max_value=100, value=default_w, step=5)
                track_split_data[track] = weight_input
                total_split_pct += weight_input
            st.write("---")
            if total_split_pct == 100: 
                st.success(f"חלוקה תקינה! {total_split_pct}%")
            else: 
                st.error(f"❌ סך משקלי המסלול עומד על {total_split_pct}%. עליך להגיע ל-100% בדיוק.")
                
    aggregated_mix = {"S&P 500": 0.0, "TA 125": 0.0, "Nasdaq 100": 0.0, "Bonds": 0.0, "Cash": 0.0}
    if total_split_pct == 100 and chosen_tracks:
        for track, track_weight in track_split_data.items():
            for asset, asset_pct in available_tracks[track].items():
                aggregated_mix[asset] += asset_pct * (track_weight / 100)
                
    with col2:
        st.subheader("פילוח נכסים משוקלל סופי")
        if total_split_pct == 100:
            mix_df = pd.DataFrame({"אפיק השקעה": list(aggregated_mix.keys()), "אחוז": list(aggregated_mix.values())})
            fig = px.pie(mix_df, values="אחוז", names="אפיק השקעה", hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
        else: 
            st.info("הגרף יוצג לאחר איזון ל-100%.")
            
    st.write("---")
    c_back, c_next = st.columns(2)
    if c_back.button("חזור לפרטים אישיים"): 
        navigate_to("page1")
    if c_next.button("בצע ניתוח ביצועים ודוח AI! 🚀", type="primary", disabled=(total_split_pct != 100)):
        st.session_state.user_info["fund"] = " | ".join([f"{t} ({w}%)" for t, w in track_split_data.items()])
        st.session_state.user_info["chosen_tracks_list"] = chosen_tracks
        st.session_state.mix_data = aggregated_mix
        navigate_to("analysis")
# =====================================================================
# חלק 5: הצגת תוצאות הסימולציה האקטוארית וגרף צמיחה
# =====================================================================

    st.write("---")
    st.subheader("תוצאות שיערוך אקטוארי מנוכה מס (נטו בפרישה)")
    
    # חישוב אחוז התחלופה נטו מהשכר האחרון
    replacement_rate_net = (net_pension / salary_axis[-1]) * 100 if salary_axis[-1] > 0 else 0.0
    
    # תצוגת המדדים ב-4 עמודות (כולל תיקון השגיאה מהצילום מסך)
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("משוערת פרישה משכורת", f"{salary_axis[-1]:,} ₪")
    p2.metric("בפרישה צבור סכום", f"{final_balance:,.0f} ₪")
    p3.metric("חודשית קצבה (ברוטו)", f"{gross_pension:,.0f} ₪", f"משוער מס: {final_tax_deduction:,.0f} ₪")
    p4.metric("קצבת נטו בבנק", f"{net_pension:,.0f} ₪ / לחודש", f"אחוז תחלופה נטו: {replacement_rate_net:.1f}%")
    
    # יצירת גרף קו להצגת התפתחות ההון לאורך השנים
    st.write("### גרף התפתחות ההון מול עליית השכר לאורך השנים")
    chart_df = pd.DataFrame({
        "age": age_axis, 
        "balance": balance_axis
    })
    
    # שימוש באנגלית בכותרות הגרף למניעת בעיות היפוך טקסט וקריסות
    fig_line = px.line(
        chart_df, 
        x="age", 
        y="balance", 
        title="Pension Portfolio Growth Projection", 
        markers=True
    )
    fig_line.update_layout(
        yaxis_tickformat=",.0f", 
        yaxis_title="Portfolio Value (NIS)", 
        xaxis_title="Age"
    )
    
    st.plotly_chart(fig_line, use_container_width=True)
