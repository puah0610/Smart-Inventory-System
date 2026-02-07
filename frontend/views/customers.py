import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import API_URL

def show():
    st.header("Customer Database")
    
    # 1. Add Customer Form
    with st.expander("Register New Customer"):
        with st.form("add_customer"):
            name = st.text_input("Name")
            phone = st.text_input("Phone Number")
            email = st.text_input("Email (Optional)")
            submit_cust = st.form_submit_button("Add Customer")
            
            if submit_cust and name and phone:
                payload = {"name": name, "phone": phone, "email": email}
                try:
                    res = requests.post(f"{API_URL}/products/customers/", json=payload)
                    if res.status_code == 200:
                        st.success("Customer Registered!")
                        st.rerun()
                    else:
                        st.error(res.text)
                except Exception as e:
                    st.error(f"Error: {e}")

    # 2. Smart Customer Profiles (CRM)
    st.subheader("Customer Profiles & Insights")
    
    try:
        res = requests.get(f"{API_URL}/products/customers/")
        if res.status_code == 200:
            custs = res.json()
            if custs:
                # Layout: Left for Selector, Right for Details
                c1, c2 = st.columns([1, 2])
                
                with c1:
                    st.write("📋 **Customer List**")
                    cust_map = {f"{c['name']} ({c['phone']})": c['id'] for c in custs}
                    selected_name = st.radio("Select Customer", list(cust_map.keys()))
                    selected_id = cust_map[selected_name]
                
                with c2:
                    st.write("📊 **Detailed Profile**")
                    try:
                        p_res = requests.get(f"{API_URL}/products/customers/id/{selected_id}/profile")
                        if p_res.status_code == 200:
                            profile = p_res.json()
                            customer = profile['customer']
                            
                            st.markdown(f"### {customer['name']}")
                            st.caption(f"Member since: {datetime.fromisoformat(customer['created_at']).strftime('%b %Y')}")
                            
                            # Display Segment prominently
                            st.info(f"**Customer Segment:** {profile['segment']}")

                            m1, m2, m3 = st.columns(3)
                            m1.metric("Total Spent", f"${profile['total_spent']:,.2f}")
                            m2.metric("Orders", profile['visit_count'])
                            m3.metric("Last Visit", profile['last_visit'].split("T")[0] if profile['last_visit'] else "Never")
                            
                            st.divider()
                            st.markdown("#### Item Preferences")
                            if profile['top_items']:
                                prefs = pd.DataFrame(profile['top_items']).rename(columns={"name": "Product", "qty": "Qty Bought"})
                                st.dataframe(prefs, hide_index=True)
                            else:
                                st.info("No purchase history yet.")
                            
                        else:
                            st.error("Could not load profile.")
                    except Exception as e:
                        st.error(f"Error: {e}")
            else:
                st.info("No customers found.")
        else:
            st.error("Failed to fetch customers.")
    except Exception as e:
        st.error(f"Connection error: {e}")
