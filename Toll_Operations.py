import streamlit as st
import diesel_monitoring_app

def main():
    st.title("🛣️ Toll Plaza Operations")

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
        import eb_meter_reading_app
        eb_meter_reading_app.run()

    elif module == "Highway Reading":
        import highway_reading_app
        highway_reading_app.run()

    elif module == "Inventory Management (Coming Soon)":
        st.info("🛠️ Inventory Management module is under development and will be available soon.")

if __name__ == "__main__":
    main()
