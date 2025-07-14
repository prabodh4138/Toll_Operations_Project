import streamlit as st
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import time

# Database setup
conn = sqlite3.connect("Toll_Operations.db", check_same_thread=False)
c = conn.cursor()

# Create tables if not exist
c.execute('''CREATE TABLE IF NOT EXISTS eb_meter_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    toll_plaza TEXT,
    consumer_number TEXT,
    opening_kwh REAL,
    closing_kwh REAL,
    net_kwh REAL,
    opening_kvah REAL,
    closing_kvah REAL,
    net_kvah REAL,
    opening_kvarh REAL,
    closing_kvarh REAL,
    net_kvarh REAL,
    pf REAL,
    md REAL,
    remarks TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)''')

c.execute('''CREATE TABLE IF NOT EXISTS live_status_eb (
    toll_plaza TEXT PRIMARY KEY,
    opening_kwh REAL,
    opening_kvah REAL,
    opening_kvarh REAL
)''')
conn.commit()

# Helper functions
def get_live_eb_values(toll_plaza):
    c.execute("SELECT opening_kwh, opening_kvah, opening_kvarh FROM live_status_eb WHERE toll_plaza=?", (toll_plaza,))
    row = c.fetchone()
    if row:
        return row
    else:
        return (0.0, 0.0, 0.0)

def update_live_eb_status(toll_plaza, opening_kwh, opening_kvah, opening_kvarh):
    c.execute('''INSERT OR REPLACE INTO live_status_eb
                (toll_plaza, opening_kwh, opening_kvah, opening_kvarh)
                VALUES (?, ?, ?, ?)''',
              (toll_plaza, opening_kwh, opening_kvah, opening_kvarh))
    conn.commit()

# Run function for launcher
def run():
    st.title("⚡ EB Meter Reading - Toll Operations")

    menu = ["User Block", "Last 10 Transactions", "Admin Block"]
    choice = st.sidebar.selectbox("Select Block", menu)

    if choice == "User Block":
        st.header("🔌 User Block - EB Meter Entry")

        date = st.date_input("Select Date", datetime.now()).strftime("%d-%m-%Y")
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])

        consumer_numbers = {
            "TP01": "416000000110",
            "TP02": "812001020208",
            "TP03": "813000000281"
        }
        consumer_number = consumer_numbers[toll_plaza]
        st.info(f"Consumer Number (Auto): {consumer_number}")

        opening_kwh, opening_kvah, opening_kvarh = get_live_eb_values(toll_plaza)
        st.info(f"Opening KWH (Auto): {opening_kwh}")
        st.info(f"Opening KVAH (Auto): {opening_kvah}")
        st.info(f"Opening KVARH (Auto): {opening_kvarh}")

        closing_kwh = st.number_input("Closing KWH", min_value=opening_kwh)
        net_kwh = closing_kwh - opening_kwh
        st.success(f"Net KWH: {net_kwh}")

        closing_kvah = st.number_input("Closing KVAH", min_value=opening_kvah)
        net_kvah = closing_kvah - opening_kvah
        st.success(f"Net KVAH: {net_kvah}")

        closing_kvarh = st.number_input("Closing KVARH", min_value=opening_kvarh)
        net_kvarh = closing_kvarh - opening_kvarh
        st.success(f"Net KVARH: {net_kvarh}")

        pf = st.number_input("Power Factor (0 to 1)", min_value=0.0, max_value=1.0)
        md = st.number_input("Maximum Demand (kVA)", min_value=0.0)
        remarks = st.text_area("Remarks (optional)")

        if st.button("Submit Entry"):
            try:
                c.execute('''INSERT INTO eb_meter_readings (
                                date, toll_plaza, consumer_number,
                                opening_kwh, closing_kwh, net_kwh,
                                opening_kvah, closing_kvah, net_kvah,
                                opening_kvarh, closing_kvarh, net_kvarh,
                                pf, md, remarks
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                          (date, toll_plaza, consumer_number,
                           opening_kwh, closing_kwh, net_kwh,
                           opening_kvah, closing_kvah, net_kvah,
                           opening_kvarh, closing_kvarh, net_kvarh,
                           pf, md, remarks))
                conn.commit()

                # Update live values for the next entry
                update_live_eb_status(toll_plaza, closing_kwh, closing_kvah, closing_kvarh)

                st.success("✅ Data submitted successfully and updated in database.")
                time.sleep(1.5)
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error: {e}")

    elif choice == "Last 10 Transactions":
        st.header("📊 Last 10 EB Meter Transactions")
        toll_plaza = st.selectbox("Filter by Toll Plaza", ["TP01", "TP02", "TP03"])

        df = pd.read_sql_query(
            "SELECT * FROM eb_meter_readings WHERE toll_plaza=? ORDER BY id DESC LIMIT 10",
            conn, params=(toll_plaza,))
        st.dataframe(df)

    elif choice == "Admin Block":
        st.header("🛠️ Admin Block - Initialization")

        password = st.text_input("Enter Admin Password", type="password")

        if password == "Sekura@2025":
            st.success("Access Granted. Initialize EB Meter Parameters.")

            toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"], key="admin_tp_eb")

            init_kwh = st.number_input("Initialize Opening KWH", min_value=0.0)
            init_kvah = st.number_input("Initialize Opening KVAH", min_value=0.0)
            init_kvarh = st.number_input("Initialize Opening KVARH", min_value=0.0)

            if st.button("Save Initialization"):
                try:
                    update_live_eb_status(toll_plaza, init_kwh, init_kvah, init_kvarh)
                    st.success("✅ Initialization saved and synced with User Block.")
                    time.sleep(1.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error: {e}")
        else:
            if password != "":
                st.error("❌ Incorrect password. Please try again.")
