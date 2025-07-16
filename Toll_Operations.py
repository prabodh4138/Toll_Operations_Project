import streamlit as st
 
# Import your modular apps
import diesel_monitoring_app
import eb_meter_reading_app
import highway_reading_app
# Future: import inventory_management_app
 
def main():
    st.set_page_config(page_title="Toll Plaza Operations", page_icon="🛣️", layout="wide")
    st.title("🛣️ Toll Plaza Operations Dashboard")
 
    module = st.sidebar.selectbox(
        "Select Module",
        [
            "DG Monitoring",
            "EB Meter Reading",
            "Highway Reading",
            "Inventory Management (Coming Soon)"
        ]
    )
 
    if module == "DG Monitoring":
        diesel_monitoring_app.run()
 
    elif module == "EB Meter Reading":
        eb_meter_reading_app.run()
 
    elif module == "Highway Reading":
        highway_reading_app.run()
 
    elif module == "Inventory Management (Coming Soon)":
        st.info("🛠️ This module will be added soon.")
 
if __name__ == "__main__":
    main()
 
