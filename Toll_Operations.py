import streamlit as st
import diesel_monitoring_app
import eb_meter_reading_app
 
def main():
    st.title("🛣️ Sekura Toll Plaza Operations Dashboard")
 
    module = st.sidebar.selectbox(
        "Select Module",
        [
            "DG Monitoring",
            "EB Meter Reading",
            "Highway Meter Reading (Coming Soon)",
            "Inventory Management (Coming Soon)"
        ]
    )
 
    if module == "DG Monitoring":
        diesel_monitoring_app.run()
 
    elif module == "EB Meter Reading":
        eb_meter_reading_app.run()
 
    elif module == "Highway Meter Reading (Coming Soon)":
        st.info("🚧 This module is under development and will be available soon.")
 
    elif module == "Inventory Management (Coming Soon)":
        st.info("🚧 This module is under development and will be available soon.")
 
if __name__ == "__main__":
    main()
 
