import streamlit as st
import requests
import pandas as pd
import sqlite3
import time

API_URL = "http://127.0.0.1:8000"
DB_PATH = "backend/smart_inventory.db"

st.title("Smart Inventory Management System")

if "cart" not in st.session_state:
    st.session_state.cart = []

sidebar_option = st.sidebar.selectbox(
    "Navigation",
    ["Dashboard", "POS Terminal", "Restock Items", "Add Product", "Inventory", "Sales History", "Customers"]
)

if sidebar_option == "Dashboard":
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
                        email_subject = "Urgent Restock Order: Inventory Low"
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
                    
        else:
            st.error("Failed to load analytics.")
    except Exception as e:
        st.error(f"Error connecting to backend: {e}")

elif sidebar_option == "POS Terminal":
    st.header("Point of Sale")

    # --- Customer Selection ---
    customer_id = None
    try:
        cust_res = requests.get(f"{API_URL}/products/customers/")
        if cust_res.status_code == 200:
            customers = cust_res.json()
            # Format: "Name (Phone)"
            cust_options = {f"{c['name']} ({c['phone']})": c['id'] for c in customers}
            # Add Guest option
            cust_options["Guest / Walk-in"] = None
            
            selected_cust_label = st.selectbox(
                "👤 Select Customer (Optional)", 
                options=["Guest / Walk-in"] + list(customers and [f"{c['name']} ({c['phone']})" for c in customers] or [])
            )
            
            if selected_cust_label != "Guest / Walk-in":
                customer_id = cust_options.get(selected_cust_label)
    except Exception as e:
        st.warning(f"Could not load customers: {e}")

    # Layout for scanning method
    scan_method = st.radio("Scanning Method:", ["USB Scanner / Keyboard", "Webcam / Camera"], horizontal=True)

    scanned_code = None

    if scan_method == "USB Scanner / Keyboard":
        st.write("👉 **Instructions:** Click inside the box below, then scan the barcode with your gun.")
        # We use a form to capture the "Enter" key press from the scanner
        with st.form("scan_form", clear_on_submit=True):
            scanned_code_input = st.text_input("Scan Barcode", key="barcode_input")
            submitted = st.form_submit_button("Add to Cart")
            if submitted:
                scanned_code = scanned_code_input

    elif scan_method == "Webcam / Camera":
        st.write("👉 **Instructions:** Show the barcode to the camera and capture a photo.")
        try:
            from pyzbar.pyzbar import decode
            from PIL import Image
        except ImportError:
            st.warning("⚠️ Libraries `pyzbar` and `Pillow` are required for camera scanning. Please install them.")
            st.stop()
            
        img_file_buffer = st.camera_input("Take a picture")
        
        if img_file_buffer is not None:
            # To read image file buffer with PIL:
            image = Image.open(img_file_buffer)
            
            # Decode the barcode
            decoded_objects = decode(image)
            
            if decoded_objects:
                for obj in decoded_objects:
                    scanned_code = obj.data.decode("utf-8")
                    st.success(f"Scanned: {scanned_code}")
                    break # Just take the first one
            else:
                st.error("No barcode detected. Try moving the camera closer.")

    # Process the scan (Common logic for both methods)
    if scanned_code:
        # 1. Look up product
        try:
            res = requests.get(f"{API_URL}/products/{scanned_code}")
            if res.status_code == 200:
                product = res.json()
                
                # 2. Add to Session Cart
                # Check if already in cart to increment qty
                found = False
                for item in st.session_state.cart:
                    if item['product_id'] == product['id']:
                        item['quantity'] += 1
                        found = True
                        break
                
                if not found:
                    st.session_state.cart.append({
                        "product_id": product['id'],
                        "name": product['name'],
                        "price": product['price'],
                        "quantity": 1
                    })
                st.toast(f"Added: {product['name']}", icon="✅")
            else:
                st.error(f"Product with barcode '{scanned_code}' not found!")
        except Exception as e:
            st.error(f"Connection error: {e}")

    # Display Cart
    st.subheader("Current Cart")
    if st.session_state.cart:
        # Prepare DataFrame
        cart_df = pd.DataFrame(st.session_state.cart)
        
        # Data Editor (Editable Cart)
        edited_df = st.data_editor(
            cart_df,
            column_config={
                "product_id": st.column_config.NumberColumn("ID", disabled=True),
                "name": st.column_config.TextColumn("Product", disabled=True),
                "price": st.column_config.NumberColumn("Price ($)", disabled=True, format="%.2f"),
                "quantity": st.column_config.NumberColumn("Qty", min_value=1, step=1, required=True),
            },
            num_rows="dynamic", # Allow Deletion
            width='stretch',
            key="cart_editor"
        )
        
        # Sync Validator: Check if user modified the cart
        # We clean the df to match session structure (drop any index/extra cols if they appear)
        current_data = edited_df.to_dict('records')
        
        # Check for changes to trigger sync (Simple comparison)
        has_changes = False
        if len(current_data) != len(st.session_state.cart):
            has_changes = True
        else:
            for i, row in enumerate(current_data):
                if row['quantity'] != st.session_state.cart[i]['quantity']:
                    has_changes = True
                    break
        
        if has_changes:
            st.session_state.cart = current_data
            st.rerun()

        # Calculation Display
        total = sum(item['price'] * item['quantity'] for item in st.session_state.cart)
        st.write(f"**Grand Total: ${total:.2f}**")
        
        col_clear, col_pay = st.columns([1, 2])
        
        with col_clear:
            if st.button("🗑️ Clear Cart"):
                st.session_state.cart = []
                st.rerun()

        with col_pay:
            # Checkout Button
            # Updated to width='stretch' per Streamlit deprecation warning
            if st.button("💳 Complete Sale", type="primary", use_container_width=True): # reverting this one as width='stretch' is not standard for button yet in some versions, sticking to warning for data_editor first. 
                import uuid
                # Generate a single receipt ID for this entire cart
                receipt_id = str(uuid.uuid4())
                
                # Prepare Batch Payload
                batch_items = []
                for item in st.session_state.cart:
                    batch_items.append({
                        "product_id": item['product_id'],
                        "transaction_type": "sale",
                        "quantity": item['quantity']
                    })
                
                payload = {
                    "items": batch_items,
                    "receipt_id": receipt_id,
                    "customer_id": customer_id 
                }
                
                try:
                    # Send EVERYTHING in one go
                    res = requests.post(f"{API_URL}/inventory/batch_transaction", json=payload)
                    
                    if res.status_code == 200:
                        st.toast("Transaction Complete!", icon="🎉")
                        st.session_state.cart = [] # Clear cart
                        time.sleep(1) # Give toast time to show
                        st.rerun()
                    else:
                        # Show specific error from backend (e.g., "Insufficient stock for 'Orange'")
                        error_detail = res.json().get('detail', res.text)
                        st.error(f"Transaction Failed: {error_detail}")
                        
                except Exception as e:
                    st.error(f"Connection Error: {e}")
    else:
        st.info("Cart is empty. Scan items to begin.")
        
        # Helper to show simulation codes
        st.markdown("---")
        st.caption("No physical scanner? Use these codes if you added demo data:")
        st.caption("Run `backend/data/demo_data.sql` or add product manually first.")

