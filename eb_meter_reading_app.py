import streamlit as st
import sqlite3
from datetime import datetime
import pandas as pd
 
def run():
    st.title("⚡ EB Meter Reading - Toll Operations")
 
    conn = sqlite3.connect("toll_operations.db", check_same_thread=False)
    c = conn.cursor()
 
    # Create tables if not exist
    c.execute('''
        CREATE TABLE IF NOT EXISTS eb_meter_readings (
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
        )
    ''')
    conn.commit()
 
    menu = ["User Block", "Last 10 Readings", "Download CSV"]
    choice = st.sidebar.selectbox("Select EB Meter Block", menu)
 
    if choice == "User Block":
        st.subheader("📥 Enter EB Meter Reading")
 
        date = st.date_input("Select Date", datetime.now()).strftime("%d-%m-%Y")
        toll_plaza = st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"])
 
        consumer_dict = {
            "TP01": "416000000110",
            "TP02": "812001020208",
            "TP03": "813000000281"
        }
        consumer_number = consumer_dict[toll_plaza]
        st.info(f"Auto-fetched Consumer Number: **{consumer_number}**")
 
        # Fetch last closing values for dynamic opening
        c.execute('''SELECT closing_kwh, closing_kvah, closing_kvarh FROM eb_meter_readings
                     WHERE toll_plaza=? ORDER BY id DESC LIMIT 1''', (toll_plaza,))
        last = c.fetchone()
        if last:
            opening_kwh, opening_kvah, opening_kvarh = last
        else:
            opening_kwh = opening_kvah = opening_kvarh = 0.0
 
        st.write(f"**Opening KWH:** {opening_kwh}")
        st.write(f"**Opening KVAH:** {opening_kvah}")
        st.write(f"**Opening KVARH:** {opening_kvarh}")
 
        closing_kwh = st.number_input("Closing KWH", min_value=opening_kwh)
        net_kwh = closing_kwh - opening_kwh
 
        closing_kvah = st.number_input("Closing KVAH", min_value=opening_kvah)
        net_kvah = closing_kvah - opening_kvah
 
        closing_kvarh = st.number_input("Closing KVARH", min_value=opening_kvarh)
        net_kvarh = closing_kvarh - opening_kvarh
 
        pf = st.number_input("Power Factor (0-1)", min_value=0.0, max_value=1.0, format="%.2f")
        md = st.number_input("Maximum Demand (kVA)", min_value=0.0, format="%.2f")
        remarks = st.text_area("Remarks (optional)")
 
        if st.button("Submit Reading"):
            try:
                c.execute('''
                    INSERT INTO eb_meter_readings
                    (date, toll_plaza, consumer_number, opening_kwh, closing_kwh, net_kwh,
                     opening_kvah, closing_kvah, net_kvah, opening_kvarh, closing_kvarh,
                     net_kvarh, pf, md, remarks)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    date, toll_plaza, consumer_number, opening_kwh, closing_kwh, net_kwh,
                    opening_kvah, closing_kvah, net_kvah, opening_kvarh, closing_kvarh,
                    net_kvarh, pf, md, remarks
                ))
                conn.commit()
                st.success("✅ EB Meter Reading submitted and stored successfully.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error: {e}")
 
    elif choice == "Last 10 Readings":
        st.subheader("📄 Last 10 EB Meter Readings")
        df = pd.read_sql_query(
            "SELECT * FROM eb_meter_readings WHERE toll_plaza=? ORDER BY id DESC LIMIT 10",
            conn, params=(st.selectbox("Select Toll Plaza", ["TP01", "TP02", "TP03"]),)
        )
        st.dataframe(df)
 
    elif choice == "Download CSV":
        st.subheader("📥 Download EB Meter CSV Records")
        df = pd.read_sql_query("SELECT * FROM eb_meter_readings", conn)
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Download EB Meter Readings CSV", csv, "eb_meter_readings.csv", "text/csv")
 
