import streamlit as st
import pandas as pd
from datetime import datetime
from supabase_client import get_supabase_client

def show():
    st.header("Customer Database")
    supabase = get_supabase_client()
    
    # 1. Add Customer Form
    with st.expander("Register New Customer"):
        with st.form("add_customer"):
            name = st.text_input("Name")
            phone = st.text_input("Phone Number")
            email = st.text_input("Email (Optional)")
            submit_cust = st.form_submit_button("Add Customer")
            
            if submit_cust and name and phone:
                try:
                    clean_phone = "".join(ch for ch in str(phone) if ch.isdigit())
                    payload = {
                        "name": name,
                        "phone": int(clean_phone) if clean_phone else None,
                        "email": email,
                    }
                    res = supabase.table("customers").insert(payload).execute()
                    if res.data:
                        st.success("Customer Registered!")
                        st.rerun()
                    else:
                        st.error("Failed to register customer.")
                except Exception as e:
                    st.error(f"Error: {e}")

    # 2. Smart Customer Profiles (CRM)
    st.subheader("Customer Profiles & Insights")
    
    try:
        res = supabase.table("customers").select("*").order("name").execute()
        custs = res.data or []
        if custs:
            # Layout: Left for Selector, Right for Details
            c1, c2 = st.columns([1, 2])
            
            with c1:
                st.write("📋 **Customer List**")
                cust_map = {f"{c['name']} ({c.get('phone', '-')})": c for c in custs}
                selected_name = st.radio("Select Customer", list(cust_map.keys()))
                customer = cust_map[selected_name]
                selected_id = str(customer["id"])
            
            with c2:
                st.write("📊 **Detailed Profile**")
                try:
                    tx_res = (
                        supabase.table("transactions")
                        .select("quantity,timestamp,receipt_id,products(name,price)")
                        .eq("customer_id", selected_id)
                        .order("timestamp", desc=True)
                        .execute()
                    )
                    tx_rows = tx_res.data or []

                    st.markdown(f"### {customer['name']}")
                    created_raw = customer.get("created_at") or customer.get("timestamp")
                    if created_raw:
                        try:
                            created_dt = datetime.fromisoformat(str(created_raw).replace("Z", "+00:00"))
                            st.caption(f"Member since: {created_dt.strftime('%b %Y')}")
                        except Exception:
                            st.caption(f"Member since: {created_raw}")

                    total_spent = 0.0
                    by_product = {}
                    last_visit = tx_rows[0]["timestamp"] if tx_rows else None
                    orders = len({row.get("receipt_id") for row in tx_rows if row.get("receipt_id")})
                    for row in tx_rows:
                        product = row.get("products") or {}
                        pname = product.get("name", "Unknown")
                        qty = int(row.get("quantity", 0) or 0)
                        unit_price = float(product.get("price", 0) or 0)
                        total_spent += qty * unit_price
                        by_product[pname] = by_product.get(pname, 0) + qty

                    segment = "Occasional"
                    if orders >= 12:
                        segment = "VIP"
                    elif orders >= 5:
                        segment = "Regular"

                    st.info(f"**Customer Segment:** {segment}")

                    m1, m2, m3 = st.columns(3)
                    m1.metric("Total Spent", f"${total_spent:,.2f}")
                    m2.metric("Orders", orders)
                    m3.metric("Last Visit", str(last_visit).split("T")[0] if last_visit else "Never")
                    
                    st.divider()
                    st.markdown("#### Item Preferences")
                    if by_product:
                        top_items = sorted(by_product.items(), key=lambda x: x[1], reverse=True)[:10]
                        prefs = pd.DataFrame(top_items, columns=["Product", "Qty Bought"])
                        st.dataframe(prefs, hide_index=True, use_container_width=True)
                    else:
                        st.info("No purchase history yet.")
                except Exception as e:
                    st.error(f"Error: {e}")
        else:
            st.info("No customers found.")
    except Exception as e:
        st.error(f"Connection error: {e}")