elif sidebar_option == "Restock Items":
    st.header("Restock Inventory")
    
    # 1. Fetch all products for a dropdown list (in case they don't have scanner user)
    try:
        res = requests.get(f"{API_URL}/products/")
        if res.status_code == 200:
            products = res.json()
            # Create a lookup dictionary: "Duplicate Name (Barcode)" -> ID
            # Handling potential duplicate names by including barcode
            product_options = {f"{p['name']} (SKU: {p['barcode']})": p for p in products}
        else:
            st.error("Failed to load product list.")
            products = []
            product_options = {}
    except Exception as e:
        st.error(f"Connection error: {e}")
        product_options = {}

    # 2. Input Method
    tab1, tab2 = st.tabs(["Scan Barcode", "Select from List"])
    
    selected_product_id = None
    
    with tab1:
        st.write("Scan an item to quickly restock it.")
        with st.form("restock_scan"):
            scan_code = st.text_input("Scan Barcode", key="restock_scan_input")
            qty_scan = st.number_input("Quantity to Add", min_value=1, value=10, key="scan_qty")
            submit_scan = st.form_submit_button("Restock")
            
            if submit_scan and scan_code:
                # Find product by barcode
                # (Ideally backend has a lookup, but we can search our loaded list for speed uiless list is huge)
                found_p = next((p for p in products if p['barcode'] == scan_code), None)
                if found_p:
                    # Execute Restock
                    payload = {
                        "product_id": found_p['id'],
                        "transaction_type": "restock",
                        "quantity": qty_scan,
                         "receipt_id": "RESTOCK-" + str(int(time.time())) # Optional: grouping ID for restocks
                    }
                    try:
                        r = requests.post(f"{API_URL}/inventory/transaction", json=payload)
                        if r.status_code == 200:
                            st.success(f"Successfully added {qty_scan} units to {found_p['name']}")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"Error: {r.text}")
                    except Exception as e:
                        st.error(str(e))
                else:
                    st.error("Product barcode not found.")

    with tab2:
        if product_options:
            selected_label = st.selectbox("Select Product", list(product_options.keys()))
            qty_manual = st.number_input("Quantity to Add", min_value=1, value=10, key="manual_qty")
            
            if st.button("Confirm Restock"):
                prod = product_options[selected_label]
                payload = {
                    "product_id": prod['id'],
                    "transaction_type": "restock",
                    "quantity": qty_manual,
                    "receipt_id": "RESTOCK-" + str(int(time.time()))
                }
                try:
                    r = requests.post(f"{API_URL}/inventory/transaction", json=payload)
                    if r.status_code == 200:
                        st.success(f"Successfully added {qty_manual} units to {prod['name']}")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"Error: {r.text}")
                except Exception as e:
                    st.error(str(e))
        else:
            st.info("No products available to select.")

