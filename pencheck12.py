import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from google import genai
from google.genai import types
from datetime import datetime, timedelta

st.set_page_config(page_title="מערכת AI לניהול פנסיה, השתלמות וגמל", page_icon="📊", layout="wide")

# אתחול משתני ה-Session State לניהול המעבר בין הדפים
if "pension_page" not in st.session_state:
    st.session_state.pension_page = "page1"
if "product_type" not in st.session_state:
    st.session_state.product_type = "קרן פנסיה"
if "user_info" not in st.session_state:
    st.session_state.user_info = {}
if "mix_data" not in st.session_state:
    st.session_state.mix_data = {}
if "institutional_fx_exposure" not in st.session_state:
    st.session_state.institutional_fx_exposure = 40.0

def navigate_to(page_name):
    st.session_state.pension_page = page_name
    st.rerun()

st.sidebar.header("⚙️ הגדרות ומערכת AI")
DEFAULT_GEMINI_KEY = "" 

if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
    st.sidebar.success("✔️ מפתח API נטען אוטומטית")
elif DEFAULT_GEMINI_KEY and DEFAULT_GEMINI_KEY.strip() != "":
    api_key = DEFAULT_GEMINI_KEY
    st.sidebar.success("✔️ מפתח API קבוע נטען")
else:
    api_key = st.sidebar.text_input("הזן מפתח API של Gemini:", type="password")

BENCHMARKS = {
    "S&P 500": "^SPX", 
    "TA 125": "^TA125.TA", 
    "Nasdaq 100": "^NDX", 
    "Bonds": "AGG", 
    "Cash": "BIL"
}

def get_benchmark_returns():
    """מחשב את תשואות נכסי הבסיס מה-1 לחודש הנוכחי ועד היום ומשקלל שינויי מטבע"""
    returns = {}
    today = datetime.now()
    start_of_month = datetime(today.year, today.month, 1).strftime('%Y-%m-%d')
    
    for name, ticker in BENCHMARKS.items():
        try:
            hist = yf.Ticker(ticker).history(start=start_of_month)
            if not hist.empty and len(hist) >= 2:
                initial_price = float(hist['Close'].iloc[0])
                current_price = float(hist['Close'].iloc[-1])
                returns[name] = ((current_price - initial_price) / initial_price) * 100
            else:
                returns[name] = 0.0
        except:
            returns[name] = 0.0
            
    usd_effect = 0.0
    try:
        usd_hist = yf.Ticker("ILS=X").history(start=start_of_month)
        if not usd_hist.empty and len(usd_hist) >= 2:
            usd_initial = float(usd_hist['Close'].iloc[0])
            usd_current = float(usd_hist['Close'].iloc[-1])
            usd_effect = ((usd_current - usd_initial) / usd_initial) * 100
    except:
        pass
        
    fx_multiplier = st.session_state.institutional_fx_exposure / 100.0
    effective_usd_drag = usd_effect * fx_multiplier
    
    usd_exposed_assets = ["S&P 500", "Nasdaq 100"]
    for asset in usd_exposed_assets:
        if asset in returns:
            returns[asset] += effective_usd_drag
    return returns

def get_daily_returns_chart_data(mix_data, fx_exposure_pct):
    """בונה קו תשואה יומי מצטבר מתחילת החודש על בסיס משקלי הנכסים וחשיפת המט\"ח"""
    today = datetime.now()
    start_of_month = datetime(today.year, today.month, 1).strftime('%Y-%m-%d')
    daily_series = {}
    
    for name, ticker in BENCHMARKS.items():
        try:
            df = yf.Ticker(ticker).history(start=start_of_month)
            if not df.empty:
                daily_series[name] = df['Close']
        except:
            pass
            
    if not daily_series or "S&P 500" not in daily_series:
        return pd.DataFrame()
        
    dates = daily_series["S&P 500"].index
    portfolio_daily_cumulative = []
    date_labels = []
    
    for idx, date in enumerate(dates):
        daily_gross_return = 0.0
        usd_cum_change = 0.0
        try:
            usd_df = yf.Ticker("ILS=X").history(start=start_of_month)
            if not usd_df.empty:
                usd_initial = usd_df['Close'].iloc[0]
                usd_current_day = usd_df['Close'].asof(date)
                usd_cum_change = ((usd_current_day - usd_initial) / usd_initial) * 100
        except:
            pass
            
        effective_usd_day_drag = usd_cum_change * (fx_exposure_pct / 100.0)
        
        for asset, weight in mix_data.items():
            if asset in daily_series:
                asset_prices = daily_series[asset]
                initial_p = asset_prices.iloc[0]
                current_p = asset_prices.asof(date)
                
                asset_cum_return = ((current_p - initial_p) / initial_p) * 100
                if asset in ["S&P 500", "Nasdaq 100"]:
                    asset_cum_return += effective_usd_day_drag
                    
                daily_gross_return += asset_cum_return * (weight / 100.0)
                
        portfolio_daily_cumulative.append(daily_gross_return)
        date_labels.append(date.strftime('%m-%d'))
        
    return pd.DataFrame({"Date": date_labels, "Return": portfolio_daily_cumulative})

