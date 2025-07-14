# diesel_monitoring_app.py

import streamlit as st
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import time

# ------------------ Database Setup --------------------
conn = sqlite3.connect("diesel_monitoring.db", check_same_thread=False)
c = conn.cursor()

# Create tables if not exist
c.execute('''CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    toll_plaza TEXT,
    dg_name TEXT,
    plaza_barrel_stock REAL,
    diesel_purchase REAL,
    diesel_topup REAL,
    updated_plaza_barrel_stock REAL,
    opening_diesel_stock REAL,
    closing_diesel_stock REAL,
    diesel_consumption REAL,
    opening_kwh REAL,
    closing_kwh REAL,
    net_kwh REAL,
    opening_rh TEXT,
    closing_rh TEXT,
    net_rh TEXT,
    maximum_demand REAL,
    remarks TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)''')

c.execute('''CREATE TABLE IF NOT EXISTS live_status (
    toll_plaza TEXT,
    dg_name TEXT,
    updated_plaza_barrel_stock REAL,
    updated_diesel_stock REAL,
    updated_opening_kwh REAL,
    updated_opening_rh TEXT,
    PRIMARY KEY (toll_plaza, dg_name)
)''')
conn.commit()


# ---------------- Helper Functions --------------------
def calculate_net_rh(opening_rh, closing_rh):
    fmt = "%H:%M"
    tdelta = datetime.strptime(closing_rh, fmt) - datetime.strptime(opening_rh, fmt)
    if tdelta.total_seconds() < 0:
        tdelta += timedelta(days=1)
    hours, remainder = divmod(tdelta.seconds, 3600)
    minutes = remainder // 60
    return f"{hours:02}:{minutes:02}"


def get_live_values(toll_plaza, dg_name):
    c.execute(
        "SELECT updated_plaza_barrel_stock, updated_diesel_stock, updated_opening_kwh, updated_opening_rh FROM live_status WHERE toll_plaza=? AND dg_name=?",
        (toll_plaza, dg_name))
    row = c.fetchone()
    if row:
        return row
    else:
        return (0.0, 0.0, 0.0, "00:00")


def update_live_status(toll_plaza, dg_name, barrel_stock, diesel_stock, opening_kwh, opening_rh):
    c.execute('''INSERT OR REPLACE INTO live_status
                (toll_plaza, dg_name, updated_plaza_barrel_stock, updated_diesel_stock, updated_opening_kwh, updated_opening_rh)
                VALUES (?, ?, ?, ?, ?, ?)''',
              (toll_plaza, dg_name, barrel_stock, diesel_stock, opening_kwh, opening_rh))
    conn.commit()