elif sidebar_option == "Add Product":
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

elif sidebar_option == "Inventory":
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

elif sidebar_option == "Sales History":
    st.header("Transaction History")
    
    try:
        # Fetch transactions
        res = requests.get(f"{API_URL}/inventory/transactions")
        if res.status_code == 200:
            transactions = res.json()
            if transactions:
                df = pd.DataFrame(transactions)
                
                # Fetch products to map names (since transaction might only have product_id)
                # In a real app, the backend might join this, or we rely on the helper here
                res_prod = requests.get(f"{API_URL}/products/")
                products_map = {p['id']: p['name'] for p in res_prod.json()} if res_prod.status_code == 200 else {}
                
                df['product_name'] = df['product_id'].map(products_map)
                
                # Clean up display
                display_cols = ["id", "receipt_id", "timestamp", "transaction_type", "product_name", "quantity", "customer_id"]
                # Use only cols that exist
                cols = [c for c in display_cols if c in df.columns]
                st.dataframe(df[cols].sort_values(by="timestamp", ascending=False), hide_index=True, width='stretch')
            else:
                st.info("No transactions found.")
        else:
            st.error("Failed to load transactions.")
    except Exception as e:
        st.error(f"Error: {e}")

elif sidebar_option == "Customers":
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
                    # Create a nice label map
                    cust_map = {f"{c['name']} ({c['phone']})": c['id'] for c in custs}
                    selected_name = st.radio("Select Customer", list(cust_map.keys()))
                    selected_id = cust_map[selected_name]
                
                with c2:
                    st.write("📊 **Detailed Profile**")
                    # Fetch Profile Details
                    try:
                        p_res = requests.get(f"{API_URL}/products/customers/id/{selected_id}/profile")
                        if p_res.status_code == 200:
                            profile = p_res.json()
                            customer = profile['customer']
                            
                            # ID Card Style
                            st.info(f"### {customer['name']}")
                            
                            # Metrics Row
                            m1, m2, m3 = st.columns(3)
                            m1.metric("Status", profile['segment'])
                            m2.metric("Total Spent", f"${profile['total_spent']:,.2f}")
                            m3.metric("Visits", profile['visit_count'])
                            
                            st.markdown("---")
                            
                            # Favorites
                            st.write("❤️ **Top Favorite Items**")
                            if profile['top_items']:
                                for item in profile['top_items']:
                                    st.write(f"- **{item['name']}** (Bought {item['qty']} times)")
                            else:
                                st.caption("No purchase history yet.")
                                
                            st.markdown("---")
                            st.caption(f"Member since: {customer['created_at'][:10]}")
                            if customer['email']:
                                st.caption(f"Email: {customer['email']}")
                                
                        else:
                            st.error("Could not load profile details.")
                    except Exception as e:
                        st.error(f"Error loading profile: {e}")

            else:
                st.info("No customers registered yet.")
        else:
            st.error("Failed to load customers.")
    except Exception as e:
        st.error(e)

# REMOVED OLD Sales/Restock section as it is replaced by POS and History
# elif sidebar_option == "Sales/Restock": ... (This part effectively hidden by not including it)

# Optional: Load data from SQLite
def load_products_from_db():
    con = sqlite3.connect(DB_PATH)
    cursor = con.cursor()
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()
    con.close()
    return products

# Example usage in the app
products = load_products_from_db()
st.write(f"Loaded {len(products)} products from SQLite.")
