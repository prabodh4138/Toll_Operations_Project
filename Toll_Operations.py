import streamlit as st
import diesel_monitoring_app
 
def main():
    st.title("🛣️ Toll Plaza Operations")
 
    module = st.sidebar.selectbox(
        "Select Module",
        [
            "DG Monitoring",
            "EB Meter Reading (Coming Soon)",
            "Highway Meter Reading (Coming Soon)",
            "Inventory Management (Coming Soon)"
        ]
    )
 
    if module == "DG Monitoring":
        diesel_monitoring_app.run()
 
    # elif module == "EB Meter Reading (Coming Soon)":
    #     import eb_meter_reading_app
    #     eb_meter_reading_app.run()
 
    # elif module == "Highway Meter Reading (Coming Soon)":
    #     import highway_reading_app
    #     highway_reading_app.run()
 
    # elif module == "Inventory Management (Coming Soon)":
    #     import inventory_management_app
    #     inventory_management_app.run()
 
if __name__ == "__main__":
    main()
 