def get_historical_tracks_returns(chosen_tracks, available_tracks):
    """מחשב היסטוריית תשואות חודשיות לאחור משוקללת לפי מסלולים"""
    months_hebrew = {
        1: "ינואר", 2: "פברואר", 3: "מרץ", 4: "אפריל", 5: "מאי", 6: "יוני",
        7: "יולי", 8: "אוגוסט", 9: "ספטמבר", 10: "אוקטובר", 11: "נובמבר", 12: "דצמבר"
    }
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
        return [{"חודש": "חודש קודם"}]
        
    today = datetime.now()
    current_year = today.year
    current_month = today.month
    
    for i in range(1, 4):
        start_idx = -(i + 1) * 21
        end_idx = -i * 21
        target_month = current_month - i
        target_year = current_year
        while target_month <= 0:
            target_month += 12
            target_year -= 1
            
        month_label = f"{months_hebrew[target_month]} {target_year}"
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
            if track in available_tracks:
                track_components = available_tracks[track]["components"]
                weighted_track_return = 0.0
                for asset, asset_pct in track_components.items():
                    weighted_track_return += raw_index_returns.get(asset, 0.0) * (asset_pct / 100)
                month_row[track] = f"{weighted_track_return:+.2f}%"
        data_list.append(month_row)
        
    return data_list

# הגדרת בר התקדמות עליון קבוע לפי הסטטוס הנוכחי של העמוד
if st.session_state.pension_page == "page1": 
    st.progress(25, text="שלב 1 מתוך 4: פרטי החוסך ומוצר")
elif st.session_state.pension_page == "page2": 
    st.progress(50, text="שלב 2 מתוך 4: הגדרת חלוקת מסלולים משולבת")
elif st.session_state.pension_page == "analysis": 
    st.progress(75, text="שלב 3 מתוך 4: מנוע ניתוח ודוח AI")
elif st.session_state.pension_page == "projection": 
    st.progress(100, text="שלב 4 מתוך 4: סימולציית גיל פרישה וצמיחה")
st.write("---")
# =====================================================================
# מאגרי נתונים קומפקטיים ומאוזנים: פנסיה, השתלמות וגמל להשקעה
# =====================================================================
PENSION_REGISTRY = {
    "הראל פנסיה": {
        "מסלול מחקה S&P 500": {"components": {"S&P 500": 100, "TA 125": 0, "Nasdaq 100": 0, "Bonds": 0, "Cash": 0}, "default_fx": 40.0},
        "מסלול מנייתי כללי": {"components": {"S&P 500": 45, "TA 125": 25, "Nasdaq 100": 20, "Bonds": 5, "Cash": 5}, "default_fx": 35.0},
        "מסלול כללי / מאוזן": {"components": {"S&P 500": 20, "TA 125": 15, "Nasdaq 100": 10, "Bonds": 40, "Cash": 15}, "default_fx": 20.0}
    },
    "אלטשולר שחם פנסיה": {
        "מסלול מחקה מדדים": {"components": {"S&P 500": 50, "TA 125": 20, "Nasdaq 100": 30, "Bonds": 0, "Cash": 0}, "default_fx": 65.0},
        "מסלול כללי": {"components": {"S&P 500": 25, "TA 125": 15, "Nasdaq 100": 15, "Bonds": 35, "Cash": 10}, "default_fx": 30.0}
    },
    "הפניקס פנסיה": {
        "הפניקס מנייתי": {"components": {"S&P 500": 45, "TA 125": 25, "Nasdaq 100": 20, "Bonds": 5, "Cash": 5}, "default_fx": 40.0},
        "הפניקס מחקה S&P 500": {"components": {"S&P 500": 100, "TA 125": 0, "Nasdaq 100": 0, "Bonds": 0, "Cash": 0}, "default_fx": 40.0}
    }
}