# ---------------- Core Application Wrapped in run() --------------------
def run():
    st.title("🚩 Diesel Monitoring App - Toll Operations")

    menu = ["User Block", "Last 10 Transactions", "Admin Block", "Download CSV"]
    choice = st.sidebar.selectbox("Select Block", menu)

    # User Block
    if choice == "User Block":
        st.header("🛠️ User Block - Data Entry")

        date = st.date_input("Select Date", datetime.now()).strftime("%d-%m-%Y")
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
        dg_name = st.selectbox("Select DG Name", ["DG1", "DG2"])

        barrel_stock, diesel_stock, opening_kwh, opening_rh = get_live_values(toll_plaza, dg_name)

        st.info(f"**Plaza Barrel Stock (Virtual): {barrel_stock} L**")
        st.info(f"**Opening Diesel Stock at DG (Virtual): {diesel_stock} L**")
        st.info(f"**Opening KWH (Virtual): {opening_kwh}**")
        st.info(f"**Opening RH (Virtual): {opening_rh}**")

        diesel_purchase = st.number_input("Diesel Purchase (L)", min_value=0.0, value=0.0)
        diesel_topup = st.number_input("Diesel Top Up (L)", min_value=0.0, value=0.0)
        updated_barrel_stock = barrel_stock + diesel_purchase - diesel_topup
        st.success(f"Updated Plaza Barrel Stock: {updated_barrel_stock} L")

        closing_diesel_stock = st.number_input("Closing Diesel Stock at DG (L) (Mandatory)", min_value=0.0)
        diesel_consumption = max(0, (diesel_stock + diesel_topup - closing_diesel_stock))
        st.success(f"Diesel Consumption: {diesel_consumption} L")

        closing_kwh = st.number_input("Closing KWH (Must be >= Opening KWH)", min_value=opening_kwh)
        net_kwh = closing_kwh - opening_kwh
        st.success(f"Net KWH: {net_kwh}")

        closing_rh = st.text_input("Closing RH (HH:MM, Must be >= Opening RH)", "00:00")
        if closing_rh != "00:00":
            try:
                net_rh = calculate_net_rh(opening_rh, closing_rh)
                st.success(f"Net RH: {net_rh}")
            except Exception:
                st.warning("Incorrect RH format. Please use HH:MM.")
                net_rh = "00:00"
        else:
            net_rh = "00:00"

        maximum_demand = st.number_input("Maximum Demand (kVA)", min_value=0.0)
        remarks = st.text_area("Remarks (optional)")

        if st.button("Submit Entry"):
            try:
                c.execute('''INSERT INTO transactions (
                    date, toll_plaza, dg_name, plaza_barrel_stock, diesel_purchase, diesel_topup,
                    updated_plaza_barrel_stock, opening_diesel_stock, closing_diesel_stock,
                    diesel_consumption, opening_kwh, closing_kwh, net_kwh,
                    opening_rh, closing_rh, net_rh, maximum_demand, remarks)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                          (date, toll_plaza, dg_name, barrel_stock, diesel_purchase, diesel_topup,
                           updated_barrel_stock, diesel_stock, closing_diesel_stock,
                           diesel_consumption, opening_kwh, closing_kwh, net_kwh,
                           opening_rh, closing_rh, net_rh, maximum_demand, remarks))
                conn.commit()

                update_live_status(toll_plaza, dg_name, updated_barrel_stock, closing_diesel_stock, closing_kwh,
                                   closing_rh)

                st.success("✅ Data submitted successfully and updated in database.")
                time.sleep(1.5)
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error: {e}")

    # Last 10 Transactions
    elif choice == "Last 10 Transactions":
        st.header("📄 Last 10 Transactions")
        toll_plaza = st.selectbox("Filter by Toll Plaza", ["TP01", "TP02", "TP03"])
        dg_name = st.selectbox("Filter by DG Name", ["DG1", "DG2"])

        df = pd.read_sql_query(
            "SELECT * FROM transactions WHERE toll_plaza=? AND dg_name=? ORDER BY id DESC LIMIT 10",
            conn, params=(toll_plaza, dg_name))
        st.dataframe(df)

    # Admin Block
    elif choice == "Admin Block":
        st.header("🔐 Admin Block - Initialization")
        password = st.text_input("Enter Admin Password", type="password")

        if password == "Sekura@2025":
            st.success("Access Granted. You can now initialize data.")

            toll_plaza = st.selectbox("Select Toll Plaza for Initialization", ["TP01", "TP02", "TP03"], key="admin_tp")
            dg_name = st.selectbox("Select DG Name for Initialization", ["DG1", "DG2"], key="admin_dg")

            init_barrel_stock = st.number_input("Initialize Plaza Barrel Stock (L)", min_value=0.0)
            init_diesel_stock = st.number_input("Initialize Opening Diesel Stock at DG (L)", min_value=0.0)
            init_opening_kwh = st.number_input("Initialize Opening KWH", min_value=0.0)
            init_opening_rh = st.text_input("Initialize Opening RH (HH:MM)", "00:00")

            if st.button("Save Initialization"):
                try:
                    update_live_status(toll_plaza, dg_name, init_barrel_stock, init_diesel_stock, init_opening_kwh,
                                       init_opening_rh)
                    st.success("✅ Initialization data saved and synced to user block.")
                    time.sleep(1.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error: {e}")
        else:
            if password != "":
                st.error("Incorrect password. Please try again.")

    # Download CSV
    elif choice == "Download CSV":
        st.header("📥 Download CSV Records")
        from_date = st.date_input("From Date", datetime.now() - timedelta(days=7))
        to_date = st.date_input("To Date", datetime.now())

        if st.button("Download CSV"):
            df = pd.read_sql_query("SELECT * FROM transactions WHERE date BETWEEN ? AND ?",
                                   conn, params=(from_date.strftime("%d-%m-%Y"), to_date.strftime("%d-%m-%Y")))
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Click to Download CSV", csv, "diesel_monitoring_data.csv", "text/csv")


# Allow standalone run
if __name__ == "__main__":
    run()
