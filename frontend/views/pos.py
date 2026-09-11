import streamlit as st
import pandas as pd
import time
import uuid
from supabase_client import get_supabase_client

def show():
    st.header("Point of Sale")
    supabase = get_supabase_client()

    # --- Customer Selection ---
    customer_id = None
    try:
        cust_res = supabase.table("customers").select("id,name,phone").order("name").execute()
        if cust_res.data:
            customers = cust_res.data
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
        else:
            st.caption("No customers loaded. Sales can still continue as Guest.")
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
            res = supabase.table("products").select("id,name,price,barcode").eq("barcode", scanned_code).maybe_single().execute()
            product = res.data
            if product:
                
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
            st.error(f"Lookup error: {e}")

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
            use_container_width=True,
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
            if st.button("💳 Complete Sale", type="primary", use_container_width=True):
                # Generate a single receipt ID for this entire cart
                receipt_id = str(uuid.uuid4())

                try:
                    # Validate stock before writing transaction rows.
                    product_ids = [item["product_id"] for item in st.session_state.cart]
                    stock_rows = (
                        supabase.table("products")
                        .select("id,name,stock_quantity")
                        .in_("id", product_ids)
                        .execute()
                    )
                    stock_map = {row["id"]: row for row in (stock_rows.data or [])}

                    insufficient = []
                    for item in st.session_state.cart:
                        current_stock = stock_map.get(item["product_id"], {}).get("stock_quantity", 0)
                        if current_stock < item["quantity"]:
                            insufficient.append(f"{item['name']} (have {current_stock}, need {item['quantity']})")

                    if insufficient:
                        st.error("Transaction Failed: Insufficient stock for " + ", ".join(insufficient))
                        return

                    tx_payload = []
                    for item in st.session_state.cart:
                        tx_payload.append(
                            {
                                "product_id": item["product_id"],
                                "transaction_type": "sale",
                                "quantity": int(item["quantity"]),
                                "receipt_id": receipt_id,
                                "customer_id": str(customer_id) if customer_id is not None else None,
                            }
                        )

                    supabase.table("transactions").insert(tx_payload).execute()

                    for item in st.session_state.cart:
                        current_stock = stock_map[item["product_id"]]["stock_quantity"]
                        new_stock = current_stock - int(item["quantity"])
                        supabase.table("products").update({"stock_quantity": new_stock}).eq("id", item["product_id"]).execute()

                    st.toast("Transaction Complete!", icon="🎉")
                    st.session_state.cart = []
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Transaction Failed: {e}")
    else:
        st.info("Cart is empty. Scan items to begin.")
        
        # Helper to show simulation codes
        st.markdown("---")
        st.caption("No physical scanner? Use these codes if you added demo data:")
        st.caption("Run `backend/data/demo_data.sql` or add product manually first.")
