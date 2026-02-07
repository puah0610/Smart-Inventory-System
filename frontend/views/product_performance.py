import streamlit as st
import requests
import pandas as pd
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import API_URL

def show():
    st.header("🔎 Product Performance Deep-Dive")
    st.caption("Analyze profitability, trends, and stock health for individual items.")

    # 1. Product Search
    # Fetch all products for the dropdown
    try:
        res = requests.get(f"{API_URL}/products/")
        if res.status_code == 200:
            products = res.json()
            if not products:
                st.warning("No products found in inventory.")
                return
            
            # Create a searchable dictionary: "Name (Barcode)" -> ID
            prod_map = {f"{p['name']} ({p['barcode']})": p['id'] for p in products}
            
            # Selectbox is searchable by default in Streamlit
            # Using index=None ensures no product is selected by default (User must choose)
            selected_label = st.selectbox(
                "Search Product (Name or Barcode)", 
                options=list(prod_map.keys()),
                index=0
            )
            
            if selected_label:
                selected_id = prod_map[selected_label]
                
                # Fetch Analytics
                analytics_res = requests.get(f"{API_URL}/products/id/{selected_id}/analytics")
                if analytics_res.status_code == 200:
                    data = analytics_res.json()
                    product = data['product']
                    
                    st.divider()
                    
                    # --- Header Section ---
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.subheader(f"📦 {product['name']}")
                        st.text(f"Barcode: {product['barcode']} | Category: {product['category']}")
                    with c2:
                         st.metric("Current Stock", product['stock_quantity'])

                    # --- Key Metrics Row ---
                    m1, m2, m3, m4 = st.columns(4)
                    
                    m1.metric("All-Time Sold", f"{data['total_sold_all_time']} units")
                    m2.metric("All-Time Profit", f"${data['total_profit_all_time']:,.2f}")
                    
                    doc = data['days_of_cover']
                    doc_label = "Infinity" if doc >= 999 else f"{doc} days"
                    
                    # Visual logic for Delta Color (Inverse means RED is UP/High which isn't right here, usually we just use color)
                    # Streamlit metrics don't support custom colors easily without delta.
                    # We will use Delta to show "Sustainability"
                    delta_msg = "Stockout Imminent" if doc < 7 else "Healthy"
                    
                    m3.metric("Days of Cover", doc_label, delta_msg, delta_color="normal" if doc > 7 else "inverse")
                    m4.metric("Avg Daily Sales", f"{data['avg_daily_sales']} / day")

                    # --- Profitability & Health ---
                    st.markdown("#### 📊 Profitability & Health")
                    p1, p2 = st.columns(2)
                    
                    with p1:
                        # Simple Margin Calculation
                        margin = 0
                        if product['price'] > 0:
                            margin = ((product['price'] - product['cost']) / product['price']) * 100
                        
                        st.info(f"**Profit Margin:** {margin:.1f}%")
                        st.caption(f"Cost: ${product['cost']:.2f} | Selling Price: ${product['price']:.2f}")
                        
                        if margin < 20: 
                            st.warning("⚠️ Low margin product.")
                        elif margin > 50:
                            st.success("✅ High margin product.")

                    with p2:
                        # Stock Health Status
                        if doc >= 999:
                            st.error("💀 **Dead Stock Alert**: No sales in last 30 days.")
                        elif doc < 7:
                            st.error("🚨 **Stockout Risk**: Less than 1 week of supply.")
                        elif doc < 14:
                            st.warning("⚠️ **Restock Soon**: 2 weeks supply left.")
                        else:
                            st.success("✅ **Healthy Stock Level**")

                    # --- Chart Section ---
                    st.subheader("📈 Sales Trend (Last 30 Days)")
                    
                    hist_data = data['sales_history']
                    if hist_data:
                        df_hist = pd.DataFrame(hist_data)
                        
                        # Ensure date conversion
                        df_hist['date'] = pd.to_datetime(df_hist['date'])
                        
                        # Create a nice area chart
                        st.area_chart(df_hist.set_index("date")['qty'], color="#29B5E8")
                    else:
                        st.caption("No sales recorded in the last 30 days.")

                else:
                    st.error("Failed to load product analytics.")
                    
        else:
            st.error("Failed to fetch product list.")
            
    except Exception as e:
        st.error(f"Connection Error: {e}")
