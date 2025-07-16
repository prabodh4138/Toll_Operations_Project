import streamlit as st
from supabase import create_client
from datetime import datetime, timedelta
import pandas as pd
import time
 
# -------------------- Supabase Connection --------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
 
# -------------------- Helper Functions --------------------
def get_plaza_barrel_stock(toll_plaza):
    resp = supabase.table("dg_live_status").select("updated_plaza_barrel_stock").eq("toll_plaza", toll_plaza).execute()
    if resp.data and len(resp.data) > 0:
        return resp.data[0]["updated_plaza_barrel_stock"] or 0.0
    else:
        return 0.0
 
def get_opening_status(toll_plaza, dg_name):
    resp = supabase.table("dg_opening_status").select("*").eq("toll_plaza", toll_plaza).eq("dg_name", dg_name).execute()
    if resp.data and len(resp.data) > 0:
        data = resp.data[0]
        return (
            data.get("opening_diesel_stock", 0.0),
            data.get("opening_kwh", 0.0),
            data.get("opening_rh", "00:00")
        )
    else:
        return (0.0, 0.0, "00:00")
 
def calculate_net_rh(opening_rh, closing_rh):
    fmt = "%H:%M"
    tdelta = datetime.strptime(closing_rh, fmt) - datetime.strptime(opening_rh, fmt)
    if tdelta.total_seconds() < 0:
        tdelta += timedelta(days=1)
    hours, remainder = divmod(tdelta.seconds, 3600)
    minutes = remainder // 60
    return f"{hours:02}:{minutes:02}"
 
# -------------------- MAIN FUNCTION --------------------
def run():
    st.title("🔋 Diesel Monitoring - Toll Operations")
 
    menu = ["User Block", "Last 10 Transactions", "Admin Block", "Download CSV"]
    choice = st.sidebar.selectbox("Select Block", menu)
 
    # -------------------- User Block --------------------
    if choice == "User Block":
        st.header("🛠️ User Block - Data Entry")
 
        date = st.date_input("Select Date", datetime.now())
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
        dg_name = st.selectbox("Select DG Name", ["DG1", "DG2"])
 
        plaza_barrel_stock = get_plaza_barrel_stock(toll_plaza)
        opening_diesel_stock, opening_kwh, opening_rh = get_opening_status(toll_plaza, dg_name)
 
