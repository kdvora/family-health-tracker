import streamlit as st
import pandas as pd
from datetime import date
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, ForeignKey, inspect, text
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
    pin = Column(String)  # 4-digit security PIN
    avatar_url = Column(String, nullable=True)  # Profile picture URL
    gender = Column(String, nullable=True)
    dob = Column(Date, nullable=True)
    height = Column(Float, nullable=True)
    current_weight = Column(Float, nullable=True)
    target_weight = Column(Float, nullable=True)
    diet = Column(String, nullable=True)

class VitalLogDB(Base):
    __tablename__ = "vitals"
    id = Column(Integer, primary_key=True, autoincrement=True)
    member = Column(String, ForeignKey("profiles.name"))
    log_date = Column(Date)
    systolic = Column(Integer, nullable=True)
    diastolic = Column(Integer, nullable=True)
    blood_sugar = Column(Float, nullable=True)
    timing = Column(String, nullable=True)

class WeightLogDB(Base):
    __tablename__ = "weight_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    member = Column(String, ForeignKey("profiles.name"))
    log_date = Column(Date)
    weight = Column(Float, nullable=True)
    steps = Column(Integer, nullable=True)

class HabitLogDB(Base):
    __tablename__ = "habit_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    member = Column(String, ForeignKey("profiles.name"))
    log_date = Column(Date)
    sleep_hrs = Column(Float, nullable=True)
    water_l = Column(Float, nullable=True)
    protein_g = Column(Float, nullable=True)

# Create missing tables safely
Base.metadata.create_all(bind=engine)

# --- AUTOMATIC SCHEMA MIGRATION ---
inspector = inspect(engine)
if "profiles" in inspector.get_table_names():
    existing_columns = [col["name"] for col in inspector.get_columns("profiles")]
    if "pin" not in existing_columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE profiles ADD COLUMN pin VARCHAR;"))
    if "avatar_url" not in existing_columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE profiles ADD COLUMN avatar_url VARCHAR;"))

# --- 4. HELPER FUNCTIONS ---
def get_db():
    return SessionLocal()

def calculate_age(dob):
    if not dob:
        return "--"
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

DEFAULT_AVATAR = "https://cdn-icons-png.flaticon.com/512/3135/3135715.png"
DEFAULT_MEMBERS = ["Kush", "Dharmesh", "Kinaree", "Daksha", "Dhaval", "Pallavi", "Charvi", "Prahi"]

# Date boundaries for birthday selection
MIN_DOB = date(1900, 1, 1)
MAX_DOB = date.today()

# --- 5. SESSION STATE ---
if "active_member" not in st.session_state:
    st.session_state.active_member = None
if "selected_member_auth" not in st.session_state:
    st.session_state.selected_member_auth = None

db = get_db()

