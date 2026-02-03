import streamlit as st
import requests
import pandas as pd
import time

API_URL = "http://127.0.0.1:8000"

def show():
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
