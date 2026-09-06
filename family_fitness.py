import base64
import hashlib
import io
from datetime import date
import pandas as pd
from PIL import Image
import streamlit as st
from sqlalchemy import Column, Date, Float, ForeignKey, Integer, String, create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

# --- 1. PAGE SETUP & STYLING ---
st.set_page_config(page_title="Family Health & Fitness", page_icon="🏋️‍♂️", layout="wide")

st.markdown("""
    <style>
    .main-header { font-weight: 700; color: #1E293B; margin-bottom: 0px; }
    .sub-text { color: #64748B; font-size: 0.95rem; }
    [data-testid="stMetricValue"] { font-weight: 700; color: #0F172A; }
    </style>
""", unsafe_allow_html=True)

# --- 2. SECURITY & IMAGE HELPERS ---
def hash_pin(pin: str) -> str:
    """Hashes PIN inputs using SHA-256."""
    return hashlib.sha256(pin.encode('utf-8')).hexdigest()

def process_uploaded_image(uploaded_file, max_size=(300, 300), quality=85):
    """Resizes and compresses uploaded images using PIL, returning a lightweight Base64 string."""
    if uploaded_file is None:
        return None
    try:
        img = Image.open(uploaded_file)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality, optimize=True)
        buffer.seek(0)
        
        base64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{base64_str}"
    except Exception as e:
        st.error(f"Error processing image: {e}")
        return None

# --- 3. DATABASE CONNECTION & SECRETS ---
LOCAL_URL = "sqlite:///./health_tracker.db"
SUPABASE_URL = st.secrets.get("SUPABASE_URL", None)

@st.cache_resource
def init_db_engine():
    """Attempts cloud connection; falls back to local SQLite if unavailable."""
    if SUPABASE_URL:
        try:
            engine = create_engine(SUPABASE_URL, pool_pre_ping=True, connect_args={"connect_timeout": 5})
            with engine.connect() as conn:
                pass
            return engine, "Supabase Cloud"
        except Exception:
            pass
    
    engine = create_engine(LOCAL_URL, connect_args={"check_same_thread": False})
    return engine, "Local SQLite (Offline)"

engine, db_source = init_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- 4. SCHEMA DEFINITIONS ---
class ProfileDB(Base):
    __tablename__ = "profiles"
    name = Column(String, primary_key=True, index=True)
    pin = Column(String, nullable=False)
    avatar_url = Column(String, nullable=True)
    gender = Column(String, nullable=True)
    dob = Column(Date, nullable=True)
    height = Column(Float, nullable=True)
    current_weight = Column(Float, nullable=True)
    target_weight = Column(Float, nullable=True)
    diet = Column(String, nullable=True)

class VitalLogDB(Base):
    __tablename__ = "vitals"
    id = Column(Integer, primary_key=True, autoincrement=True)
    member = Column(String, ForeignKey("profiles.name", ondelete="CASCADE"))
    log_date = Column(Date, index=True)
    systolic = Column(Integer, nullable=True)
    diastolic = Column(Integer, nullable=True)
    blood_sugar = Column(Float, nullable=True)
    timing = Column(String, nullable=True)

class WeightLogDB(Base):
    __tablename__ = "weight_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    member = Column(String, ForeignKey("profiles.name", ondelete="CASCADE"))
    log_date = Column(Date, index=True)
    weight = Column(Float, nullable=True)
    steps = Column(Integer, nullable=True)

class HabitLogDB(Base):
    __tablename__ = "habit_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    member = Column(String, ForeignKey("profiles.name", ondelete="CASCADE"))
    log_date = Column(Date, index=True)
    sleep_hrs = Column(Float, nullable=True)
    water_l = Column(Float, nullable=True)
    protein_g = Column(Float, nullable=True)

Base.metadata.create_all(bind=engine)

# Schema Migrations
inspector = inspect(engine)
if "profiles" in inspector.get_table_names():
    existing_columns = [col["name"] for col in inspector.get_columns("profiles")]
    with engine.begin() as conn:
        if "pin" not in existing_columns:
            conn.execute(text("ALTER TABLE profiles ADD COLUMN pin VARCHAR;"))
        if "avatar_url" not in existing_columns:
            conn.execute(text("ALTER TABLE profiles ADD COLUMN avatar_url VARCHAR;"))

