import sqlite3
import random
from datetime import datetime, timedelta
import uuid

import os

# Configuration
# Robust path handling
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DB_PATH = os.path.join(PROJECT_ROOT, "backend", "smart_inventory.db")
DAYS_OF_HISTORY = 90

def create_synthetic_history():
    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get Products
    cursor.execute("SELECT id, name, price, stock_quantity FROM products")
    products = cursor.fetchall()
    
    # Get Customers
    cursor.execute("SELECT id FROM customers")
    customers = [row[0] for row in cursor.fetchall()]

    if not products:
        print("No products found! Run the app and add products first.")
        conn.close()
        return

    print(f"Found {len(products)} products and {len(customers)} customers. Generating {DAYS_OF_HISTORY} days of history...")
    
    # Optional: Clear old history to avoid duplicates
    print("Clearing old transaction history...")
    cursor.execute("DELETE FROM transactions WHERE transaction_type = 'sale'") # Keep restocks if you want, or delete all. 
    
    transactions = []
    
    # We will "reverse playback" history
    # Start from today and go back
    end_date = datetime.now()
    
    # Pattern Logic: Shopping Trips instead of individual item checks
    for day_offset in range(DAYS_OF_HISTORY):
        current_date = end_date - timedelta(days=day_offset)
        is_weekend = current_date.weekday() >= 5 # 5=Sat, 6=Sun
        
        # Traffic: 10-20 transactions on weekdays, 20-40 on weekends
        num_receipts = random.randint(20, 40) if is_weekend else random.randint(10, 20)
        
        for _ in range(num_receipts):
            # 1. Who is buying?
            # 30% chance it's a registered customer (if we have any), 70% Guest
            if customers and random.random() < 0.3:
                cust_id = random.choice(customers)
            else:
                cust_id = None # Guest
            
            # 2. When?
            ts_str = current_date.replace(hour=random.randint(9, 21), minute=random.randint(0, 59)).strftime("%Y-%m-%d %H:%M:%S")
            receipt_id = str(uuid.uuid4())
            
            # 3. What are they buying? (Basket Generation)
            # Pick 1 to 5 random items
            basket_size = random.randint(1, 5)
            
            # Weighted random selection for realism
            # Make a flat list with duplicates for weighting
            weighted_products = []
            for p in products:
                p_name = p[1]
                if p_name in ['Banana', 'Mineral Water']: weight = 10
                elif p_name in ['Toothbrush', 'Toothpaste']: weight = 5
                else: weight = 2
                weighted_products.extend([p] * weight)
                
            basket_items = random.sample(weighted_products, basket_size)
            
            # Deduplicate items in basket (sum quantities instead)
            basket_summary = {}
            for p in basket_items:
                p_id = p[0]
                basket_summary[p_id] = basket_summary.get(p_id, 0) + 1
            
            # Add to transactions list
            for p_id, qty in basket_summary.items():
                transactions.append((
                   p_id,
                   'sale',
                   qty,
                   receipt_id,
                   ts_str,
                   cust_id
                ))

    # Bulk Insert
    print(f"Inserting {len(transactions)} synthetic transaction records...")
    cursor.executemany("""
        INSERT INTO transactions (product_id, transaction_type, quantity, receipt_id, timestamp, customer_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, transactions)

    conn.commit()
    print("Success! History generated.")
    conn.close()

if __name__ == "__main__":
    create_synthetic_history()