# --- SCREEN A: PROFILE SELECTOR & AUTHENTICATION ---
if st.session_state.active_member is None:
    st.markdown("<h1 class='main-header'>🏋️‍♂️ Family Health & Fitness</h1>", unsafe_allow_html=True)
    st.markdown(f"<p class='sub-text'>Select your profile. <i>(Database Mode: {db_source})</i></p>", unsafe_allow_html=True)
    st.divider()

    if st.session_state.selected_member_auth:
        auth_name = st.session_state.selected_member_auth
        p_rec = db.query(ProfileDB).filter(ProfileDB.name == auth_name).first()

        st.subheader(f"🔒 Enter PIN for {auth_name}")
        
        if not p_rec or not p_rec.pin:
            st.info("No PIN set for this profile yet. Please set your 4-digit PIN.")
            with st.form("set_pin_form"):
                new_pin = st.text_input("Set 4-Digit PIN", type="password", max_chars=4)
                confirm_pin = st.text_input("Confirm 4-Digit PIN", type="password", max_chars=4)
                c1, c2 = st.columns(2)
                
                if c1.form_submit_button("Set PIN & Continue"):
                    if len(new_pin) == 4 and new_pin.isdigit():
                        if new_pin == confirm_pin:
                            if not p_rec:
                                p_rec = ProfileDB(name=auth_name, pin=new_pin)
                                db.add(p_rec)
                            else:
                                p_rec.pin = new_pin
                            db.commit()
                            st.session_state.active_member = auth_name
                            st.session_state.selected_member_auth = None
                            st.success("PIN created successfully!")
                            st.rerun()
                        else:
                            st.error("PINs do not match. Please try again.")
                    else:
                        st.error("PIN must be exactly 4 digits.")
                        
                if c2.form_submit_button("Cancel"):
                    st.session_state.selected_member_auth = None
                    st.rerun()
        else:
            with st.form("verify_pin_form"):
                entered_pin = st.text_input("Enter 4-Digit PIN", type="password", max_chars=4)
                c1, c2 = st.columns(2)
                
                if c1.form_submit_button("Unlock Profile"):
                    if entered_pin == p_rec.pin:
                        st.session_state.active_member = auth_name
                        st.session_state.selected_member_auth = None
                        st.rerun()
                    else:
                        st.error("Incorrect PIN. Please try again.")
                        
                if c2.form_submit_button("Cancel"):
                    st.session_state.selected_member_auth = None
                    st.rerun()

    else:
        existing_profiles = {p.name: p for p in db.query(ProfileDB).all()}
        all_names = sorted(list(set(DEFAULT_MEMBERS + list(existing_profiles.keys()))))
        
        num_columns = 4
        for i in range(0, len(all_names), num_columns):
            cols = st.columns(num_columns)
            for idx, name in enumerate(all_names[i:i + num_columns]):
                with cols[idx]:
                    with st.container(border=True):
                        prof = existing_profiles.get(name)
                        avatar = prof.avatar_url if (prof and prof.avatar_url) else DEFAULT_AVATAR
                        st.image(avatar, width=65)
                        st.markdown(f"### {name}")
                        
                        if prof and prof.dob:
                            st.caption(f"Age: **{calculate_age(prof.dob)}** | **{prof.current_weight or '--'} kg**")
                            st.caption("🔒 PIN Protected")
                        else:
                            st.caption("⚠️ Setup required")
                            
                        if st.button("Select Profile", key=f"btn_{name}", use_container_width=True):
                            st.session_state.selected_member_auth = name
                            st.rerun()

        st.divider()
        with st.expander("➕ Add New Family Member"):
            with st.form("add_member"):
                new_name = st.text_input("Member Name", value="")
                gender_opt = st.selectbox("Biological Sex (Optional)", ["Male", "Female"], index=None, placeholder="Select Sex...")
                new_avatar = st.text_input("Profile Image URL (Optional)", value="", placeholder="https://example.com/photo.png")
                new_user_pin = st.text_input("Set 4-Digit Security PIN", type="password", max_chars=4)
                
                if st.form_submit_button("Add Member"):
                    if new_name and len(new_user_pin) == 4 and new_user_pin.isdigit():
                        if not db.query(ProfileDB).filter(ProfileDB.name == new_name).first():
                            new_p = ProfileDB(name=new_name, gender=gender_opt, pin=new_user_pin, avatar_url=new_avatar or DEFAULT_AVATAR)
                            db.add(new_p)
                            db.commit()
                        st.session_state.active_member = new_name
                        st.rerun()
                    else:
                        st.error("Please provide a name and a 4-digit numeric PIN.")

