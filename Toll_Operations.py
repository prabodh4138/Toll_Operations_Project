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
# AUTH PAGE (LOGIN + SIGNUP + RESET)
# ==========================================================
def auth_page():

    if "auth_mode" not in st.session_state:
        st.session_state.auth_mode = "login"

    st.title("🔐 Toll Operations System")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Login"):
            st.session_state.auth_mode = "login"

    with col2:
        if st.button("Sign Up"):
            st.session_state.auth_mode = "signup"

    with col3:
        if st.button("Reset Password"):
            st.session_state.auth_mode = "reset"

    st.markdown("---")

    # ================= LOGIN =================
    if st.session_state.auth_mode == "login":

        emp_id = st.text_input("Employee ID", key="login_emp")
        password = st.text_input("Password", type="password", key="login_pass")

        if st.button("Login Now"):

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
                    st.error("User not registered.")
                    return

                st.session_state.logged_in = True
                st.session_state.employee_id = emp.data["employee_id"]
                st.session_state.role = emp.data["role"]
                st.session_state.toll_plaza = emp.data["toll_plaza"]
                st.session_state.full_name = emp.data["full_name"]

                st.rerun()

            except Exception as e:
                st.error(f"Login failed: {e}")

    # ================= SIGNUP =================
    if st.session_state.auth_mode == "signup":

        new_emp = st.text_input("Employee ID", key="signup_emp")
        new_pass = st.text_input("Set Password", type="password", key="signup_pass")

        if st.button("Create Account"):

            try:
                # Check predefined employee
                master = supabase.table("employee_master") \
                    .select("*") \
                    .eq("employee_code", new_emp) \
                    .single() \
                    .execute()

                if not master.data:
                    st.error("Employee ID not authorized.")
                    return

                plaza = master.data["toll_plaza"]
                role = master.data["role"]
                full_name = master.data["full_name"]

                # Create Auth user
                response = supabase.auth.sign_up({
                    "email": f"{new_emp}@sekura.in",
                    "password": new_pass
                })

                user = response.user
                if not user:
                    st.error("Signup failed.")
                    return

                # Insert into employees table
                supabase.table("employees").insert({
                    "id": user.id,
                    "employee_id": new_emp,
                    "toll_plaza": plaza,
                    "role": role,
                    "full_name": full_name,
                    "is_active": True
                }).execute()

                st.success("Account created successfully. Please login.")

                # Redirect to login
                st.session_state.auth_mode = "login"

            except Exception as e:
                st.error(f"Signup failed: {e}")

    # ================= RESET PASSWORD =================
    if st.session_state.auth_mode == "reset":

        reset_emp = st.text_input("Employee ID", key="reset_emp")
        new_password = st.text_input("New Password", type="password", key="reset_pass")

        if st.button("Update Password"):

            try:
                # Send reset email
                supabase.auth.reset_password_email(
                    f"{reset_emp}@sekura.in"
                )
                st.success("Password reset email sent.")
            except:
                st.error("Password reset failed.")

# ==========================================================
# LOGOUT
# ==========================================================
def logout():
    supabase.auth.sign_out()
    st.session_state.clear()
    st.rerun()

# ==========================================================
# MAIN
# ==========================================================
def main():

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        auth_page()
        return

    # Greeting
    st.success(
        f"Hello {st.session_state.full_name} 👋\n\n"
        f"Login as: {st.session_state.role.upper()}\n\n"
        f"Plaza: {st.session_state.toll_plaza}"
    )

    st.markdown("---")

    # Sidebar
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
        st.write("Admin features here.")
        return

    mod = importlib.import_module(MODULES[choice])
    mod.run()

if __name__ == "__main__":
    main()
