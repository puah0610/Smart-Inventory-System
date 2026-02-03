import streamlit as st
import requests

API_URL = "http://127.0.0.1:8000"

def show():
    st.header("Add New Product")
    with st.form("add_product_form"):
        name = st.text_input("Product Name")
        barcode = st.text_input("Barcode")
        price = st.number_input("Price", min_value=0.0)
        cost = st.number_input("Cost", min_value=0.0)
        category = st.text_input("Category")
        stock = st.number_input("Initial Stock", min_value=0, step=1)
        
        submitted = st.form_submit_button("Add Product")
        if submitted:
            payload = {
                "name": name,
                "barcode": barcode,
                "price": price,
                "cost": cost,
                "category": category,
                "stock_quantity": stock
            }
            try:
                res = requests.post(f"{API_URL}/products/", json=payload)
                if res.status_code == 200:
                    st.success("Product added successfully!")
                else:
                    st.error(f"Error: {res.text}")
            except Exception as e:
                st.error(f"Connection error: {e}")