TRAINING_FUND_REGISTRY = {
    "הראל השתלמות": {
        "הראל השתלמות מניות": {"components": {"S&P 500": 50, "TA 125": 20, "Nasdaq 100": 20, "Bonds": 5, "Cash": 5}, "default_fx": 45.0},
        "הראל השתלמות מחקה S&P 500": {"components": {"S&P 500": 100, "TA 125": 0, "Nasdaq 100": 0, "Bonds": 0, "Cash": 0}, "default_fx": 40.0},
        "הראל השתלמות כללי": {"components": {"S&P 500": 25, "TA 125": 20, "Nasdaq 100": 10, "Bonds": 35, "Cash": 10}, "default_fx": 25.0}
    },
    "אלטשולר שחם השתלמות": {
        "אלטשולר השתלמות מניות": {"components": {"S&P 500": 55, "TA 125": 15, "Nasdaq 100": 20, "Bonds": 5, "Cash": 5}, "default_fx": 65.0},
        "אלטשולר השתלמות כללי": {"components": {"S&P 500": 28, "TA 125": 18, "Nasdaq 100": 14, "Bonds": 30, "Cash": 10}, "default_fx": 35.0}
    },
    "ילין לפידות השתלמות": {
        "ילין השתלמות מניות": {"components": {"S&P 500": 40, "TA 125": 35, "Nasdaq 100": 15, "Bonds": 5, "Cash": 5}, "default_fx": 35.0},
        "ילין מסלול השתלמות כללי": {"components": {"S&P 500": 18, "TA 125": 25, "Nasdaq 100": 7, "Bonds": 40, "Cash": 10}, "default_fx": 20.0}
    }
}

INVESTMENT_PROVIDENT_REGISTRY = {
    "אנליסט גמל להשקעה": {
        "מסלול מניות": {"components": {"S&P 500": 55, "TA 125": 20, "Nasdaq 100": 25, "Bonds": 0, "Cash": 0}, "default_fx": 55.0},
        "מסלול כללי": {"components": {"S&P 500": 30, "TA 125": 25, "Nasdaq 100": 15, "Bonds": 20, "Cash": 10}, "default_fx": 30.0},
        "מסלול עוקב מדדים - גמיש": {"components": {"S&P 500": 45, "TA 125": 15, "Nasdaq 100": 40, "Bonds": 0, "Cash": 0}, "default_fx": 60.0}
    },
    "הראל גמל להשקעה": {
        "מסלול מניות": {"components": {"S&P 500": 50, "TA 125": 20, "Nasdaq 100": 20, "Bonds": 5, "Cash": 5}, "default_fx": 45.0},
        "מסלול כללי": {"components": {"S&P 500": 25, "TA 125": 20, "Nasdaq 100": 10, "Bonds": 35, "Cash": 10}, "default_fx": 25.0}
    },
    "אלטשולר שחם גמל להשקעה": {
        "מסלול מניות": {"components": {"S&P 500": 55, "TA 125": 15, "Nasdaq 100": 20, "Bonds": 5, "Cash": 5}, "default_fx": 65.0},
        "מסלול כללי": {"components": {"S&P 500": 28, "TA 125": 18, "Nasdaq 100": 14, "Bonds": 30, "Cash": 10}, "default_fx": 35.0}
    },
    "מיטב גמל להשקעה": {
        "מסלול מניות": {"components": {"S&P 500": 50, "TA 125": 15, "Nasdaq 100": 25, "Bonds": 5, "Cash": 5}, "default_fx": 55.0},
        "מסלול כללי": {"components": {"S&P 500": 25, "TA 125": 20, "Nasdaq 100": 15, "Bonds": 30, "Cash": 10}, "default_fx": 30.0}
    },
    "מור גמל להשקעה": {
        "מסלול מניות": {"components": {"S&P 500": 45, "TA 125": 25, "Nasdaq 100": 20, "Bonds": 5, "Cash": 5}, "default_fx": 45.0},
        "מסלול עוקב מדדים": {"components": {"S&P 500": 50, "TA 125": 15, "Nasdaq 100": 35, "Bonds": 0, "Cash": 0}, "default_fx": 60.0}
    }
}

