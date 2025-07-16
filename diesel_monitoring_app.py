import streamlit as st
from supabase import create_client
from datetime import datetime
import pandas as pd
import os
 
# Initialize Supabase
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
 
# RH parser
def parse_rh(rh_str):
    try:
        parts = rh_str.strip().split(":")
        if len(parts) != 2:
            return None
        hours = int(parts[0])
        minutes = int(parts[1])
        if minutes >= 60 or hours < 0 or minutes < 0:
            return None
        return hours * 60 + minutes
    except:
        return None
 
# Calculate net RH
def calculate_net_rh(opening_rh, closing_rh):
    open_min = parse_rh(opening_rh)
    close_min = parse_rh(closing_rh)
    if open_min is None or close_min is None:
        return None, "❌ Invalid RH format. Use hh:mm."
    if close_min < open_min:
        return None, "❌ Closing RH must be ≥ Opening RH."
    net_min = close_min - open_min
    net_hours = net_min // 60
    net_minutes = net_min % 60
    return f"{net_hours}:{net_minutes:02d}", None
 
def run():
    st.title("🔋 DG Monitoring Module")
 
    menu = ["User Entry", "Admin Initialization", "Last 10 Transactions"]
    choice = st.sidebar.radio("Select Action", menu)
 
    if choice == "Admin Initialization":
        st.header("🛠️ Admin Initialization")
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
        dg_name = st.selectbox("Select DG", ["DG1", "DG2"])
 
        opening_diesel_stock = st.number_input("Opening Diesel Stock (L)", min_value=0.0)
        opening_kwh = st.number_input("Opening KWH", min_value=0.0)
        opening_rh = st.text_input("Opening RH (hh:mm)")
 
        if st.button("Initialize"):
            if parse_rh(opening_rh) is None:
                st.error("❌ Invalid RH format. Use hh:mm.")
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
                st.success("✅ Initialization saved successfully.")
                st.rerun()
            else:
                st.error(f"❌ Initialization failed: {resp.status_code} {resp.status_text}")
 
    elif choice == "User Entry":
        st.header("📝 DG Entry Form")
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
        dg_name = st.selectbox("Select DG", ["DG1", "DG2"])
 
        # Fetch opening data
        resp = supabase.table("dg_opening_status").select("*").eq("toll_plaza", toll_plaza).eq("dg_name", dg_name).execute()
        if resp.data and len(resp.data) > 0:
            opening_data = resp.data[0]
            opening_diesel_stock = opening_data.get("opening_diesel_stock", 0)
            opening_kwh = opening_data.get("opening_kwh", 0)
            opening_rh = opening_data.get("opening_rh", "0:00")
        else:
            st.warning("⚠️ Please initialize this DG first in the Admin block.")
            return
 
st.info(f"Opening Diesel Stock: {opening_diesel_stock} L")
st.info(f"Opening KWH: {opening_kwh}")
st.info(f"Opening RH: {opening_rh}")
 
        diesel_purchase = st.number_input("Diesel Purchase (L)", min_value=0.0, value=0.0)
        diesel_topup = st.number_input("Diesel Topup (L)", min_value=0.0, value=0.0)
 
        closing_diesel_stock = st.number_input("Closing Diesel Stock (L)", min_value=0.0)
        if closing_diesel_stock > (opening_diesel_stock + diesel_topup):
            st.error("❌ Closing Diesel Stock cannot exceed (Opening + Topup).")
            return
 
        diesel_consumption = (opening_diesel_stock + diesel_topup) - closing_diesel_stock
 
        closing_kwh = st.number_input("Closing KWH", min_value=0.0)
        if closing_kwh < opening_kwh:
            st.error("❌ Closing KWH cannot be less than Opening KWH.")
            return
        net_kwh = closing_kwh - opening_kwh
 
        closing_rh = st.text_input("Closing RH (hh:mm)")
        net_rh, rh_error = calculate_net_rh(opening_rh, closing_rh)
        if rh_error:
            st.error(rh_error)
            return
 
        maximum_demand = st.number_input("Maximum Demand (kVA)", min_value=0.0)
        remarks = st.text_area("Remarks (optional)")
 
        date = datetime.now().strftime("%Y-%m-%d")
 
        if st.button("Submit Entry"):
            data = {
                "date": date,
                "toll_plaza": toll_plaza,
                "dg_name": dg_name,
                "diesel_purchase": diesel_purchase,
                "diesel_topup": diesel_topup,
                "updated_plaza_barrel_stock": None,  # future enhancement
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
            resp = supabase.table("dg_transactions").insert(data).execute()
            if resp.status_code in [200, 201]:
                st.success("✅ Entry submitted successfully.")
                st.rerun()
            else:
                st.error(f"❌ Submission failed: {resp.status_code} {resp.status_text}")
 
    elif choice == "Last 10 Transactions":
        st.header("📄 Last 10 Transactions")
        resp = supabase.table("dg_transactions").select("*").order("id", desc=True).limit(10).execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            st.dataframe(df, use_container_width=True)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download CSV", data=csv, file_name="dg_transactions.csv", mime="text/csv")
        else:
st.info("ℹ️ No transactions found.")
 
if __name__ == "__main__":
    run()
