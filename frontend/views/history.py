import streamlit as st
import requests
import pandas as pd
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import API_URL

def show():
    st.header("Transaction History")
    
    try:
        # Fetch transactions
        res = requests.get(f"{API_URL}/inventory/transactions")
        if res.status_code == 200:
            transactions = res.json()
            if transactions:
                df = pd.DataFrame(transactions)
                
                # Fetch products to map names (since transaction might only have product_id)
                res_prod = requests.get(f"{API_URL}/products/")
                products_map = {p['id']: p['name'] for p in res_prod.json()} if res_prod.status_code == 200 else {}
                
                df['product_name'] = df['product_id'].map(products_map)
                
                # Clean up display
                display_cols = ["id", "receipt_id", "timestamp", "transaction_type", "product_name", "quantity", "customer_id"]
                cols = [c for c in display_cols if c in df.columns]
                st.dataframe(df[cols].sort_values(by="timestamp", ascending=False), hide_index=True, width='stretch')
            else:
                st.info("No transactions found.")
        else:
            st.error("Failed to load transactions.")
    except Exception as e:
        st.error(f"Error: {e}")
