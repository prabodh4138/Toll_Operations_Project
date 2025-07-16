import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import datetime

# Initialize Supabase
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# -----------------------
# Helper Functions
# -----------------------

def parse_rh(rh_str):
    try:
        if ":" not in rh_str:
            return None
        parts = rh_str.strip().split(":")
        if len(parts) != 2:
            return None
        hours, minutes = int(parts[0]), int(parts[1])
        if not (0 <= minutes < 60 and hours >= 0):
            return None
        return hours * 60 + minutes
    except:
        return None

def format_rh(total_minutes):
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours}:{minutes:02d}"

def calculate_net_rh(opening_rh_str, closing_rh_str):
    opening_minutes = parse_rh(opening_rh_str)
    closing_minutes = parse_rh(closing_rh_str)
    if opening_minutes is None or closing_minutes is None:
        return None, "❌ Incorrect RH format. Use HH:MM."
    if closing_minutes < opening_minutes:
        return None, "❌ Closing RH must be greater than or equal to Opening RH."
    net_minutes = closing_minutes - opening_minutes
    return format_rh(net_minutes), None

# -----------------------
# Admin Block
# -----------------------

def admin_block():
    st.subheader("🛠️ Admin Initialization")

    toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
    dg_name = st.selectbox("Select DG", ["DG1", "DG2", "DG3"])

    opening_diesel_stock = st.number_input("Opening Diesel Stock (L)", min_value=0.0, format="%.2f")
    opening_kwh = st.number_input("Opening KWH", min_value=0.0, format="%.2f")
    opening_rh = st.text_input("Opening RH (HH:MM)")

    if st.button("✅ Initialize"):
        if parse_rh(opening_rh) is None:
            st.error("❌ Incorrect RH format. Use HH:MM.")
            return

        data = {
            "toll_plaza": toll_plaza,
            "dg_name": dg_name,
            "opening_diesel_stock": opening_diesel_stock,
            "opening_kwh": opening_kwh,
            "opening_rh": opening_rh
        }

        resp = supabase.table("dg_opening_status").upsert(data).execute()
        if resp.status_code in [200, 201]:
            st.success("✅ Initialization completed.")
            st.experimental_rerun()
        else:
            st.error(f"❌ Initialization failed: {resp.data}")

# -----------------------
# User Block
# -----------------------

