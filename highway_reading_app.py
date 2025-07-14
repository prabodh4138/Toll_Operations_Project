import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import time
 
# ---------------- DATABASE SETUP ----------------
conn = sqlite3.connect("Toll_Operations.db", check_same_thread=False)
c = conn.cursor()
 
# Create highway_readings table
c.execute('''CREATE TABLE IF NOT EXISTS highway_readings (
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
    pf REAL,
    md REAL,
    remarks TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)''')
 
# Create live_status_highway table
c.execute('''CREATE TABLE IF NOT EXISTS live_status_highway (
    toll_plaza TEXT,
    consumer_number TEXT,
    opening_kwh REAL,
    opening_kvah REAL,
    PRIMARY KEY (toll_plaza, consumer_number)
)''')
 
# Create consumer_numbers table
c.execute('''CREATE TABLE IF NOT EXISTS consumer_numbers (
    toll_plaza TEXT,
    consumer_number TEXT,
    PRIMARY KEY (toll_plaza, consumer_number)
)''')
 
conn.commit()
 
# ---------------- HELPER FUNCTIONS ----------------
def get_consumer_numbers(toll_plaza):
    c.execute("SELECT consumer_number FROM consumer_numbers WHERE toll_plaza=?", (toll_plaza,))
    return [row[0] for row in c.fetchall()]
 
def get_live_values(toll_plaza, consumer_number):
    c.execute("SELECT opening_kwh, opening_kvah FROM live_status_highway WHERE toll_plaza=? AND consumer_number=?",
              (toll_plaza, consumer_number))
    row = c.fetchone()
    if row:
        return row
    else:
        return (0.0, 0.0)
 
def update_live_status(toll_plaza, consumer_number, opening_kwh, opening_kvah):
    c.execute('''INSERT OR REPLACE INTO live_status_highway 
                 (toll_plaza, consumer_number, opening_kwh, opening_kvah)
                 VALUES (?, ?, ?, ?)''',
              (toll_plaza, consumer_number, opening_kwh, opening_kvah))
    conn.commit()
 
def add_consumer_number(toll_plaza, consumer_number):
    try:
        c.execute("INSERT OR IGNORE INTO consumer_numbers (toll_plaza, consumer_number) VALUES (?, ?)",
                  (toll_plaza, consumer_number))
        conn.commit()
    except Exception as e:
        st.error(f"Error adding consumer number: {e}")
 
# ---------------- MAIN RUN FUNCTION ----------------
def run():
    st.title("🛣️ Highway Energy Meter Reading")
 
    menu = ["User Block", "Last 10 Transactions", "Admin Block", "Download CSV"]
    choice = st.sidebar.selectbox("Select Block", menu)
 
    # ---------- USER BLOCK ----------
    if choice == "User Block":
        st.header("🔹 User Block - Entry")
        date = st.date_input("Select Date", datetime.now()).strftime("%d-%m-%Y")
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
 
        consumer_list = get_consumer_numbers(toll_plaza)
        if not consumer_list:
            st.warning("No consumer numbers available for this Toll Plaza. Contact Admin.")
            return
 
        consumer_number = st.selectbox("Select Consumer Number", consumer_list)
 
        opening_kwh, opening_kvah = get_live_values(toll_plaza, consumer_number)
        st.info(f"**Opening KWH:** {opening_kwh}")
        st.info(f"**Opening KVAH:** {opening_kvah}")
 
        closing_kwh = st.number_input("Closing KWH (≥ Opening KWH)", min_value=opening_kwh)
        net_kwh = closing_kwh - opening_kwh
        st.success(f"Net KWH: {net_kwh}")
 
        closing_kvah = st.number_input("Closing KVAH (≥ Opening KVAH)", min_value=opening_kvah)
        net_kvah = closing_kvah - opening_kvah
        st.success(f"Net KVAH: {net_kvah}")
 
        pf = st.number_input("Power Factor (0 to 1)", min_value=0.0, max_value=1.0)
        md = st.number_input("Maximum Demand (kVA)", min_value=0.0)
        remarks = st.text_area("Remarks (optional)")
 
        if st.button("Submit Entry"):
            try:
                c.execute('''INSERT INTO highway_readings 
                    (date, toll_plaza, consumer_number, opening_kwh, closing_kwh, net_kwh,
                     opening_kvah, closing_kvah, net_kvah, pf, md, remarks)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (date, toll_plaza, consumer_number, opening_kwh, closing_kwh, net_kwh,
                     opening_kvah, closing_kvah, net_kvah, pf, md, remarks))
                conn.commit()
 
                update_live_status(toll_plaza, consumer_number, closing_kwh, closing_kvah)
                st.success("✅ Data submitted successfully and updated in database.")
                time.sleep(1.2)
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
 
    # ---------- LAST 10 TRANSACTIONS ----------
    elif choice == "Last 10 Transactions":
        st.header("📄 Last 10 Transactions")
        toll_plaza = st.selectbox("Filter Toll Plaza", ["TP01", "TP02", "TP03"])
        consumer_list = get_consumer_numbers(toll_plaza)
        if consumer_list:
            consumer_number = st.selectbox("Filter Consumer Number", consumer_list)
            df = pd.read_sql_query(
                "SELECT * FROM highway_readings WHERE toll_plaza=? AND consumer_number=? ORDER BY id DESC LIMIT 10",
                conn, params=(toll_plaza, consumer_number))
            st.dataframe(df)
        else:
            st.warning("No consumer numbers found for this Toll Plaza.")
 
    # ---------- ADMIN BLOCK ----------
    elif choice == "Admin Block":
        st.header("🔐 Admin Block - Initialization")
        password = st.text_input("Enter Admin Password", type="password")
 
        if password == "Sekura@2025":
            st.success("Access Granted.")
 
            toll_plaza = st.selectbox("Toll Plaza", ["TP01", "TP02", "TP03"])
            st.subheader("Add Consumer Number")
            new_consumer = st.text_input("Enter New Consumer Number")
            if st.button("Add Consumer Number"):
                if new_consumer.strip() != "":
                    add_consumer_number(toll_plaza, new_consumer.strip())
                    st.success("Consumer Number added successfully.")
                    time.sleep(1)
                    st.rerun()
 
            consumer_list = get_consumer_numbers(toll_plaza)
            if consumer_list:
                consumer_number = st.selectbox("Select Consumer Number for Initialization", consumer_list)
                init_opening_kwh = st.number_input("Initialize Opening KWH", min_value=0.0)
                init_opening_kvah = st.number_input("Initialize Opening KVAH", min_value=0.0)
                if st.button("Save Initialization"):
                    update_live_status(toll_plaza, consumer_number, init_opening_kwh, init_opening_kvah)
                    st.success("✅ Initialization saved and synced with user block.")
                    time.sleep(1.2)
                    st.rerun()
            else:
                st.warning("Add at least one consumer number first.")
        else:
            if password != "":
                st.error("Incorrect password.")
 
    # ---------- DOWNLOAD CSV ----------
    elif choice == "Download CSV":
        st.header("📥 Download CSV")
        from_date = st.date_input("From Date", datetime.now() - timedelta(days=7))
        to_date = st.date_input("To Date", datetime.now())
 
        if st.button("Download CSV"):
            df = pd.read_sql_query(
                "SELECT * FROM highway_readings WHERE date BETWEEN ? AND ?",
                conn, params=(from_date.strftime("%d-%m-%Y"), to_date.strftime("%d-%m-%Y")))
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Click to Download CSV", csv, "highway_readings.csv", "text/csv")
 
