import streamlit as st
import requests
import pandas as pd

API_URL = "http://127.0.0.1:8000"

def show():
    st.header("Inventory List")
    try:
        res = requests.get(f"{API_URL}/products/")
        if res.status_code == 200:
            products = res.json()
            if products:
                df = pd.DataFrame(products)
                
                # Reorder columns: ID first, then Name, etc.
                desired_order = ["id", "name", "category", "stock_quantity", "price", "cost", "barcode"]
                # Filter to only ensure columns that actually exist in the data are selected
                cols_to_use = [c for c in desired_order if c in df.columns]
                df = df[cols_to_use]
                
                # Rename columns to be more readable
                df = df.rename(columns={
                    "id": "ID",
                    "name": "Product Name",
                    "category": "Category",
                    "stock_quantity": "Current Stock",
                    "price": "Selling Price ($)",
                    "cost": "Unit Cost ($)",
                    "barcode": "Barcode / SKU"
                })
                
                # Display with hidden index for a cleaner look
                st.dataframe(df, hide_index=True, width='stretch')
            else:
                st.info("No products found.")
        else:
            st.error("Failed to fetch inventory")
    except Exception as e:
        st.error(f"Connection error: {e}")