# =====================================================================
# שלב 1 - בחירת מוצר ונתוני קופה
# =====================================================================
if st.session_state.pension_page == "page1":
    st.title("שלב 1: בחירת מוצר ונתוני קופה")
    
    product_options = ["קרן פנסיה", "קרן השתלמות", "קופת גמל להשקעה"]
    saved_product = st.session_state.get("product_type", "קרן פנסיה")
    default_product_idx = product_options.index(saved_product) if saved_product in product_options else 0
    
    product_type = st.radio("בחר את סוג המוצר הפיננסי לניתוח:", product_options, index=default_product_idx, horizontal=True)
    st.session_state.product_type = product_type
    
    saved_info = st.session_state.user_info
    col1, col2 = st.columns(2)
    
    if product_type == "קרן פנסיה":
        company_list = list(PENSION_REGISTRY.keys())
    elif product_type == "קרן השתלמות":
        company_list = list(TRAINING_FUND_REGISTRY.keys())
    else:
        company_list = list(INVESTMENT_PROVIDENT_REGISTRY.keys())
        
    with col1:
        default_company_idx = company_list.index(saved_info["company"]) if "company" in saved_info and saved_info["company"] in company_list else 0
        company_name = st.selectbox("שם החברה המנהלת:", company_list, index=default_company_idx)
        
        if product_type == "קרן פנסיה":
            user_age = st.number_input("גיל המשתמש הנוכחי:", min_value=18, max_value=100, value=saved_info.get("age", 30))
            fund_start_date = None
        elif product_type == "קרן השתלמות":
            user_age = 30
            default_date = saved_info.get("start_date", datetime.now() - timedelta(days=365*3))
            fund_start_date = st.date_input("תאריך תחילת ההפקדות (פתיחת הקופה):", value=default_date)
        else:
            user_age = 30
            fund_start_date = None
            
        total_balance = st.number_input("יתרה צבורה בתחילת החודש (ש\"ח):", min_value=0, value=saved_info.get("balance", 100000), step=10000)

    with col2:
        if product_type == "קרן פנסיה":
            st.markdown("**נתוני שכר והפקדות חודשיות**")
            current_salary = st.number_input("משכורת חודשית ברוטו נוכחית (בש\"ח):", min_value=0, value=saved_info.get("current_salary", 15000), step=1000)
            target_salary = st.number_input("משכורת חודשית משוערת לקראת הפרישה (בש\"ח):", min_value=0, value=saved_info.get("target_salary", 22000), step=1000)
            suggested_deposit = int(current_salary * 0.185)
            monthly_deposit = st.number_input("סך הפקדה חודשית נוכחית לקופה (ברוטו בש\"ח):", min_value=0, value=saved_info.get("monthly_deposit", suggested_deposit), step=100)
        elif product_type == "קרן השתלמות":
            st.markdown("**נתוני הפקדות לקרן השתלמות**")
            monthly_deposit = st.number_input("סך הפקדה חודשית משולבת לקופה (עובד + מעביד בש\"ח):", min_value=0, value=saved_info.get("monthly_deposit", 1500), step=100)
            current_salary = 0.0
            target_salary = 0.0
        else:
            monthly_deposit = 0.0
            current_salary = 0.0
            target_salary = 0.0
            st.info("💡 בקופת גמל להשקעה הניתוח מבוסס על היתרה הקיימת וביצועי השוק החודשיים בלבד.")

        st.markdown("**דמי ניהול נוכחיים**")
        sub_c1, sub_c2 = st.columns(2)
        
        if product_type == "קופת גמל להשקעה":
            default_fee_dep = 0.0
            default_fee_bal = 0.65
        else:
            default_fee_dep = 0.0 if product_type == "קרן השתלמות" else 1.5
            default_fee_bal = 0.50 if product_type == "קרן השתלמות" else 0.22
            
        fee_from_deposit = sub_c1.number_input("דמי ניהול מהפקדה (%):", min_value=0.0, max_value=6.0, value=saved_info.get("fee_deposit", default_fee_dep), step=0.1, disabled=(product_type == "קופת גמל להשקעה"))
        fee_from_balance = sub_c2.number_input("דמי ניהול שנתיים מצבירה (%):", min_value=0.0, max_value=2.0, value=saved_info.get("fee_balance", default_fee_bal), step=0.01)

    st.write("---")
    if st.button("המשך לבחירת מסלולי ההשקעה", type="primary"):
        st.session_state.user_info = {
            "company": company_name, "age": user_age, "balance": total_balance,
            "current_salary": current_salary, "target_salary": target_salary,
            "monthly_deposit": monthly_deposit, "fee_deposit": fee_from_deposit, "fee_balance": fee_from_balance,
            "start_date": fund_start_date
        }
        navigate_to("page2")
