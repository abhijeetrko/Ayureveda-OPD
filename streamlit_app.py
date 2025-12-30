import streamlit as st
import pandas as pd
from datetime import date
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI

# ------------------ PAGE CONFIG ------------------
st.set_page_config(page_title="", layout="wide")

st.title("🌿 Welcome Vaidya Prathama, Your OPD Summary Dashboard")
st.caption(
    "For OPD overview only. "
    "No diagnosis or treatment decisions are made here."
)

# ------------------ SESSION STATE ------------------
if "opd_data" not in st.session_state:
    st.session_state.opd_data = []

if "current_view" not in st.session_state:
    st.session_state.current_view = "overview"


# -------- GOOGLE SHEETS CONNECTION --------
def get_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_key(
        st.secrets["SHEET_ID"]
    ).sheet1
    return sheet
# ------------------ SIDEBAR ------------------
st.sidebar.header("🩺 OPD Actions")

if st.sidebar.button("📊 OPD Overview"):
    st.session_state.current_view = "overview"

if st.sidebar.button("➕ Add OPD Entry"):
    st.session_state.current_view = "entry"

# ------------------ MAIN SECTION ------------------
# ================== ADD OPD ENTRY ==================
if st.session_state.current_view == "entry":
    st.subheader("📝 Add OPD Patient Details")

    with st.form("opd_form", clear_on_submit=True):
        opd_date = st.date_input("OPD Date", value=date.today())
        patient_name = st.text_input("Patient Name")
        age = st.number_input("Age", min_value=0, max_value=120, step=1)
        gender = st.selectbox("Gender", ["Male", "Female", "Other"])
        prakriti = st.selectbox(
            "Prakriti",
            ["Vata", "Pitta", "Kapha", "Vata-Pitta", "Pitta-Kapha", "Vata-Kapha"]
        )
        complaint = st.text_input("Main Complaint")
        diagnosis = st.text_input("Diagnosis (Doctor Entry)")
        follow_up = st.selectbox("Follow-up Required?", ["Yes", "No"])

        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("Save Entry")
        with col2:
            cancel = st.form_submit_button("Cancel")

        if submitted:
            sheet = get_sheet()
            sheet.append_row([
                str(opd_date),
                patient_name,
                age,
                gender,
                prakriti,
                complaint,
                diagnosis,
                follow_up
            ])
            st.success("OPD entry added successfully")
            st.session_state.current_view = "overview"

        if cancel:
            st.session_state.current_view = "overview"

# ================== OPD OVERVIEW ==================
else:
    st.subheader("📊 OPD Overview")
    sheet = get_sheet()
    records = sheet.get_all_records()
    df = pd.DataFrame(records)
    opd_json = df.to_dict(orient="records")

    if df.empty:
        st.info("No OPD data available. Add entries using 'Add OPD Entry'.")
    else:
        # -------- DATE FILTER --------
        with st.expander("📅 Filter by Date (Optional)", expanded=False):
            selected_date = st.date_input(
                "Select Date",
                value=None
            )

        if selected_date:
            df = df[df["Date"] == selected_date]

        # -------- KPIs --------
        col1, col2, col3, col4 = st.columns(4)

        col1.metric("Total Patients", len(df))
        col2.metric("Follow-ups", df["FollowUp"].value_counts().get("Yes", 0))
        col3.metric("Top Diagnosis", df["Diagnosis"].mode()[0] if not df.empty else "-")
        col4.metric("Dominant Prakriti", df["Prakriti"].mode()[0] if not df.empty else "-")

        # -------- CHARTS --------
        st.subheader("📈 OPD Distribution")

        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.bar_chart(df["Diagnosis"].value_counts())

        with chart_col2:
            st.bar_chart(df["Prakriti"].value_counts())

        # -------- TABLE --------
        st.subheader("📋 OPD Patient List")
        st.dataframe(df, use_container_width=True)

# ------------------ FOOTER ------------------
st.markdown("---")


# ------------------ OPENAI CLIENT ------------------
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])


def build_opd_prompt(opd_json, user_prompt):
    return f"""
You are assisting an Ayurvedic doctor.

STRICT RULES:
- Do NOT diagnose
- Do NOT suggest medicines
- Do NOT change treatment
- Only summarize and observe patterns
- Use simple, non-alarming language

OPD DATA:
{opd_json}

TASK:
1. Give a short OPD summary + {user_prompt}
2. List most common complaints
3. List common diagnoses
4. Mention prakriti trends
5. Mention follow-up workload
6. How Next week will be?
7. How I can be Prepared?
"""

st.markdown("---")
st.subheader("🧠 AI Prompt Playground (Basic)")

user_prompt = st.text_area(
    "Enter your prompt",
    placeholder="e.g. Summarize today's OPD in simple language",
    height=120
)

prompt = build_opd_prompt(opd_json, user_prompt)

if st.button("Generate Response"):
    if user_prompt.strip() == "":
        st.warning("Please enter a prompt")
    else:
        with st.spinner("Thinking..."):
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "user", "content": prompt},
                    {"role":"system","content":"You are assiting ayurvedic doctor for his OPD summary and analysis"}
                ],
                temperature=0.3
            )

            ai_output = response.choices[0].message.content
            st.text_area(
                "AI Response",
                ai_output,
                height=200
            )
