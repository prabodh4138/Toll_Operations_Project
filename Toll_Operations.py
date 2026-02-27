import streamlit as st
import importlib
from supabase import create_client

# ==========================================================
# PAGE CONFIG
# ==========================================================
st.set_page_config(page_title="Toll Operations System", layout="wide")

# ==========================================================
# SUPABASE CONNECTION
# ==========================================================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================================
# MODULE LIST (UNCHANGED)
# ==========================================================
MODULES = {
    "DG Monitoring": "diesel_monitoring_app",
    "EB Meter Reading": "eb_meter_reading_app",
    "Highway Reading": "highway_reading_app",
    "Inventory Management": "inventory_management_app",
    "Solar Generation": "solar_power_module",
}

# ==========================================================
# AUTH PAGE
# ==========================================================
def auth_page():

    st.title("🔐 Toll Operations Login")

    emp_id = st.text_input("Employee ID")
    password = st.text_input("Password", type="password")

    if st.button("Login"):

        try:
            response = supabase.auth.sign_in_with_password({
                "email": f"{emp_id}@sekura.in",
                "password": password
            })

            user = response.user
            if not user:
                st.error("Invalid credentials")
                return

            emp = supabase.table("employees") \
                .select("*") \
                .eq("id", user.id) \
                .single() \
                .execute()

            if not emp.data:
                st.error("User not registered")
                return

            st.session_state.logged_in = True
            st.session_state.employee_id = emp.data["employee_id"]
            st.session_state.role = emp.data["role"]
            st.session_state.toll_plaza = emp.data["toll_plaza"]
            st.session_state.full_name = emp.data["full_name"]

            st.rerun()

        except Exception as e:
            st.error(f"Login failed: {e}")

# ==========================================================
# LOGOUT
# ==========================================================
def logout():
    supabase.auth.sign_out()
    st.session_state.clear()
    st.rerun()

# ==========================================================
# MAIN APP
# ==========================================================
def main():

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        auth_page()
        return

    # ================= GREETING SCREEN =================
    st.success(
        f"Hello {st.session_state.full_name} 👋\n\n"
        f"Login as: {st.session_state.role.upper()}\n\n"
        f"Plaza: {st.session_state.toll_plaza}"
    )

    st.markdown("---")

    # ================= SIDEBAR =================
    st.sidebar.success(f"👤 {st.session_state.employee_id}")
    st.sidebar.info(f"📍 {st.session_state.toll_plaza}")
    st.sidebar.warning(f"Role: {st.session_state.role}")

    menu = list(MODULES.keys())

    if st.session_state.role == "admin":
        menu.append("Admin Panel")

    choice = st.sidebar.selectbox("Select Module", menu)

    if st.sidebar.button("Logout"):
        logout()

    if choice == "Admin Panel":
        st.title("Admin Panel")
        st.write("Admin features here")
        return

    mod = importlib.import_module(MODULES[choice])
    mod.run()

if __name__ == "__main__":
    main()