# =====================================================================
# שלב 2 - הגדרת חלוקת מסלולים משולבת
# =====================================================================
elif st.session_state.pension_page == "page2":
    selected_company = st.session_state.user_info["company"]
    product_type = st.session_state.product_type
    
    st.title("שלב 2: הגדרת חלוקת מסלולים משולבת")
    st.write(f"סוג קופה: **{product_type}** | חברה מנהלת: **{selected_company}**")
    
    if product_type == "קרן פנסיה":
        available_tracks = PENSION_REGISTRY[selected_company]
    elif product_type == "קרן השתלמות":
        available_tracks = TRAINING_FUND_REGISTRY[selected_company]
    else:
        available_tracks = INVESTMENT_PROVIDENT_REGISTRY[selected_company]
        
    chosen_tracks = st.multiselect(
        "בחר את מסלולי ההשקעה הפעילים בקופה שלך:", 
        list(available_tracks.keys()), 
        default=list(available_tracks.keys())[:1] if list(available_tracks.keys()) else None
    )
    
    track_split_data = {}
    total_split_pct = 0
    weighted_fx_exposure = 0.0
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("קביעת משקלים למסלולים")
        if not chosen_tracks: 
            st.warning("אנא בחר לפחות מסלול אחד.")
        else:
            for track in chosen_tracks:
                default_w = max(0, 100 // len(chosen_tracks)) if len(chosen_tracks) > 1 else 100
                weight_input = st.number_input(f"משקל מסלול '{track}' בתיק (%):", min_value=0, max_value=100, value=default_w, step=5)
                track_split_data[track] = weight_input
                total_split_pct += weight_input
                weighted_fx_exposure += available_tracks[track]["default_fx"] * (weight_input / 100)
                
            st.write("---")
            if total_split_pct == 100: 
                st.success(f"חלוקה תקינה המגיעה ל-{total_split_pct}%!")
                st.session_state.institutional_fx_exposure = weighted_fx_exposure
                st.info(f"חשיפת מט\"ח משוקללת משוערת לחברה זו: {weighted_fx_exposure:.1f}%")
            else: 
                st.error(f"❌ סך משקלי המסלול עומד על {total_split_pct}%. עליך להגיע ל-100% בדיוק.")
                
    aggregated_mix = {"S&P 500": 0.0, "TA 125": 0.0, "Nasdaq 100": 0.0, "Bonds": 0.0, "Cash": 0.0}
    if total_split_pct == 100 and chosen_tracks:
        for track, track_weight in track_split_data.items():
            track_components = available_tracks[track]["components"]
            for asset, asset_pct in track_components.items():
                aggregated_mix[asset] += asset_pct * (track_weight / 100)
                
    with col2:
        st.subheader("פילוח נכסים משוקלל סופי")
        if total_split_pct == 100:
            mix_df = pd.DataFrame({"השקעה אפיק": list(aggregated_mix.keys()), "אחוז": list(aggregated_mix.values())})
            fig = px.pie(mix_df, values="אחוז", names="השקעה אפיק", hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("הגרף יוצג לאחר איזון המשקלים ל-100%.")
            
    st.write("---")
    c_back, c_next = st.columns(2)
    if c_back.button("חזור לשלב הקודם"): 
        navigate_to("page1")
    if c_next.button("בצע ניתוח ביצועים ודוח AI! ", type="primary", disabled=(total_split_pct != 100)):
        st.session_state.user_info["fund"] = " | ".join([f"{t} ({w}%)" for t, w in track_split_data.items()])
        st.session_state.user_info["chosen_tracks_list"] = chosen_tracks
        st.session_state.mix_data = aggregated_mix
        navigate_to("analysis")
# =====================================================================
# שלב 3 - מנוע ניתוח ביצועי קופה ודוח AI בזמן אמת
# =====================================================================
elif st.session_state.pension_page == "analysis":
    if not st.session_state.mix_data: 
        navigate_to("page1")
        
    product_type = st.session_state.product_type
    st.title(f"מנוע ניתוח ביצועי {product_type} ודוח AI")
    
    u = st.session_state.user_info
    st.subheader(f"אומדן ביצועים עבור: {u['fund']} ({u['company']})")
    
    if st.button("חזור לעריכת תמהיל התיק"): 
        navigate_to("page2")
        
    st.write("---")
    
    with st.spinner("מחשב נתונים בזמן אמת..."): 
        try:
            benchmark_returns = get_benchmark_returns()
            total_gross_return = sum(benchmark_returns.get(asset, 0.0) * (weight / 100) for asset, weight in st.session_state.mix_data.items())
            
            total_monthly_fees_nis = (u["monthly_deposit"] * (u["fee_deposit"] / 100)) + (u["balance"] * ((u["fee_balance"] / 100) / 12))
            
            total_net_return = total_gross_return - ((total_monthly_fees_nis / u["balance"]) * 100 if u["balance"] > 0 else 0.0)
            money_change_net = u["balance"] * (total_net_return / 100)
        except Exception as calc_error:
            st.error(f"שגיאה בחישוב הנתונים: {str(calc_error)}")
            total_net_return, total_monthly_fees_nis, money_change_net = 0.0, 0.0, 0.0
            
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("תשואה מוערכת (נטו החודש)", f"{total_net_return:+.2f}%")
    m2.metric("דמי ניהול (כסף כללי החודש)", f"{total_monthly_fees_nis:,.2f} ₪")
    m3.metric("שינוי כספי מוערך (נטו)", f"{money_change_net:+,.2f} ₪")
    m4.metric("שווי תיק מעודכן", f"{u['balance'] + money_change_net:,.2f} ₪")
    
    st.write("---")
    st.write("### הגרף היומי המצטבר מתחילת החודש ועד היום (%)")
    
    with st.spinner("מייצר גרף ביצועים יומי..."): 
        daily_chart_df = get_daily_returns_chart_data(st.session_state.mix_data, st.session_state.institutional_fx_exposure)
        if not daily_chart_df.empty:
            fig_daily_perf = px.line(
                daily_chart_df, x="Date", y="Return", 
                title="Portfolio Cumulative Performance (Month-to-Date)", markers=True
            )
            fig_daily_perf.update_layout(
                yaxis_title="Cumulative Return (%)", xaxis_title="Date (MM-DD)",
                yaxis_tickformat="+.2f%"
            )
            st.plotly_chart(fig_daily_perf, use_container_width=True)
        else:
            st.info("נתוני מסחר יומיים אינם זמינים כעת בגלל סוף שבוע או בעיית תקשורת.")
    st.write("### היסטוריית תשואות משוקללת של מסלולי הקופה שבחרת")
    try:
        if product_type == "קרן פנסיה":
            available_registry = PENSION_REGISTRY[u["company"]]
        elif product_type == "קרן השתלמות":
            available_registry = TRAINING_FUND_REGISTRY[u["company"]]
        else:
            available_registry = INVESTMENT_PROVIDENT_REGISTRY[u["company"]]
        
        history_data = get_historical_tracks_returns(
            u.get("chosen_tracks_list", list(available_registry.keys())), 
            available_registry
        )
        st.dataframe(pd.DataFrame(history_data), use_container_width=True)
    except Exception as hist_error:
        st.warning("⚠️ לא ניתן היה לטעון את נתוני ההיסטוריה מ-Yahoo Finance.")
        history_data = []
        
    st.write("---")
    st.subheader("🤖 דוח ניתוח והמלצות אסטרטגיות מה-AI")
    
    if not api_key: 
        st.info("🔑 אנא הזן מפתח API בתפריט הצד לקבלת דוח AI.")
    else:
        ai_placeholder = st.empty()
        ai_placeholder.info("⏳ מנוע ה-AI מנתח את נתוני הקופה וההיסטוריה... אנא המתן")
        
        user_context = (
            f"Product: {product_type}, Company: {u['company']}, Split Tracks: {u['fund']}, "
            f"Balance: {u['balance']} NIS, Combined Net Return: {total_net_return:.2f}%, History: {history_data}, "
            f"Estimated Institutional FX Exposure: {st.session_state.institutional_fx_exposure}%"
        )
        
        system_instruction = (
            f"אתה מומחה פיננסי בכיר ומנהל השקעות ישראלי. נתח את ביצועי החודש וההיסטוריה של מוצר החיסכון: {product_type}. "
            f"התייחס ספציפית לתמהיל הנכסים, דמי הניהול שנבחרו, והשפעת חשיפת המט''ח/הגידור השקלי שחושבה (ILS=X). "
            f"ספק דוח מקצועי, חד, ומנומק היטב המיועד לחוסך. הדוח חייב להיכתב בשפה העברית בלבד ובמבנה קריא עם בולטים."
        )
        
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model='gemini-2.5-flash', 
                contents=user_context, 
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction, 
                    temperature=0.2
                )
            )
            ai_placeholder.markdown(response.text)
        except Exception as e:
            ai_placeholder.empty()
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                st.warning("⚠️ הגעת למגבלת המכסה החינמית של מפתח ה-API של גוגל לדקה זו. ניתן להמשיך ישירות לסימולציה למטה.")
            else: 
                st.error(f"❌ שגיאה בהפקת הדוח: {str(e)}")
                
    st.write("---")
    if product_type == "קרן פנסיה":
        btn_label = "המשך לסימולציית גיל פרישה (שנת 65)"
    elif product_type == "קרן השתלמות":
        btn_label = "המשך לסימולציית נזילות הון מותאמת תאריך"
    else:
        btn_label = "המשך לסימולציית צמיחת הון ארוכת טווח (10 שנים)"
        
    if st.button(btn_label, type="primary"): 
        navigate_to("projection")
