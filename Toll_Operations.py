import streamlit as st
import diesel_monitoring_app
import eb_meter_reading_app
import highway_reading_app
import inventory_management_app
def main():
    st.title("🛣️ Sekura Toll Plaza Operations Dashboard")
 
    module = st.sidebar.selectbox(
        "Select Module",
        [
            "DG Monitoring",
            "EB Meter Reading",
            "Highway Meter Reading",
            "Inventory Management"
        ]
    )
 
    if module == "DG Monitoring":
        diesel_monitoring_app.run()
 
    elif module == "EB Meter Reading":
        eb_meter_reading_app.run()
 
    elif module == "Highway Meter Reading":
        highway_reading_app.run()
 
    elif module == "Inventory Management":
        inventory_management_app.run()
 
if __name__ == "__main__":
    main()
 
