import streamlit as st
import pandas as pd
from datetime import date
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker

# --- 1. PAGE SETUP & MOBILE STYLING ---
st.set_page_config(page_title="Family Health & Fitness", page_icon="🏋️‍♂️", layout="wide")

st.markdown("""
    <style>
    .main-header { font-weight: 700; color: #1E293B; margin-bottom: 0px; }
    .sub-text { color: #64748B; font-size: 0.95rem; }
    [data-testid="stMetricValue"] { font-weight: 700; color: #0F172A; }
    </style>
""", unsafe_allow_html=True)

# --- 2. BACKEND DATABASE CONNECTION WITH AUTOMATIC FALLBACK ---
SUPABASE_URL = "postgresql://postgres.vslncvltydnzooedllao:Kdv_Dav%4012901@aws-0-ap-south-1.pooler.supabase.com:6543/postgres"
LOCAL_URL = "sqlite:///./health_tracker.db"

@st.cache_resource
def init_db_engine():
    """Attempts cloud connection; falls back to local SQLite if internet/DNS fails."""
    try:
        engine = create_engine(SUPABASE_URL, pool_pre_ping=True, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            pass  # Test connection
        return engine, "Supabase Cloud"
    except Exception:
        engine = create_engine(LOCAL_URL, connect_args={"check_same_thread": False})
        return engine, "Local File (Offline)"

engine, db_source = init_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- 3. DATABASE SCHEMA (SQLAlchemy Models) ---
class ProfileDB(Base):
    __tablename__ = "profiles"
    name = Column(String, primary_key=True, index=True)
    gender = Column(String)
    dob = Column(Date)
    height = Column(Float)
    current_weight = Column(Float)
    target_weight = Column(Float)
    diet = Column(String)

class VitalLogDB(Base):
    __tablename__ = "vitals"
    id = Column(Integer, primary_key=True, autoincrement=True)
    member = Column(String, ForeignKey("profiles.name"))
    log_date = Column(Date)
    systolic = Column(Integer)
    diastolic = Column(Integer)
    blood_sugar = Column(Float)
    timing = Column(String)

class WeightLogDB(Base):
    __tablename__ = "weight_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    member = Column(String, ForeignKey("profiles.name"))
    log_date = Column(Date)
    weight = Column(Float)
    steps = Column(Integer)

class HabitLogDB(Base):
    __tablename__ = "habit_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    member = Column(String, ForeignKey("profiles.name"))
    log_date = Column(Date)
    sleep_hrs = Column(Float)
    water_l = Column(Float)
    protein_g = Column(Float)

# Create missing tables safely
Base.metadata.create_all(bind=engine)

# --- 4. HELPER FUNCTIONS ---
def get_db():
    return SessionLocal()

def calculate_age(dob):
    if not dob:
        return "--"
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

AVATAR_URL = "https://cdn-icons-png.flaticon.com/512/3135/3135715.png"
DEFAULT_MEMBERS = ["Kush", "Dharmesh", "Kinaree", "Daksha", "Dhaval", "Pallavi", "Charvi", "Parhi"]

# --- 5. SESSION STATE ---
if "active_member" not in st.session_state:
    st.session_state.active_member = None

db = get_db()

# --- SCREEN A: PROFILE SELECTOR ---
if st.session_state.active_member is None:
    st.markdown("<h1 class='main-header'>🏋️‍♂️ Family Health & Fitness</h1>", unsafe_allow_html=True)
    st.markdown(f"<p class='sub-text'>Select your profile. <i>(Database Mode: {db_source})</i></p>", unsafe_allow_html=True)
    st.divider()

    # Load profiles from database
    existing_profiles = {p.name: p for p in db.query(ProfileDB).all()}
    all_names = sorted(list(set(DEFAULT_MEMBERS + list(existing_profiles.keys()))))
    
    # Grid display
    num_columns = 4
    for i in range(0, len(all_names), num_columns):
        cols = st.columns(num_columns)
        for idx, name in enumerate(all_names[i:i + num_columns]):
            with cols[idx]:
                with st.container(border=True):
                    prof = existing_profiles.get(name)
                    st.image(AVATAR_URL, width=65)
                    st.markdown(f"### {name}")
                    
                    if prof and prof.dob:
                        st.caption(f"Age: **{calculate_age(prof.dob)}** | **{prof.current_weight} kg**")
                    else:
                        st.caption("⚠️ Setup required")
                        
                    if st.button("Select Profile", key=f"btn_{name}", use_container_width=True):
                        st.session_state.active_member = name
                        st.rerun()

    st.divider()
    with st.expander("➕ Add New Family Member"):
        with st.form("add_member"):
            new_name = st.text_input("Member Name")
            gender_opt = st.selectbox("Biological Sex", ["Male", "Female"])
            if st.form_submit_button("Add Member") and new_name:
                if not db.query(ProfileDB).filter(ProfileDB.name == new_name).first():
                    new_p = ProfileDB(name=new_name, gender=gender_opt)
                    db.add(new_p)
                    db.commit()
                st.session_state.active_member = new_name
                st.rerun()

# --- SCREEN B: ACTIVE MEMBER DASHBOARD ---
else:
    member_name = st.session_state.active_member
    profile = db.query(ProfileDB).filter(ProfileDB.name == member_name).first()

    # Header Controls
    col_t, col_b = st.columns([5, 1])
    col_t.title(f"📱 {member_name}'s Health Dashboard")
    if col_b.button("⬅️ Switch Member"):
        st.session_state.active_member = None
        st.rerun()

    # --- DELETE PROFILE / ACCOUNT MANAGEMENT ---
    with st.expander("⚙️ Manage Profile / Delete Account"):
        st.warning(f"⚠️ Danger Zone: Deleting **{member_name}** will permanently erase all their logged vitals, weight, and habit records.")
        
        confirm = st.checkbox(f"I understand that deleting {member_name}'s profile is permanent and cannot be undone.")
        
        if st.button(f"🗑️ Delete {member_name}'s Profile", type="primary", disabled=not confirm):
            # 1. Delete all associated logs first
            db.query(VitalLogDB).filter(VitalLogDB.member == member_name).delete()
            db.query(WeightLogDB).filter(WeightLogDB.member == member_name).delete()
            db.query(HabitLogDB).filter(HabitLogDB.member == member_name).delete()
            
            # 2. Delete the profile record itself
            if profile:
                db.delete(profile)
                
            db.commit()
            
            # 3. Reset session state back to selector
            st.session_state.active_member = None
            st.success(f"Profile for {member_name} has been completely deleted.")
            st.rerun()

    st.divider()

    # ONBOARDING / PROFILE SETUP FORM
    if not profile or not profile.dob:
        st.info("👋 Welcome! Please complete your initial profile setup.")
        with st.form("setup_form"):
            dob = st.date_input("Date of Birth", date(1995, 1, 1))
            height = st.number_input("Height (cm)", value=170.0)
            weight = st.number_input("Current Weight (kg)", value=70.0)
            target = st.number_input("Target Weight (kg)", value=65.0)
            gender = st.selectbox("Sex", ["Male", "Female"])
            diet = st.selectbox("Diet Preference", ["Vegetarian", "Non-Vegetarian", "Vegan", "Eggetarian"])
            
            if st.form_submit_button("Save Setup"):
                if not profile:
                    profile = ProfileDB(name=member_name)
                    db.add(profile)
                profile.dob = dob
                profile.height = height
                profile.current_weight = weight
                profile.target_weight = target
                profile.gender = gender
                profile.diet = diet
                db.commit()
                st.success("Profile saved!")
                st.rerun()
    else:
        tabs = st.tabs(["📊 Overview & Goals", "🫀 Vitals", "⚖️ Weight & Steps", "💧 Daily Habits"])

        # TAB 1: METRICS & GOALS SNAPSHOT
        with tabs[0]:
            st.subheader("🎯 Target Weight & Progress")
            
            latest_vital = db.query(VitalLogDB).filter(VitalLogDB.member == member_name).order_by(VitalLogDB.log_date.desc()).first()
            bp_val = f"{latest_vital.systolic}/{latest_vital.diastolic}" if latest_vital else "No records"

            diff = round(profile.current_weight - profile.target_weight, 1)

            with st.container(border=True):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Current Weight", f"{profile.current_weight} kg")
                c2.metric("Target Weight", f"{profile.target_weight} kg")
                
                if diff > 0:
                    c3.metric("Weight Left to Lose", f"{abs(diff)} kg", delta=f"-{abs(diff)} kg", delta_color="inverse")
                elif diff < 0:
                    c3.metric("Weight Left to Gain", f"{abs(diff)} kg", delta=f"+{abs(diff)} kg")
                else:
                    c3.metric("Goal Status", "Target Achieved! 🎉")
                
                c4.metric("Latest BP", bp_val)

        # TAB 2: VITALS WITH DATE SEARCH
        with tabs[1]:
            st.subheader("🫀 Log Vitals")
            with st.form("vitals_form"):
                cv1, cv2, cv3, cv4 = st.columns(4)
                v_date = cv1.date_input("Log Date", date.today())
                sys_bp = cv2.number_input("Systolic BP", value=120)
                dia_bp = cv3.number_input("Diastolic BP", value=80)
                sugar = cv4.number_input("Blood Sugar (mg/dL)", value=95.0)
                timing = st.radio("Context", ["Fasting", "Post-Meal", "Random"], horizontal=True)

                if st.form_submit_button("Save Vitals"):
                    log = VitalLogDB(member=member_name, log_date=v_date, systolic=sys_bp, diastolic=dia_bp, blood_sugar=sugar, timing=timing)
                    db.add(log)
                    db.commit()
                    st.success("Vitals saved!")
                    st.rerun()

            st.write("")
            st.subheader("🔍 Search Vital Logs by Date")
            query = db.query(VitalLogDB).filter(VitalLogDB.member == member_name)
            search_date = st.date_input("Select Filter Date", value=None, key="v_search")
            
            if search_date:
                query = query.filter(VitalLogDB.log_date == search_date)
            
            records = query.order_by(VitalLogDB.log_date.desc()).all()
            if records:
                df = pd.DataFrame([{"Date": r.log_date, "BP": f"{r.systolic}/{r.diastolic}", "Sugar": r.blood_sugar, "Timing": r.timing} for r in records])
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No vital logs found.")

        # TAB 3: WEIGHT & STEPS
        with tabs[2]:
            st.subheader("⚖️ Log Weight & Step Count")
            with st.form("weight_form"):
                cw1, cw2, cw3 = st.columns(3)
                w_date = cw1.date_input("Date", date.today())
                w_val = cw2.number_input("Weight (kg)", value=float(profile.current_weight or 70.0))
                s_val = cw3.number_input("Steps Walked", value=5000)

                if st.form_submit_button("Save Entry"):
                    log = WeightLogDB(member=member_name, log_date=w_date, weight=w_val, steps=s_val)
                    db.add(log)
                    profile.current_weight = w_val
                    db.commit()
                    st.success("Weight log updated!")
                    st.rerun()

            st.write("")
            st.subheader("🔍 Search Weight Logs by Date")
            q_ws = db.query(WeightLogDB).filter(WeightLogDB.member == member_name)
            s_ws_date = st.date_input("Select Filter Date", value=None, key="ws_search")
            if s_ws_date:
                q_ws = q_ws.filter(WeightLogDB.log_date == s_ws_date)
            
            ws_records = q_ws.order_by(WeightLogDB.log_date.desc()).all()
            if ws_records:
                df_ws = pd.DataFrame([{"Date": r.log_date, "Weight (kg)": r.weight, "Steps": r.steps} for r in ws_records])
                st.dataframe(df_ws, use_container_width=True, hide_index=True)

        # TAB 4: DAILY HABITS
        with tabs[3]:
            st.subheader("💧 Log Daily Habits")
            with st.form("habit_form"):
                ch1, ch2, ch3, ch4 = st.columns(4)
                h_date = ch1.date_input("Date", date.today())
                sleep = ch2.number_input("Sleep (hrs)", value=7.5)
                water = ch3.number_input("Water Intake (L)", value=2.5)
                prot = ch4.number_input("Protein Intake (g)", value=60)

                if st.form_submit_button("Save Habits"):
                    log = HabitLogDB(member=member_name, log_date=h_date, sleep_hrs=sleep, water_l=water, protein_g=prot)
                    db.add(log)
                    db.commit()
                    st.success("Habits logged successfully!")
                    st.rerun()

            st.write("")
            st.subheader("🔍 Search Habit Logs by Date")
            q_h = db.query(HabitLogDB).filter(HabitLogDB.member == member_name)
            s_h_date = st.date_input("Select Filter Date", value=None, key="h_search")
            if s_h_date:
                q_h = q_h.filter(HabitLogDB.log_date == s_h_date)
                
            h_records = q_h.order_by(HabitLogDB.log_date.desc()).all()
            if h_records:
                df_h = pd.DataFrame([{"Date": r.log_date, "Sleep (hrs)": r.sleep_hrs, "Water (L)": r.water_l, "Protein (g)": r.protein_g} for r in h_records])
                st.dataframe(df_h, use_container_width=True, hide_index=True)

db.close()