def user_block():
    st.subheader("📝 DG Reading Entry")

    toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
    dg_name = st.selectbox("Select DG", ["DG1", "DG2", "DG3"])
    date = st.date_input("Date", datetime.today())

    diesel_purchase = st.number_input("Diesel Purchase (L)", min_value=0.0, format="%.2f")
    diesel_topup = st.number_input("Diesel Topup (L)", min_value=0.0, format="%.2f")

    barrel_resp = supabase.table("dg_live_status").select("*").eq("toll_plaza", toll_plaza).execute()
    plaza_barrel_stock = barrel_resp.data[0]['updated_plaza_barrel_stock'] if barrel_resp.data else 0.0
    st.info(f"Current Plaza Barrel Stock: {plaza_barrel_stock:.2f} L")

    closing_diesel_stock = st.number_input("Closing Diesel Stock (L)", min_value=0.0, format="%.2f")
    closing_kwh = st.number_input("Closing KWH", min_value=0.0, format="%.2f")
    closing_rh = st.text_input("Closing RH (HH:MM)")
    maximum_demand = st.number_input("Maximum Demand (kVA)", min_value=0.0, format="%.2f")
    remarks = st.text_area("Remarks")

    if st.button("✅ Submit Entry"):
        open_resp = supabase.table("dg_opening_status").select("*").eq("toll_plaza", toll_plaza).eq("dg_name", dg_name).execute()
        if not open_resp.data:
            st.error("❌ Please initialize data in Admin Block first.")
            return

        opening_data = open_resp.data[0]
        opening_diesel_stock = opening_data["opening_diesel_stock"]
        opening_kwh = opening_data["opening_kwh"]
        opening_rh = opening_data["opening_rh"]

        net_rh, error_msg = calculate_net_rh(opening_rh, closing_rh)
        if error_msg:
            st.error(error_msg)
            return

        net_kwh = closing_kwh - opening_kwh
        if net_kwh < 0:
            st.error("❌ Closing KWH must be greater than or equal to Opening KWH.")
            return

        if closing_diesel_stock > (opening_diesel_stock + diesel_topup):
            st.error("❌ Closing Diesel Stock cannot exceed Opening + Topup.")
            return

        diesel_consumption = (opening_diesel_stock + diesel_topup) - closing_diesel_stock
        if diesel_consumption < 0:
            st.error("❌ Diesel Consumption cannot be negative. Check your entries.")
            return

        updated_plaza_barrel_stock = plaza_barrel_stock - diesel_topup

        data = {
            "date": date.strftime("%Y-%m-%d"),
            "toll_plaza": toll_plaza,
            "dg_name": dg_name,
            "diesel_purchase": diesel_purchase,
            "diesel_topup": diesel_topup,
            "updated_plaza_barrel_stock": updated_plaza_barrel_stock,
            "opening_diesel_stock": opening_diesel_stock,
            "closing_diesel_stock": closing_diesel_stock,
            "diesel_consumption": diesel_consumption,
            "opening_kwh": opening_kwh,
            "closing_kwh": closing_kwh,
            "net_kwh": net_kwh,
            "opening_rh": opening_rh,
            "closing_rh": closing_rh,
            "net_rh": net_rh,
            "maximum_demand": maximum_demand,
            "remarks": remarks
        }

        insert_resp = supabase.table("dg_transactions").insert(data).execute()
        supabase.table("dg_live_status").upsert({
            "toll_plaza": toll_plaza,
            "updated_plaza_barrel_stock": updated_plaza_barrel_stock
        }).execute()
        supabase.table("dg_opening_status").upsert({
            "toll_plaza": toll_plaza,
            "dg_name": dg_name,
            "opening_diesel_stock": closing_diesel_stock,
            "opening_kwh": closing_kwh,
            "opening_rh": closing_rh
        }).execute()

        if insert_resp.status_code in [200, 201]:
            st.success("✅ Entry submitted successfully.")
            st.rerun()
        else:
            st.error(f"❌ Submission failed: {insert_resp.data}")

# -----------------------
# CSV Download Block
# -----------------------

def download_block():
    st.subheader("📥 Download All Transactions (CSV)")
    resp = supabase.table("dg_transactions").select("*").order("created_at", desc=True).execute()
    if resp.data:
        df = pd.DataFrame(resp.data)
        st.dataframe(df)
        st.download_button("Download CSV", df.to_csv(index=False), "dg_transactions.csv", "text/csv")
    else:
        st.info("No data available to download.")

# -----------------------
# Last 10 Transactions Block
# -----------------------

def last_10_transactions_block():
    st.subheader("📊 Last 10 Transactions")
    toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
    dg_name = st.selectbox("Select DG", ["DG1", "DG2", "DG3"])

    resp = supabase.table("dg_transactions").select("*").eq("toll_plaza", toll_plaza).eq("dg_name", dg_name).order("created_at", desc=True).limit(10).execute()
    if resp.data:
        df = pd.DataFrame(resp.data)
        st.dataframe(df)
        st.download_button("Download Last 10 CSV", df.to_csv(index=False), "last_10_dg_transactions.csv", "text/csv")
    else:
        st.info("No transactions found for the selection.")

# -----------------------
# Main Runner
# -----------------------

def run():
    st.title("🔌 DG Monitoring Module")
    menu = st.sidebar.radio("Select", ["Admin Block", "User Block", "Download CSV", "View Last 10 Transactions"])

    if menu == "Admin Block":
        admin_block()
    elif menu == "User Block":
        user_block()
    elif menu == "Download CSV":
        download_block()
    elif menu == "View Last 10 Transactions":
        last_10_transactions_block()
