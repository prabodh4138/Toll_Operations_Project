import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import datetime

# Initialize Supabase
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Helpers for RH parsing and validation
def parse_rh(rh_str):
    try:
        hours, minutes = map(int, rh_str.split(":"))
        return hours * 60 + minutes
    except:
        return None

def format_rh(total_minutes):
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{int(hours)}:{int(minutes):02d}"

def calculate_net_rh(opening_rh_str, closing_rh_str):
    opening_minutes = parse_rh(opening_rh_str)
    closing_minutes = parse_rh(closing_rh_str)

    if opening_minutes is None or closing_minutes is None:
        return None, "Incorrect RH format. Use HH:MM."

    if closing_minutes < opening_minutes:
        return None, "Closing RH must be greater than or equal to Opening RH."

    net_minutes = closing_minutes - opening_minutes
    return format_rh(net_minutes), None

# Admin Block
def admin_block():
    st.subheader("🛠️ Admin Initialization")

    toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
    dg_name = st.selectbox("Select DG", ["DG1", "DG2", "DG3"])

    opening_diesel_stock = st.number_input("Opening Diesel Stock (L)", min_value=0.0, format="%.2f")
    opening_kwh = st.number_input("Opening KWH", min_value=0.0, format="%.2f")
    opening_rh = st.text_input("Opening RH (HH:MM)")

    if st.button("Initialize"):
        # Validate RH
        if parse_rh(opening_rh) is None:
            st.error("Incorrect RH format. Use HH:MM.")
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
            st.success("DG initialized successfully.")
            st.experimental_rerun()
        else:
            st.error(f"Initialization failed: {resp.data}")

# User Block
def user_block():
    st.subheader("📝 DG Entry Form")

    toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
    dg_name = st.selectbox("Select DG", ["DG1", "DG2", "DG3"])
    date = st.date_input("Date", datetime.today())

    diesel_purchase = st.number_input("Diesel Purchase (L)", min_value=0.0, format="%.2f")
    diesel_topup = st.number_input("Diesel Topup from Barrel (L)", min_value=0.0, format="%.2f")

    # Fetch current barrel stock
    barrel_resp = supabase.table("dg_live_status").select("*").eq("toll_plaza", toll_plaza).execute()
    plaza_barrel_stock = barrel_resp.data[0]['updated_plaza_barrel_stock'] if barrel_resp.data else 0
    st.info(f"Current Plaza Barrel Stock: {plaza_barrel_stock} L")

    closing_diesel_stock = st.number_input("Closing Diesel Stock (L)", min_value=0.0, format="%.2f")
    closing_kwh = st.number_input("Closing KWH", min_value=0.0, format="%.2f")
    closing_rh = st.text_input("Closing RH (HH:MM)")
    maximum_demand = st.number_input("Maximum Demand (kVA)", min_value=0.0, format="%.2f")
    remarks = st.text_area("Remarks")

    if st.button("Submit Entry"):
        # Fetch Opening Data
        open_resp = supabase.table("dg_opening_status").select("*").eq("toll_plaza", toll_plaza).eq("dg_name", dg_name).execute()
        if not open_resp.data:
            st.error("Please initialize DG data first in Admin Block.")
            return

        opening_data = open_resp.data[0]
        opening_diesel_stock = opening_data["opening_diesel_stock"]
        opening_kwh = opening_data["opening_kwh"]
        opening_rh = opening_data["opening_rh"]

        # RH Validation and Calculation
        net_rh, error_msg = calculate_net_rh(opening_rh, closing_rh)
        if error_msg:
            st.error(error_msg)
            return

        # Net KWH Calculation
        net_kwh = closing_kwh - opening_kwh
        if net_kwh < 0:
            st.error("Closing KWH must be greater than or equal to Opening KWH.")
            return

        # Diesel Validation
        max_allowed_closing_stock = opening_diesel_stock + diesel_topup
        if closing_diesel_stock > max_allowed_closing_stock:
            st.error("Closing Diesel Stock cannot exceed Opening + Topup.")
            return

        updated_plaza_barrel_stock = plaza_barrel_stock - diesel_topup

        # Insert Transaction
        data = {
            "date": date.strftime("%Y-%m-%d"),
            "toll_plaza": toll_plaza,
            "dg_name": dg_name,
            "diesel_purchase": diesel_purchase,
            "diesel_topup": diesel_topup,
            "updated_plaza_barrel_stock": updated_plaza_barrel_stock,
            "opening_diesel_stock": opening_diesel_stock,
            "closing_diesel_stock": closing_diesel_stock,
            "diesel_consumption": opening_diesel_stock + diesel_topup - closing_diesel_stock,
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

        # Update Barrel Stock
        supabase.table("dg_live_status").upsert({
            "toll_plaza": toll_plaza,
            "updated_plaza_barrel_stock": updated_plaza_barrel_stock
        }).execute()

        # Update Opening Status for next cycle
        supabase.table("dg_opening_status").upsert({
            "toll_plaza": toll_plaza,
            "dg_name": dg_name,
            "opening_diesel_stock": closing_diesel_stock,
            "opening_kwh": closing_kwh,
            "opening_rh": closing_rh
        }).execute()

        if insert_resp.status_code in [200, 201]:
            st.success("Entry submitted successfully.")
            st.experimental_rerun()
        else:
            st.error(f"Submission failed: {insert_resp.data}")

# CSV Download Block
def download_block():
    st.subheader("📥 Download DG Transactions CSV")
    resp = supabase.table("dg_transactions").select("*").execute()
    if resp.data:
        df = pd.DataFrame(resp.data)
        st.dataframe(df)
        st.download_button("Download CSV", df.to_csv(index=False), file_name="dg_transactions.csv", mime="text/csv")
    else:
        st.info("No data available for download.")

# Last 10 Transactions Block
def last_10_transactions_block():
    st.subheader("🔍 Last 10 DG Transactions")

    toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
    dg_name = st.selectbox("Select DG", ["DG1", "DG2", "DG3"])

    resp = supabase.table("dg_transactions").select("*").eq("toll_plaza", toll_plaza).eq("dg_name", dg_name).order("created_at", desc=True).limit(10).execute()

    if resp.data:
        df = pd.DataFrame(resp.data)
        st.dataframe(df)
        st.download_button("Download Last 10 as CSV", df.to_csv(index=False), file_name="last_10_dg_transactions.csv", mime="text/csv")
    else:
        st.info("No transactions found for this selection.")

# Run launcher
def run():
    st.title("🔌 DG Monitoring Module")
    option = st.sidebar.radio("Select Option", ["Admin Block", "User Block", "Download CSV", "View Last 10 Transactions"])

    if option == "Admin Block":
        admin_block()
    elif option == "User Block":
        user_block()
    elif option == "Download CSV":
        download_block()
    elif option == "View Last 10 Transactions":
        last_10_transactions_block()