# --- 5. UTILITY FUNCTIONS ---
def calculate_age(dob):
    if not dob:
        return "--"
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

DEFAULT_AVATAR = "https://cdn-icons-png.flaticon.com/512/3135/3135715.png"
DEFAULT_MEMBERS = ["Kush", "Dharmesh", "Kinaree", "Daksha", "Dhaval", "Pallavi", "Charvi", "Parhi"]

# --- 6. SESSION STATE & NAVIGATION ---
if "active_member" not in st.session_state:
    st.session_state.active_member = None
if "selected_member_auth" not in st.session_state:
    st.session_state.selected_member_auth = None

db = SessionLocal()

try:
    # --- SCREEN A: PROFILE SELECTOR & AUTHENTICATION ---
    if st.session_state.active_member is None:
        st.markdown("<h1 class='main-header'>🏋️‍♂️ Family Health & Fitness</h1>", unsafe_allow_html=True)
        st.markdown(f"<p class='sub-text'>Select your profile. <i>(Database Mode: {db_source})</i></p>", unsafe_allow_html=True)
        st.divider()

        if st.session_state.selected_member_auth:
            auth_name = st.session_state.selected_member_auth
            p_rec = db.query(ProfileDB).filter(ProfileDB.name == auth_name).first()

            st.subheader(f"🔒 Security Verification: {auth_name}")
            
            # Setup PIN if non-existent
            if not p_rec or not p_rec.pin:
                st.info("No PIN configured for this user. Please establish a 4-digit PIN.")
                with st.form("set_pin_form"):
                    new_pin = st.text_input("Set 4-Digit PIN", type="password", max_chars=4)
                    confirm_pin = st.text_input("Confirm 4-Digit PIN", type="password", max_chars=4)
                    c1, c2 = st.columns(2)
                    
                    if c1.form_submit_button("Set PIN & Continue"):
                        if len(new_pin) == 4 and new_pin.isdigit():
                            if new_pin == confirm_pin:
                                hashed_val = hash_pin(new_pin)
                                if not p_rec:
                                    p_rec = ProfileDB(name=auth_name, pin=hashed_val, avatar_url=DEFAULT_AVATAR)
                                    db.add(p_rec)
                                else:
                                    p_rec.pin = hashed_val
                                db.commit()
                                st.session_state.active_member = auth_name
                                st.session_state.selected_member_auth = None
                                st.success("PIN set successfully!")
                                st.rerun()
                            else:
                                st.error("PIN inputs do not match.")
                        else:
                            st.error("PIN must be exactly 4 digits.")
                            
                    if c2.form_submit_button("Cancel"):
                        st.session_state.selected_member_auth = None
                        st.rerun()
            else:
                # PIN Authentication
                with st.form("verify_pin_form"):
                    entered_pin = st.text_input("Enter 4-Digit Security PIN", type="password", max_chars=4)
                    c1, c2 = st.columns(2)
                    
                    if c1.form_submit_button("Unlock Profile"):
                        if hash_pin(entered_pin) == p_rec.pin:
                            st.session_state.active_member = auth_name
                            st.session_state.selected_member_auth = None
                            st.rerun()
                        else:
                            st.error("Incorrect PIN entered.")
                            
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
            with st.expander("➕ Add New Member Profile"):
                with st.form("add_member"):
                    new_name = st.text_input("Member Name", value="").strip()
                    gender_opt = st.selectbox("Biological Sex (Optional)", ["Male", "Female"], index=None, placeholder="Select...")
                    
                    uploaded_img = st.file_uploader("Upload Profile Picture", type=["png", "jpg", "jpeg", "webp"])
                    new_avatar_url = st.text_input("OR Image URL (Optional)", value="")
                    new_user_pin = st.text_input("Set 4-Digit Security PIN", type="password", max_chars=4)
                    
                    if st.form_submit_button("Create Profile"):
                        if new_name and len(new_user_pin) == 4 and new_user_pin.isdigit():
                            if not db.query(ProfileDB).filter(ProfileDB.name == new_name).first():
                                final_avatar = DEFAULT_AVATAR
                                if uploaded_img is not None:
                                    final_avatar = process_uploaded_image(uploaded_img)
                                elif new_avatar_url.strip():
                                    final_avatar = new_avatar_url.strip()

                                new_p = ProfileDB(
                                    name=new_name, 
                                    gender=gender_opt, 
                                    pin=hash_pin(new_user_pin), 
                                    avatar_url=final_avatar
                                )
                                db.add(new_p)
                                db.commit()
                                st.session_state.active_member = new_name
                                st.rerun()
                            else:
                                st.error("A profile with this name already exists.")
                        else:
                            st.error("Provide a valid name and 4-digit PIN.")

    # --- SCREEN B: ACTIVE DASHBOARD ---
    else:
        member_name = st.session_state.active_member
        profile = db.query(ProfileDB).filter(ProfileDB.name == member_name).first()

        # ENSURE PROFILE RECORD EXISTS IN DATABASE
        if not profile:
            profile = ProfileDB(name=member_name, pin=hash_pin("0000"), avatar_url=DEFAULT_AVATAR)
            db.add(profile)
            db.commit()
            db.refresh(profile)

        col_t, col_b = st.columns([5, 1])
        current_avatar = profile.avatar_url if profile.avatar_url else DEFAULT_AVATAR
        col_t.image(current_avatar, width=50)
        col_t.title(f"{member_name}'s Dashboard")
        if col_b.button("🔒 Lock / Switch"):
            st.session_state.active_member = None
            st.rerun()

        # PROFILE SETTINGS & DELETION
        with st.expander("⚙️ Account Settings & Security"):
            st.markdown("#### ✏️ Profile Information")
            with st.form("edit_profile_form"):
                e_dob = st.date_input("Date of Birth", value=profile.dob)
                e_height = st.number_input("Height (cm)", value=profile.height)
                e_cur_weight = st.number_input("Current Weight (kg)", value=profile.current_weight)
                e_target_weight = st.number_input("Target Weight (kg)", value=profile.target_weight)
                
                sex_index = ["Male", "Female"].index(profile.gender) if profile.gender in ["Male", "Female"] else None
                e_gender = st.selectbox("Biological Sex", ["Male", "Female"], index=sex_index)
                
                diet_options = ["Vegetarian", "Non-Vegetarian", "Vegan", "Eggetarian"]
                diet_index = diet_options.index(profile.diet) if profile.diet in diet_options else None
                e_diet = st.selectbox("Dietary Preference", diet_options, index=diet_index)
                
                e_uploaded_img = st.file_uploader("Upload New Profile Picture", type=["png", "jpg", "jpeg", "webp"])
                e_avatar_url = st.text_input("OR Custom Avatar Image URL", value=profile.avatar_url or "")
                
                if st.form_submit_button("Save Profile Settings"):
                    profile.dob = e_dob
                    profile.height = e_height
                    profile.current_weight = e_cur_weight
                    profile.target_weight = e_target_weight
                    profile.gender = e_gender
                    profile.diet = e_diet
                    
                    if e_uploaded_img is not None:
                        profile.avatar_url = process_uploaded_image(e_uploaded_img)
                    elif e_avatar_url:
                        profile.avatar_url = e_avatar_url

                    db.commit()
                    st.success("Profile saved!")
                    st.rerun()

            st.divider()
            st.markdown("#### 🔒 Update Security PIN")
            with st.form("change_pin_form"):
                curr_pin_check = st.text_input("Current PIN", type="password", max_chars=4)
                updated_pin = st.text_input("New 4-Digit PIN", type="password", max_chars=4)
                if st.form_submit_button("Update PIN"):
                    if hash_pin(curr_pin_check) == profile.pin:
                        if len(updated_pin) == 4 and updated_pin.isdigit():
                            profile.pin = hash_pin(updated_pin)
                            db.commit()
                            st.success("PIN updated!")
                        else:
                            st.error("PIN must be 4 digits.")
                    else:
                        st.error("Incorrect current PIN.")

            st.divider()
            st.warning("⚠️ Deleting your profile permanently erases recorded health data.")
            confirm = st.checkbox("Confirm permanent profile removal")
            delete_pin = st.text_input("Enter 4-digit PIN to confirm deletion", type="password", max_chars=4)
            
            if st.button("🗑️ Delete Profile Permanently", type="primary", disabled=not confirm):
                if hash_pin(delete_pin) == profile.pin:
                    db.query(VitalLogDB).filter(VitalLogDB.member == member_name).delete()
                    db.query(WeightLogDB).filter(WeightLogDB.member == member_name).delete()
                    db.query(HabitLogDB).filter(HabitLogDB.member == member_name).delete()
                    db.delete(profile)
                    db.commit()
                    st.session_state.active_member = None
                    st.success("Profile deleted successfully.")
                    st.rerun()
                else:
                    st.error("Incorrect PIN. Action aborted.")

        st.divider()

        # DASHBOARD METRICS & TABS
        tabs = st.tabs(["📊 Overview & Goals", "🫀 Vitals", "⚖️ Weight & Steps", "💧 Daily Habits"])

        # TAB 1: OVERVIEW & GOALS
        with tabs[0]:
            st.subheader("🎯 Weight Progress Tracking")
            latest_vital = db.query(VitalLogDB).filter(VitalLogDB.member == member_name).order_by(VitalLogDB.log_date.desc()).first()
            bp_val = f"{latest_vital.systolic}/{latest_vital.diastolic}" if (latest_vital and latest_vital.systolic and latest_vital.diastolic) else "--"

            cur_w = profile.current_weight or 0.0
            tgt_w = profile.target_weight or 0.0
            diff = round(cur_w - tgt_w, 1)

            with st.container(border=True):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Current Weight", f"{cur_w} kg" if cur_w else "--")
                c2.metric("Target Weight", f"{tgt_w} kg" if tgt_w else "--")
                
                if cur_w and tgt_w:
                    if diff > 0:
                        c3.metric("To Lose", f"{abs(diff)} kg", delta=f"-{abs(diff)} kg", delta_color="inverse")
                    elif diff < 0:
                        c3.metric("To Gain", f"{abs(diff)} kg", delta=f"+{abs(diff)} kg")
                    else:
                        c3.metric("Goal Status", "Target Reached! 🎉")
                else:
                    c3.metric("Weight Difference", "--")
                
                c4.metric("Latest Blood Pressure", bp_val)

            w_history = db.query(WeightLogDB).filter(WeightLogDB.member == member_name, WeightLogDB.weight.isnot(None)).order_by(WeightLogDB.log_date.asc()).all()
            if w_history:
                st.write("")
                st.subheader("📈 Weight Trend")
                df_w_chart = pd.DataFrame([{"Date": r.log_date, "Weight (kg)": r.weight} for r in w_history])
                df_w_chart.set_index("Date", inplace=True)
                st.line_chart(df_w_chart)

        # TAB 2: VITALS
        with tabs[1]:
            st.subheader("🫀 Log Vitals")
            with st.form("vitals_form"):
                cv1, cv2, cv3, cv4 = st.columns(4)
                v_date = cv1.date_input("Date", value=date.today())
                sys_bp = cv2.number_input("Systolic BP (mmHg)", value=None, min_value=50, max_value=250)
                dia_bp = cv3.number_input("Diastolic BP (mmHg)", value=None, min_value=30, max_value=150)
                sugar = cv4.number_input("Blood Sugar (mg/dL)", value=None, min_value=20.0, max_value=600.0)
                timing = st.radio("Context", ["Fasting", "Post-Meal", "Random"], index=None, horizontal=True)

                if st.form_submit_button("Save Vitals Entry"):
                    if sys_bp or dia_bp or sugar or timing:
                        log = VitalLogDB(member=member_name, log_date=v_date, systolic=sys_bp, diastolic=dia_bp, blood_sugar=sugar, timing=timing)
                        db.add(log)
                        db.commit()
                        st.success("Vitals saved successfully!")
                        st.rerun()
                    else:
                        st.warning("Fill at least one metric to log.")

            st.write("")
            st.subheader("🔍 Vital Records Search")
            search_v_date = st.date_input("Filter Records by Date", value=None, key="v_search")
            q_v = db.query(VitalLogDB).filter(VitalLogDB.member == member_name)
            if search_v_date:
                q_v = q_v.filter(VitalLogDB.log_date == search_v_date)
            
            records = q_v.order_by(VitalLogDB.log_date.desc()).all()
            if records:
                df_vitals = pd.DataFrame([{
                    "Date": r.log_date, 
                    "Systolic": r.systolic or '--', 
                    "Diastolic": r.diastolic or '--', 
                    "Sugar (mg/dL)": r.blood_sugar or '--', 
                    "Timing": r.timing or '--'
                } for r in records])
                st.dataframe(df_vitals, use_container_width=True, hide_index=True)

        # TAB 3: WEIGHT & STEPS
        with tabs[2]:
            st.subheader("⚖️ Log Weight & Movement")
            with st.form("weight_form"):
                cw1, cw2, cw3 = st.columns(3)
                w_date = cw1.date_input("Log Date", value=date.today())
                w_val = cw2.number_input("Weight (kg)", value=None, min_value=10.0, max_value=300.0)
                s_val = cw3.number_input("Steps Walked", value=None, min_value=0, max_value=100000)

                if st.form_submit_button("Log Entry"):
                    if w_val or s_val:
                        log = WeightLogDB(member=member_name, log_date=w_date, weight=w_val, steps=s_val)
                        db.add(log)
                        if w_val:
                            profile.current_weight = w_val
                        db.commit()
                        st.success("Weight and activity recorded!")
                        st.rerun()

            st.write("")
            st.subheader("🔍 Weight & Step Search")
            search_ws_date = st.date_input("Filter Records by Date", value=None, key="ws_search")
            q_ws = db.query(WeightLogDB).filter(WeightLogDB.member == member_name)
            if search_ws_date:
                q_ws = q_ws.filter(WeightLogDB.log_date == search_ws_date)
            
            ws_records = q_ws.order_by(WeightLogDB.log_date.desc()).all()
            if ws_records:
                df_ws = pd.DataFrame([{
                    "Date": r.log_date, 
                    "Weight (kg)": r.weight or '--', 
                    "Steps": r.steps or '--'
                } for r in ws_records])
                st.dataframe(df_ws, use_container_width=True, hide_index=True)

        # TAB 4: DAILY HABITS
        with tabs[3]:
            st.subheader("💧 Log Daily Habits")
            with st.form("habit_form"):
                ch1, ch2, ch3, ch4 = st.columns(4)
                h_date = ch1.date_input("Date", value=date.today())
                sleep = ch2.number_input("Sleep (hrs)", value=None, min_value=0.0, max_value=24.0)
                water = ch3.number_input("Water (L)", value=None, min_value=0.0, max_value=15.0)
                prot = ch4.number_input("Protein (g)", value=None, min_value=0.0, max_value=300.0)

                if st.form_submit_button("Save Habits Log"):
                    if sleep or water or prot:
                        log = HabitLogDB(member=member_name, log_date=h_date, sleep_hrs=sleep, water_l=water, protein_g=prot)
                        db.add(log)
                        db.commit()
                        st.success("Habits logged successfully!")
                        st.rerun()

            st.write("")
            st.subheader("🔍 Habit Search")
            search_h_date = st.date_input("Filter Records by Date", value=None, key="h_search")
            q_h = db.query(HabitLogDB).filter(HabitLogDB.member == member_name)
            if search_h_date:
                q_h = q_h.filter(HabitLogDB.log_date == search_h_date)
            
            h_records = q_h.order_by(HabitLogDB.log_date.desc()).all()
            if h_records:
                df_h = pd.DataFrame([{
                    "Date": r.log_date, 
                    "Sleep (hrs)": r.sleep_hrs or '--', 
                    "Water (L)": r.water_l or '--', 
                    "Protein (g)": r.protein_g or '--'
                } for r in h_records])
                st.dataframe(df_h, use_container_width=True, hide_index=True)

finally:
    db.close()
