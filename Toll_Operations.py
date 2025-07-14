import streamlit as st
 
# Import your modules here
import diesel_monitoring_app
# import eb_meter_reading_app
# import highway_reading_app
# import inventory_management_app
 
def main():
    st.set_page_config(page_title="🛣️ Toll Plaza Operations", layout="wide")
    st.title("🛣️ Toll Plaza Operations Modular App")
 
    module = st.sidebar.selectbox(
        "📂 Select Module",
        [
            "DG Monitoring",
            "EB Meter Reading (Coming Soon)",
            "Highway Reading (Coming Soon)",
            "Inventory Management (Coming Soon)"
        ]
    )
 
    if module == "DG Monitoring":
diesel_monitoring_app.run()
 
    elif module == "EB Meter Reading (Coming Soon)":
st.info("🛠️ EB Meter Reading Module will be added soon.")
 
    elif module == "Highway Reading (Coming Soon)":
st.info("🛠️ Highway Reading Module will be added soon.")
 
    elif module == "Inventory Management (Coming Soon)":
st.info("🛠️ Inventory Management Module will be added soon.")
 
if __name__ == "__main__":
    main()