st.info(f"**Plaza Barrel Stock (Virtual): {plaza_barrel_stock} L**")
st.info(f"**Opening Diesel Stock (DG): {opening_diesel_stock} L**")
st.info(f"**Opening KWH: {opening_kwh}**")
st.info(f"**Opening RH: {opening_rh}**")
 
        diesel_purchase = st.number_input("Diesel Purchase (L)", min_value=0.0)
        diesel_topup = st.number_input("Diesel Top Up (L)", min_value=0.0)
        updated_plaza_barrel_stock = plaza_barrel_stock + diesel_purchase - diesel_topup
        st.success(f"Updated Plaza Barrel Stock: {updated_plaza_barrel_stock} L")
 
        closing_diesel_stock = st.number_input("Closing Diesel Stock (DG) (L)", min_value=0.0)
        diesel_consumption = max(0, (opening_diesel_stock + diesel_topup - closing_diesel_stock))
        st.success(f"Diesel Consumption: {diesel_consumption} L")
 
        closing_kwh = st.number_input("Closing KWH", min_value=opening_kwh)
        net_kwh = closing_kwh - opening_kwh
        st.success(f"Net KWH: {net_kwh}")
 
        closing_rh = st.text_input("Closing RH (HH:MM)", value="00:00")
        net_rh = calculate_net_rh(opening_rh, closing_rh) if closing_rh != "00:00" else "00:00"
        st.success(f"Net RH: {net_rh}")
 
        maximum_demand = st.number_input("Maximum Demand (kVA)", min_value=0.0)
        remarks = st.text_area("Remarks (optional)")
 
        if st.button("Submit Entry"):
            try:
                supabase.table("dg_transactions").insert({
                    "date": date.isoformat(),
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
                }).execute()
 
                supabase.table("dg_live_status").upsert({
                    "toll_plaza": toll_plaza,
                    "updated_plaza_barrel_stock": updated_plaza_barrel_stock,
                    "last_updated": datetime.utcnow().isoformat()
                }).execute()
 
                st.success("✅ Entry submitted and plaza barrel stock updated.")
                time.sleep(1.5)
                st.experimental_rerun()
            except Exception as e:
                st.error(f"❌ Submission failed: {e}")
 
    # -------------------- Last 10 Transactions --------------------
    elif choice == "Last 10 Transactions":
        st.header("📄 Last 10 Transactions")
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
        dg_name = st.selectbox("Select DG Name", ["DG1", "DG2"])
 
        try:
            resp = supabase.table("dg_transactions").select("*").eq("toll_plaza", toll_plaza).eq("dg_name", dg_name).order("id", desc=True).limit(10).execute()
            df = pd.DataFrame(resp.data)
            st.dataframe(df)
        except Exception as e:
            st.error(f"❌ Unable to fetch transactions: {e}")
 
    # -------------------- Admin Block --------------------
    elif choice == "Admin Block":
        st.header("🔐 Admin Block")
        password = st.text_input("Enter Admin Password", type="password")
        if password == "Sekura@2025":
            st.success("Access Granted.")
            admin_choice = st.selectbox("Select Action", ["Plaza Barrel Initialization", "DG Initialization"])
 
            if admin_choice == "Plaza Barrel Initialization":
                toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
                init_barrel_stock = st.number_input("Plaza Barrel Stock (L)", min_value=0.0)
                if st.button("Save Plaza Barrel Stock"):
                    try:
                        supabase.table("dg_live_status").upsert({
                            "toll_plaza": toll_plaza,
                            "updated_plaza_barrel_stock": init_barrel_stock,
                            "last_updated": datetime.utcnow().isoformat()
                        }).execute()
                        st.success("✅ Plaza barrel stock initialized.")
                        time.sleep(1.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Initialization failed: {e}")
 
            elif admin_choice == "DG Initialization":
                toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
                dg_name = st.selectbox("Select DG Name", ["DG1", "DG2"])
                opening_diesel_stock = st.number_input("Opening Diesel Stock (L)", min_value=0.0)
                opening_kwh = st.number_input("Opening KWH", min_value=0.0)
                opening_rh = st.text_input("Opening RH (HH:MM)", value="00:00")
                if st.button("Save DG Initialization"):
                    try:
                        supabase.table("dg_opening_status").upsert({
                            "toll_plaza": toll_plaza,
                            "dg_name": dg_name,
                            "opening_diesel_stock": opening_diesel_stock,
                            "opening_kwh": opening_kwh,
                            "opening_rh": opening_rh,
                            "last_updated": datetime.utcnow().isoformat()
                        }).execute()
                        st.success("✅ DG initialization saved.")
                        time.sleep(1.5)
                        st.experimental_rerun()
                    except Exception as e:
                        st.error(f"❌ Initialization failed: {e}")
        else:
            if password != "":
                st.error("Incorrect password. Please try again.")
 
    # -------------------- CSV Download --------------------
    elif choice == "Download CSV":
        st.header("📥 Download CSV Records")
        from_date = st.date_input("From Date", datetime.now() - timedelta(days=7))
        to_date = st.date_input("To Date", datetime.now())
 
        if st.button("Download CSV"):
            try:
                resp = supabase.table("dg_transactions").select("*").gte("date", from_date.isoformat()).lte("date", to_date.isoformat()).execute()
                df = pd.DataFrame(resp.data)
                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button("📥 Download CSV", csv, "dg_transactions.csv", "text/csv")
            except Exception as e:
                st.error(f"❌ Unable to download CSV: {e}")
 
# Allow direct run testing if needed:
if __name__ == "__main__":
    run()
