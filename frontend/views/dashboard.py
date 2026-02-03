import streamlit as st
import requests
import pandas as pd

API_URL = "http://127.0.0.1:8000"

def show():
    st.header("Dashboard & Analytics")
    
    try:
        response = requests.get(f"{API_URL}/analytics/summary")
        if response.status_code == 200:
            data = response.json()
            
            # --- 1. Top Level Metrics ---
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Revenue", f"${data['total_revenue']:,.2f}")
            with col2:
                st.metric("Total Profit", f"${data['total_profit']:,.2f}")
            with col3:
                st.metric("Total Transactions", data['sales_count'])
            
            st.divider()

            # --- AI Insights Section ---
            if "ai_insights" in data and data["ai_insights"]:
                st.subheader("🤖 AI Patterns & Actionable Advice")
                
                # Separate insights by type
                patterns = [i for i in data["ai_insights"] if i['type'] == 'bundle']
                actions = [i for i in data["ai_insights"] if i['type'] in ['promo', 'clearance', 'forecast']]
                
                c_ai1, c_ai2 = st.columns(2)
                
                with c_ai1:
                    st.markdown("#### 🧠 Shopping Patterns")
                    if patterns:
                        for p in patterns:
                            st.info(f"**Trend Detected:** {p['message']} ({p['count']} times)")
                    else:
                        st.caption("No patterns detected yet. Record more sales!")

                with c_ai2:
                    st.markdown("#### 🚀 Recommended Actions")
                    if actions:
                        for a in actions:
                            if a['type'] == 'promo':
                                st.success(a['message'])
                            elif a['type'] == 'forecast':
                                st.error(a['message']) # Use error (red) for stockout alerts
                            else:
                                st.warning(a['message'])
                    else:
                        st.caption("Inventory levels look efficient. No actions needed.")
            
            st.divider()

            # --- 2. Charts & Tables ---
            c1, c2 = st.columns([2, 1])
            
            with c1:
                st.subheader("🏆 Top Selling Products")
                if data['top_selling']:
                    df_top = pd.DataFrame(data['top_selling'])
                    # Simple Bar Chart
                    st.bar_chart(df_top.set_index("name"))
                else:
                    st.info("No sales data yet.")
            
            with c2:
                st.subheader("⚠️ Low Stock Alert")
                if data['low_stock_items']:
                    df_low = pd.DataFrame(data['low_stock_items'])
                    st.dataframe(
                        df_low[['name', 'stock']], 
                        hide_index=True, 
                        width='stretch'
                    )
                    
                    # --- Automated Supplier Alert ---
                    st.markdown("#### Actions")
                    
                    # Generate a draft email setup
                    if st.button("📧 Draft Supplier Email"):
                        # Create an email body
                        items_list = "\n".join([f"- {row['name']} (Current: {row['stock']})" for _, row in df_low.iterrows()])
                        email_body = f"""Dear Supplier,

Please process an urgent restock for the following items which are below safety levels:

{items_list}

Please confirm delivery date.

Best,
Smart Inventory Manager"""
                        
                        st.code(email_body, language="text")
                        st.caption("Copy the text above and send to your supplier.")
                        st.toast("Email Draft Generated!", icon="📝")
                        
                else:
                    st.success("All stock levels healthy!")

            st.divider()

            # --- 3. Demand Forecast (New) ---
            st.subheader("📈 AI Demand Forecast (Next 7 Days)")
            try:
                # Use a unique key for the error to avoid UI weirdness
                with st.spinner("Calculating AI Forecast..."):
                    forecast_res = requests.get(f"{API_URL}/analytics/forecast")
                    if forecast_res.status_code == 200:
                        f_data = forecast_res.json().get("forecast", [])
                        if f_data:
                            df_forecast = pd.DataFrame(f_data)
                            df_forecast['date'] = pd.to_datetime(df_forecast['date'])
                            
                            # Aggregate just in case multiple entries per date
                            df_forecast = df_forecast.groupby('date').sum()
                            
                            # Use Bar Chart for clearer daily separation
                            st.bar_chart(df_forecast, color="#29B5E8")
                            st.caption("Projected sales quantity for the upcoming week.")
                        else:
                            st.info("Record more sales data to unlock AI Forecasting.")
            except Exception as e:
                st.warning(f"Forecast Engine Unavailable: {e}")
            
            st.divider()

            # --- 4. Market Basket Analysis (New) ---
            st.subheader("🛍️ Market Basket Analysis (Product Associations)")
            st.caption("What do customers buy together? (Likelihood based on history)")
            
            try:
                mba_res = requests.get(f"{API_URL}/analytics/market-basket")
                if mba_res.status_code == 200:
                    mba_data = mba_res.json().get("rules", [])
                    if mba_data:
                        # Format for display
                        display_data = []
                        for rule in mba_data:
                            display_data.append({
                                "If Customer Buys...": rule['antecedent'],
                                "They Also Buy...": rule['consequent'],
                                "Chance (%)": f"{rule['confidence']}%",
                                "Occurrences": rule['frequency']
                            })
                        
                        st.dataframe(pd.DataFrame(display_data), use_container_width=True, hide_index=True)
                        
                        top_rule = mba_data[0]
                        st.info(f"💡 **Top Insight:** Customers buying **{top_rule['antecedent']}** are {top_rule['confidence']}% likely to buy **{top_rule['consequent']}**!")
                        
                    else:
                        st.info("No strong purchasing patterns detected yet. Need more diverse transactions.")
            except Exception as e:
                st.warning(f"Market Basket Analysis Unavailable: {e}")

        else:
            st.error("Failed to load analytics.")
    except Exception as e:
        st.error(f"Error connecting to backend: {e}")
