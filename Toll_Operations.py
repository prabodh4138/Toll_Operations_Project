import streamlit as st
import diesel_monitoring_app
import eb_meter_reading_app
import highway_reading_app
 
def main():
    st.title("🛣️ Toll Plaza Operations")
 
    module = st.sidebar.selectbox("Select Module", [
        "DG Monitoring",
        "EB Meter Reading",
        "Highway Meter Reading",
        "Inventory Management (Coming Soon)"
    ])
 
    if module == "DG Monitoring":
        diesel_monitoring_app.run()
    elif module == "EB Meter Reading":
        eb_meter_reading_app.run()
    elif module == "Highway Meter Reading":
        highway_reading_app.run()
    elif module == "Inventory Management (Coming Soon)":
        st.warning("⚠️ This module will be implemented in the next phase.")
 
if __name__ == "__main__":
       main()
 
