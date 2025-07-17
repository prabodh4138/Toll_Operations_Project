import streamlit as st
from supabase import create_client
from datetime import datetime
import pandas as pd
import os
 
# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
 
# RH Utilities
def parse_rh(rh_str):
    try:
        parts = rh_str.strip().split(":")
        if len(parts) != 2:
            return None
        hours = int(parts[0])
        minutes = int(parts[1])
        if not (0 <= minutes < 60):
            return None
        return hours * 60 + minutes
    except:
        return None
 
def minutes_to_rh(mins):
    hours = mins // 60
    minutes = mins % 60
    return f"{hours}:{minutes:02d}"
 
def calculate_net_rh(opening_rh, closing_rh):
    open_min = parse_rh(opening_rh)
    close_min = parse_rh(closing_rh)
    if open_min is None or close_min is None:
        return None, "❌ Invalid RH format. Use hh:mm."
    if close_min < open_min:
        return None, "❌ Closing RH must be ≥ Opening RH."
    net_min = close_min - open_min
    return minutes_to_rh(net_min), None
 
def run():
    st.title("⚡ DG Monitoring Module")
 
    menu = ["User Entry", "Admin Initialization", "Last 10 Transactions"]
    choice = st.sidebar.selectbox("Select Action", menu)
 
    if choice == "Admin Initialization":
        st.header("🛠️ Admin Initialization")
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
        dg_name = st.selectbox("Select DG", ["DG1", "DG2"])
        opening_diesel_stock = st.number_input("Opening Diesel Stock (L)", min_value=0.0)
        opening_kwh = st.number_input("Opening KWH", min_value=0.0)
        opening_rh = st.text_input("Opening RH (hh:mm)", placeholder="e.g., 4435:12")
 
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
            if resp.data:
                st.success("✅ Initialization saved.")
                st.rerun()
            else:
                st.error("❌ Initialization failed.")
 
    elif choice == "User Entry":
        st.header("📝 User Entry")
 
        # Date Picker displayed FIRST
        date = st.date_input("Select Entry Date", value=datetime.now()).strftime("%Y-%m-%d")
 
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
        dg_name = st.selectbox("Select DG", ["DG1", "DG2"])
 
        # Fetch Opening Parameters
        open_resp = supabase.table("dg_opening_status").select("*").eq("toll_plaza", toll_plaza).eq("dg_name", dg_name).execute()
        if not open_resp.data:
            st.error("❌ Opening data not initialized for this DG and Plaza.")
            return
 
        open_data = open_resp.data[0]
        opening_diesel_stock = open_data.get("opening_diesel_stock", 0.0)
        opening_kwh = open_data.get("opening_kwh", 0.0)
        opening_rh = open_data.get("opening_rh", "0:00")
 
        st.info(f"🔹 **Opening Diesel Stock:** {opening_diesel_stock} L")
        st.info(f"🔹 **Opening KWH:** {opening_kwh}")
        st.info(f"🔹 **Opening RH:** {opening_rh}")
 
        # Fetch Current Plaza Barrel Stock
        live_resp = supabase.table("dg_live_status").select("*").eq("toll_plaza", toll_plaza).execute()
        current_barrel_stock = live_resp.data[0]['updated_plaza_barrel_stock'] if live_resp.data else 0.0
        st.info(f"🛢️ **Current Plaza Barrel Stock:** {current_barrel_stock} L")
 
        diesel_purchase = st.number_input("Diesel Purchase (L)", min_value=0.0, value=0.0)
        diesel_topup = st.number_input("Diesel Topup to DG (L)", min_value=0.0, value=0.0)
        updated_barrel_stock = current_barrel_stock + diesel_purchase - diesel_topup
        st.info(f"🛢️ **Updated Plaza Barrel Stock after transaction:** {updated_barrel_stock} L")
 
        closing_diesel_stock = st.number_input("Closing Diesel Stock (L)", min_value=0.0, value=0.0)
        max_closing_stock = opening_diesel_stock + diesel_topup
        if closing_diesel_stock > max_closing_stock:
            st.error(f"❌ Closing Diesel Stock cannot exceed Opening + Topup ({max_closing_stock} L).")
            return
 
        diesel_consumption = max_closing_stock - closing_diesel_stock
        st.info(f"🔻 **Diesel Consumption:** {diesel_consumption} L")
 
        closing_kwh = st.number_input("Closing KWH", min_value=0.0, value=0.0)
        if closing_kwh < opening_kwh:
            st.error("❌ Closing KWH must be ≥ Opening KWH.")
            return
 
        net_kwh = closing_kwh - opening_kwh
        st.info(f"⚡ **Net KWH:** {net_kwh}")
 
        closing_rh = st.text_input("Closing RH (hh:mm)", placeholder="e.g., 4436:30")
        net_rh, rh_error = calculate_net_rh(opening_rh, closing_rh)
        if rh_error:
            st.error(rh_error)
            return
        st.info(f"⏱️ **Net RH:** {net_rh}")
 
        maximum_demand = st.number_input("Maximum Demand (kVA)", min_value=0.0, value=0.0)
        remarks = st.text_area("Remarks (optional)", value="")
 
        if st.button("Submit Entry"):
            data = {
                "date": date,
                "toll_plaza": toll_plaza,
                "dg_name": dg_name,
                "diesel_purchase": diesel_purchase,
                "diesel_topup": diesel_topup,
                "updated_plaza_barrel_stock": updated_barrel_stock,
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
            if resp.data:
                # Update dg_live_status for barrel stock
                supabase.table("dg_live_status").upsert({
                    "toll_plaza": toll_plaza,
                    "updated_plaza_barrel_stock": updated_barrel_stock
                }).execute()
 
                # Auto-update opening parameters to closing parameters for next cycle
                supabase.table("dg_opening_status").upsert({
                    "toll_plaza": toll_plaza,
                    "dg_name": dg_name,
                    "opening_diesel_stock": closing_diesel_stock,
                    "opening_kwh": closing_kwh,
                    "opening_rh": closing_rh
                }).execute()
 
                st.success("✅ Entry submitted successfully, opening parameters updated for next cycle.")
                st.rerun()
            else:
                st.error("❌ Submission failed.")
 
    elif choice == "Last 10 Transactions":
        st.header("📜 Last 10 Transactions")
        toll_plaza = st.selectbox("Select Toll Plaza for Transactions", ["TP01", "TP02", "TP03"])
        resp = supabase.table("dg_transactions").select("*").eq("toll_plaza", toll_plaza).order("id", desc=True).limit(10).execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            st.dataframe(df)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(f"📥 Download CSV for {toll_plaza}", data=csv, file_name=f"{toll_plaza}_dg_last10.csv", mime="text/csv")
        else:
            st.info("No transactions found for this Toll Plaza.")
 
if __name__ == "__main__":
    run()
 