# --- SCREEN B: ACTIVE MEMBER DASHBOARD ---
else:
    member_name = st.session_state.active_member
    profile = db.query(ProfileDB).filter(ProfileDB.name == member_name).first()

    col_t, col_b = st.columns([5, 1])
    current_avatar = profile.avatar_url if (profile and profile.avatar_url) else DEFAULT_AVATAR
    col_t.image(current_avatar, width=50)
    col_t.title(f"📱 {member_name}'s Health Dashboard")
    if col_b.button("🔒 Switch / Lock Member"):
        st.session_state.active_member = None
        st.rerun()

    # --- EDIT PROFILE & SECURITY SETTINGS ---
    with st.expander("⚙️ Edit Profile Details & Security / Delete Account"):
        st.markdown("#### ✏️ Edit Profile Details & Picture")
        with st.form("edit_profile_form"):
            initial_dob = profile.dob if (profile and profile.dob) else date(2000, 1, 1)
            e_dob = st.date_input("Birthday / Date of Birth", value=initial_dob, min_value=MIN_DOB, max_value=MAX_DOB)
            e_height = st.number_input("Height (cm)", value=profile.height if (profile and profile.height) else None, placeholder="e.g. 170.0")
            e_cur_weight = st.number_input("Current Weight (kg)", value=profile.current_weight if (profile and profile.current_weight) else None, placeholder="e.g. 70.0")
            e_target_weight = st.number_input("Target Weight (kg)", value=profile.target_weight if (profile and profile.target_weight) else None, placeholder="e.g. 65.0")
            
            sex_index = ["Male", "Female"].index(profile.gender) if (profile and profile.gender in ["Male", "Female"]) else None
            e_gender = st.selectbox("Biological Sex", ["Male", "Female"], index=sex_index, placeholder="Select Sex...")
            
            diet_options = ["Vegetarian", "Non-Vegetarian", "Vegan", "Eggetarian"]
            diet_index = diet_options.index(profile.diet) if (profile and profile.diet in diet_options) else None
            e_diet = st.selectbox("Diet Preference", diet_options, index=diet_index, placeholder="Select Diet...")
            
            st.markdown("##### 🖼️ Profile Picture")
            e_avatar_url = st.text_input("Custom Image URL", value=profile.avatar_url if (profile and profile.avatar_url) else "", placeholder="https://example.com/my-photo.jpg")
            
            if st.form_submit_button("Save Profile Changes"):
                if not profile:
                    profile = ProfileDB(name=member_name)
                    db.add(profile)
                profile.dob = e_dob
                profile.height = e_height
                profile.current_weight = e_cur_weight
                profile.target_weight = e_target_weight
                profile.gender = e_gender
                profile.diet = e_diet
                if e_avatar_url:
                    profile.avatar_url = e_avatar_url
                db.commit()
                st.success("Profile updated successfully!")
                st.rerun()

        st.divider()
        st.markdown("#### 🔒 Update Security PIN")
        with st.form("change_pin_form"):
            curr_pin_check = st.text_input("Current PIN", type="password", max_chars=4)
            updated_pin = st.text_input("New 4-Digit PIN", type="password", max_chars=4)
            if st.form_submit_button("Update PIN"):
                if profile and profile.pin == curr_pin_check:
                    if len(updated_pin) == 4 and updated_pin.isdigit():
                        profile.pin = updated_pin
                        db.commit()
                        st.success("Security PIN updated successfully!")
                    else:
                        st.error("New PIN must be 4 numeric digits.")
                else:
                    st.error("Incorrect current PIN.")

        st.divider()
        st.warning(f"⚠️ Danger Zone: Deleting **{member_name}** will permanently erase all profile and health records.")
        
        confirm = st.checkbox(f"I understand that deleting {member_name}'s profile is permanent.")
        delete_pin = st.text_input("Confirm with your 4-digit PIN to delete", type="password", max_chars=4)
        
        if st.button(f"🗑️ Delete {member_name}'s Profile", type="primary", disabled=not confirm):
            if profile and profile.pin == delete_pin:
                db.query(VitalLogDB).filter(VitalLogDB.member == member_name).delete()
                db.query(WeightLogDB).filter(WeightLogDB.member == member_name).delete()
                db.query(HabitLogDB).filter(HabitLogDB.member == member_name).delete()
                db.delete(profile)
                db.commit()
                st.session_state.active_member = None
                st.success(f"Profile for {member_name} has been completely deleted.")
                st.rerun()
            else:
                st.error("Incorrect PIN. Deletion cancelled.")

    st.divider()

    # INITIAL SETUP FORM IF DOB IS NOT YET SAVED
    if not profile or not profile.dob:
        st.info("👋 Welcome! Optional: Set up your profile metrics below or skip and fill later.")
        with st.form("setup_form"):
            dob = st.date_input("Date of Birth (Optional)", value=date(2001, 9, 12), min_value=MIN_DOB, max_value=MAX_DOB)
            height = st.number_input("Height (cm) (Optional)", value=None, placeholder="e.g. 170.0")
            weight = st.number_input("Current Weight (kg) (Optional)", value=None, placeholder="e.g. 70.0")
            target = st.number_input("Target Weight (kg) (Optional)", value=None, placeholder="e.g. 65.0")
            gender = st.selectbox("Sex (Optional)", ["Male", "Female"], index=None, placeholder="Select Sex...")
            diet = st.selectbox("Diet Preference (Optional)", ["Vegetarian", "Non-Vegetarian", "Vegan", "Eggetarian"], index=None, placeholder="Select Diet...")
            
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
                st.success("Profile updated!")
                st.rerun()
    else:
        rec_protein = round(profile.current_weight * 1.0, 1) if profile.current_weight else 60.0

        tabs = st.tabs(["📊 Overview & Goals", "🫀 Vitals", "⚖️ Weight & Steps", "💧 Daily Habits"])

        # TAB 1: OVERVIEW & GOALS
        with tabs[0]:
            st.subheader("🎯 Target Weight & Progress")
            
            latest_vital = db.query(VitalLogDB).filter(VitalLogDB.member == member_name).order_by(VitalLogDB.log_date.desc()).first()
            bp_val = f"{latest_vital.systolic}/{latest_vital.diastolic}" if (latest_vital and latest_vital.systolic and latest_vital.diastolic) else "No records"

            cur_w = profile.current_weight or 0.0
            tgt_w = profile.target_weight or 0.0
            diff = round(cur_w - tgt_w, 1)

            with st.container(border=True):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Current Weight", f"{cur_w} kg" if cur_w else "--")
                c2.metric("Target Weight", f"{tgt_w} kg" if tgt_w else "--")
                
                if cur_w and tgt_w:
                    if diff > 0:
                        c3.metric("Weight Left to Lose", f"{abs(diff)} kg", delta=f"-{abs(diff)} kg", delta_color="inverse")
                    elif diff < 0:
                        c3.metric("Weight Left to Gain", f"{abs(diff)} kg", delta=f"+{abs(diff)} kg")
                    else:
                        c3.metric("Goal Status", "Target Achieved! 🎉")
                else:
                    c3.metric("Weight Left", "--")
                
                c4.metric("Latest BP", bp_val)

            w_history = db.query(WeightLogDB).filter(WeightLogDB.member == member_name, WeightLogDB.weight.isnot(None)).order_by(WeightLogDB.log_date.asc()).all()
            if w_history:
                st.write("")
                st.subheader("📈 Weight Progress Trend")
                df_w_chart = pd.DataFrame([{"Date": r.log_date, "Weight (kg)": r.weight} for r in w_history])
                df_w_chart.set_index("Date", inplace=True)
                st.line_chart(df_w_chart)

        # TAB 2: VITALS
        with tabs[1]:
            st.subheader("🫀 Log Vitals")
            with st.form("vitals_form"):
                cv1, cv2, cv3, cv4 = st.columns(4)
                
                with cv1:
                    v_date = st.date_input("Log Date", value=date.today())

                with cv2:
                    sys_bp = st.number_input("Systolic BP (Optional)", value=None, placeholder="e.g. 120")

                with cv3:
                    dia_bp = st.number_input("Diastolic BP (Optional)", value=None, placeholder="e.g. 80")

                with cv4:
                    sugar = st.number_input("Blood Sugar (mg/dL) (Optional)", value=None, placeholder="e.g. 95.0")

                timing = st.radio("Context (Optional)", ["Fasting", "Post-Meal", "Random"], index=None, horizontal=True)

                if st.form_submit_button("Save Vitals"):
                    if sys_bp is not None or dia_bp is not None or sugar is not None or timing is not None:
                        log = VitalLogDB(member=member_name, log_date=v_date, systolic=sys_bp, diastolic=dia_bp, blood_sugar=sugar, timing=timing)
                        db.add(log)
                        db.commit()
                        st.success("Vitals saved!")
                        st.rerun()
                    else:
                        st.warning("Please fill at least one metric to save a log entry.")

            v_history = db.query(VitalLogDB).filter(VitalLogDB.member == member_name).order_by(VitalLogDB.log_date.asc()).all()
            if v_history:
                st.write("")
                st.subheader("📈 Blood Pressure & Sugar Trends")
                df_v_chart = pd.DataFrame([{
                    "Date": r.log_date, 
                    "Systolic BP": r.systolic, 
                    "Diastolic BP": r.diastolic,
                    "Blood Sugar": r.blood_sugar
                } for r in v_history])
                df_v_chart.set_index("Date", inplace=True)
                
                c_chart1, c_chart2 = st.columns(2)
                with c_chart1:
                    st.caption("Blood Pressure (Systolic vs Diastolic)")
                    st.line_chart(df_v_chart[["Systolic BP", "Diastolic BP"]])
                with c_chart2:
                    st.caption("Blood Sugar Level")
                    st.line_chart(df_v_chart[["Blood Sugar"]])

            st.write("")
            st.subheader("🔍 Search Vital Logs by Date")
            query = db.query(VitalLogDB).filter(VitalLogDB.member == member_name)
            search_date = st.date_input("Select Filter Date", value=None, key="v_search")
            
            if search_date:
                query = query.filter(VitalLogDB.log_date == search_date)
            
            records = query.order_by(VitalLogDB.log_date.desc()).all()
            if records:
                df = pd.DataFrame([{"Date": r.log_date, "BP": f"{r.systolic or '--'}/{r.diastolic or '--'}", "Sugar": r.blood_sugar or '--', "Timing": r.timing or '--'} for r in records])
                st.dataframe(df, use_container_width=True, hide_index=True)

        # TAB 3: WEIGHT & STEPS
        with tabs[2]:
            st.subheader("⚖️ Log Weight & Step Count")
            with st.form("weight_form"):
                cw1, cw2, cw3 = st.columns(3)
                
                with cw1:
                    w_date = st.date_input("Date", value=date.today())

                with cw2:
                    w_val = st.number_input("Weight (kg) (Optional)", value=None, placeholder="e.g. 70.0")

                with cw3:
                    s_val = st.number_input("Steps Walked (Optional)", value=None, placeholder="e.g. 8000")

                if st.form_submit_button("Save Entry"):
                    if w_val is not None or s_val is not None:
                        log = WeightLogDB(member=member_name, log_date=w_date, weight=w_val, steps=s_val)
                        db.add(log)
                        if w_val is not None:
                            profile.current_weight = w_val
                        db.commit()
                        st.success("Entry updated!")
                        st.rerun()
                    else:
                        st.warning("Please enter either weight or steps to save.")

            ws_history = db.query(WeightLogDB).filter(WeightLogDB.member == member_name, WeightLogDB.steps.isnot(None)).order_by(WeightLogDB.log_date.asc()).all()
            if ws_history:
                st.write("")
                st.subheader("📈 Daily Step Count")
                df_ws_chart = pd.DataFrame([{"Date": r.log_date, "Steps": r.steps} for r in ws_history])
                df_ws_chart.set_index("Date", inplace=True)
                st.line_chart(df_ws_chart)

            st.write("")
            st.subheader("🔍 Search Weight Logs by Date")
            q_ws = db.query(WeightLogDB).filter(WeightLogDB.member == member_name)
            s_ws_date = st.date_input("Select Filter Date", value=None, key="ws_search")
            if s_ws_date:
                q_ws = q_ws.filter(WeightLogDB.log_date == s_ws_date)
            
            ws_records = q_ws.order_by(WeightLogDB.log_date.desc()).all()
            if ws_records:
                df_ws = pd.DataFrame([{"Date": r.log_date, "Weight (kg)": r.weight or '--', "Steps": r.steps or '--'} for r in ws_records])
                st.dataframe(df_ws, use_container_width=True, hide_index=True)

        # TAB 4: DAILY HABITS
        with tabs[3]:
            st.subheader("💧 Log Daily Habits")
            with st.form("habit_form"):
                ch1, ch2, ch3, ch4 = st.columns(4)
                
                with ch1:
                    h_date = st.date_input("Date", value=date.today())

                with ch2:
                    sleep = st.number_input("Sleep (hrs) (Optional)", value=None, placeholder="e.g. 7.5")

                with ch3:
                    water = st.number_input("Water Intake (L) (Optional)", value=None, placeholder="e.g. 2.5")

                with ch4:
                    prot = st.number_input("Protein Intake (g) (Optional)", value=None, placeholder=f"e.g. {rec_protein}")

                if st.form_submit_button("Save Habits"):
                    if sleep is not None or water is not None or prot is not None:
                        log = HabitLogDB(member=member_name, log_date=h_date, sleep_hrs=sleep, water_l=water, protein_g=prot)
                        db.add(log)
                        db.commit()
                        st.success("Habits logged successfully!")
                        st.rerun()
                    else:
                        st.warning("Please enter at least one habit metric to save.")

            h_history = db.query(HabitLogDB).filter(HabitLogDB.member == member_name).order_by(HabitLogDB.log_date.asc()).all()
            if h_history:
                st.write("")
                st.subheader("📈 Habit Trends over Time")
                df_h_chart = pd.DataFrame([{"Date": r.log_date, "Water (L)": r.water_l, "Sleep (hrs)": r.sleep_hrs, "Protein (g)": r.protein_g} for r in h_history])
                df_h_chart.set_index("Date", inplace=True)
                
                hc1, hc2 = st.columns(2)
                with hc1:
                    st.caption("Water & Sleep Intake")
                    st.line_chart(df_h_chart[["Water (L)", "Sleep (hrs)"]])
                with hc2:
                    st.caption("Daily Protein (g)")
                    st.line_chart(df_h_chart[["Protein (g)"]])

            st.write("")
            st.subheader("🔍 Search Habit Logs by Date")
            q_h = db.query(HabitLogDB).filter(HabitLogDB.member == member_name)
            s_h_date = st.date_input("Select Filter Date", value=None, key="h_search")
            if s_h_date:
                q_h = q_h.filter(HabitLogDB.log_date == s_h_date)
                
            h_records = q_h.order_by(HabitLogDB.log_date.desc()).all()
            if h_records:
                df_h = pd.DataFrame([{"Date": r.log_date, "Sleep (hrs)": r.sleep_hrs or '--', "Water (L)": r.water_l or '--', "Protein (g)": r.protein_g or '--'} for r in h_records])
                st.dataframe(df_h, use_container_width=True, hide_index=True)

db.close()