# =====================================================================
# שלב 4 - סימולציית הון ותחזית צמיחה לטווח ארוך
# =====================================================================
elif st.session_state.pension_page == "projection":
    product_type = st.session_state.product_type
    st.title("שלב 4: סימולציית הון ותחזית צמיחה לטווח ארוך")
    
    if st.button("↩️ חזור לדוח הניתוח"):
        navigate_to("analysis")
        
    u = st.session_state.user_info
    
    if product_type == "קרן פנסיה":
        years_to_simulate = max(1, 65 - u["age"])
        target_title = "🎯 תוצאות שיערוך אקטוארי מנוכה מס (נטו בפרישה)"
    elif product_type == "קרן השתלמות":
        start_date = u.get("start_date")
        if start_date:
            if isinstance(start_date, str):
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            today_date = datetime.now().date()
            months_passed = (today_date.year - start_date.year) * 12 + (today_date.month - start_date.month)
            months_to_liquidity = max(0, 72 - months_passed)
            years_to_simulate = round(months_to_liquidity / 12, 2)
        else:
            years_to_simulate = 6
            
        if years_to_simulate > 0:
            st.success(f"📅 הקופה נפתחה ב-{start_date.strftime('%d/%m/%Y') if start_date else 'עבר'}. נותרו כ-{months_to_liquidity} חודשים (כ-{years_to_simulate} שנים) לנזילות מלאה פטורה ממס.")
        else:
            st.success("🎉 הקופה ותיקה ונזילה לחלוטין! (פתחת אותה לפני יותר מ-6 שנים). הסימולציה מציגה צפי צמיחה ל-6 השנים הבאות.")
            years_to_simulate = 6
        target_title = "🎯 תוצאות שיערוך הון פטור ממס בנקודת הנזילות המלאה"
    else:
        years_to_simulate = 10
        target_title = f"🎯 תחזית צמיחת הון צפויה ל-{int(years_to_simulate)} השנים הבאות"

    if years_to_simulate <= 0: 
        st.warning("⚠️ היעד הושג. נתוני הסימולציה אינם יכולים לרוץ לאחור.")
    else:
        if product_type == "קרן פנסיה" and u["target_salary"] > u["current_salary"]:
            salary_growth_rate = (u["target_salary"] / u["current_salary"]) ** (1 / years_to_simulate) - 1
        else:
            salary_growth_rate = 0.0
            
        if product_type == "קרן פנסיה" and salary_growth_rate > 0:
            st.info(f"📈 מודל הסימולציה מניח קידום שכר שנתי ממוצע של {salary_growth_rate*100:.2f}%")
            
        mix = st.session_state.mix_data
        calculated_longterm_return = (
            (mix.get("S&P 500", 0.0) * 8.5) + 
            (mix.get("Nasdaq 100", 0.0) * 9.5) + 
            (mix.get("TA 125", 0.0) * 7.0) + 
            (mix.get("Bonds", 0.0) * 4.0) + 
            (mix.get("Cash", 0.0) * 2.5)
        ) / 100
        
        st.subheader("📊 בחירת תרחיש תשואה היסטורי לסימולציה")
        scenarios_options = [
            f"תרחיש 1 - תשואה משוקללת נכסים מותאמת ({calculated_longterm_return:.2f}%)",
            "תרחיש 2 - תשואה קבועה גבוהה (7.50%)",
            "תרחיש 3 - תשואה קבועה שמרנית (4.50%)"
        ]
        scenario = st.selectbox("בחר תרחיש תשואה מועדף לתחזית ארוכת הטווח:", scenarios_options)
        
        if "תרחיש 1" in scenario: 
            chosen_rate = float(calculated_longterm_return)
        elif "תרחיש 2" in scenario: 
            chosen_rate = 7.50
        else: 
            chosen_rate = 4.50
            
        annual_return_input = st.number_input(
            "שיעור התשואה השנתית הפעיל בסימולציה (%):", 
            min_value=1.0, max_value=15.0, value=chosen_rate, step=0.1
        )
        
        if product_type == "קרן פנסיה":
            conversion_coefficient = st.number_input("מקדם המרה צפוי לקצבה (ברירת מחדל 200):", min_value=150, max_value=250, value=200)
            
        balance = u["balance"]
        fee_deposit_rate = u["fee_deposit"] / 100
        fee_balance_rate = u["fee_balance"] / 100
        return_rate = annual_return_input / 100
        
        age_axis = [u["age"] if product_type == "קרן פנסיה" else 0]
        balance_axis = [round(balance)]
        salary_axis = [round(u["current_salary"])]
        active_salary = u["current_salary"]
        
        loop_years = int(years_to_simulate + 0.99)
        for year in range(1, loop_years + 1):
            active_salary *= (1 + salary_growth_rate)
            annual_deposit = u["monthly_deposit"] * 12
            net_annual_deposit = annual_deposit * (1 - fee_deposit_rate)
            
            balance = (balance * (1 + return_rate)) + net_annual_deposit
            balance *= (1 - fee_balance_rate)
            
            if product_type == "קרן פנסיה":
                age_axis.append(u["age"] + year)
            else:
                age_axis.append(year)
                
            balance_axis.append(round(balance))
            salary_axis.append(round(active_salary))
            
        final_balance = balance_axis[-1]
        st.write("---")
        st.subheader(target_title)
        
        if product_type == "קרן פנסיה":
            gross_pension = final_balance / conversion_coefficient
            tax = 0.0
            if gross_pension <= 7010: 
                tax = gross_pension * 0.10
            else:
                tax += 7010 * 0.10
                if gross_pension <= 10060: tax += (gross_pension - 7010) * 0.14
                else:
                    tax += (10060 - 7010) * 0.14
                    if gross_pension <= 16150: tax += (gross_pension - 10060) * 0.20
                    else:
                        tax += (16150 - 10060) * 0.20
                        if gross_pension <= 22440: tax += (gross_pension - 16150) * 0.31
                        else:
                            tax += (22440 - 16150) * 0.31
                            if gross_pension <= 45320: tax += (gross_pension - 22440) * 0.35
                            else:
                                tax += (45320 - 22440) * 0.35
                                tax += (gross_pension - 45320) * 0.47
            
            tax_credit = 554.4  
            final_tax_deduction = max(0.0, tax - tax_credit)
            net_pension = gross_pension - final_tax_deduction
            replacement_rate_net = (net_pension / salary_axis[-1]) * 100 if salary_axis[-1] > 0 else 0.0
            
            p1, p2, p3, p4 = st.columns(4)
            p1.metric("משכורת פרישה משוערת", f"{salary_axis[-1]:,} ₪")
            p2.metric("סכום צבור בפרישה", f"{final_balance:,.0f} ₪")
            p3.metric("קצבה חודשית (ברוטו)", f"{gross_pension:,.0f} ₪", f"מס משוער: {final_tax_deduction:,.0f} ₪")
            p4.metric("קצבת נטו בבנק", f"{net_pension:,.0f} ₪/לחודש", f"אחוז תחלופה נטו: {replacement_rate_net:.1f}%")
        else:
            p1, p2, p3 = st.columns(3)
            p1.metric("סכום התחלתי בקופה", f"{u['balance']:,} ₪")
            p2.metric("סכום סופי צבור משוער", f"{final_balance:,.0f} ₪")
            
            total_net_profit = final_balance - u['balance'] - (u['monthly_deposit'] * 12 * years_to_simulate)
            profit_label = "רווח נקי משוער פטור ממס" if product_type == "קרן השתלמות" else "צמיחת הון נטו משוערת"
            p3.metric(profit_label, f"{max(0.0, total_net_profit):+,.0f} ₪")
            
        st.write("---")
        st.write("### 📈 גרף התפתחות ההון לאורך השנים בסימולציה")
        
        chart_df = pd.DataFrame({"Timeline": age_axis, "balance": balance_axis})
        x_label = "גיל המשתמש" if product_type == "קרן פנסיה" else "שנים מהיום"
        
        fig_line = px.line(chart_df, x="Timeline", y="balance", title=f"תחזית גידול צבור עבור {product_type}", markers=True)
        fig_line.update_layout(yaxis_tickformat=",.0f", yaxis_title="שווי תיק (₪)", xaxis_title=x_label)
        st.plotly_chart(fig_line, use_container_width=True)
