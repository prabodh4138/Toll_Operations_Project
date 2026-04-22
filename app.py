import streamlit as st
from inventory_management import inventory_app

st.set_page_config(page_title="Toll Operations", layout="wide")

st.sidebar.title("🚧 Toll Operations")

menu = st.sidebar.selectbox(
    "Select Module",
    ["Inventory Management"]
)

if menu == "Inventory Management":
    inventory_app()