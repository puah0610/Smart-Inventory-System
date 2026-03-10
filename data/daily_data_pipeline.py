import sqlite3
import random
from datetime import datetime, timedelta
import uuid
import os
import time

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DB_PATH = os.path.join(PROJECT_ROOT, "backend", "smart_inventory.db")
MAX_DAILY_TRANSACTIONS = 200

def generate_daily_transactions():
    print(f"[{datetime.now()}] Starting daily transaction generation...")
    
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}. Waiting...")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM transactions
            WHERE transaction_type = 'sale'
              AND date(timestamp) = ?
            """,
            (today_str,)
        )
        current_daily_count = cursor.fetchone()[0] or 0
        remaining_slots = MAX_DAILY_TRANSACTIONS - current_daily_count

        if remaining_slots <= 0:
            print(f"Daily cap reached ({MAX_DAILY_TRANSACTIONS}). Skipping generation for {today_str}.")
            return

        # Get Products
        cursor.execute("SELECT id, name, price, stock_quantity FROM products")
        products = cursor.fetchall()
        product_stock = {p[0]: p[3] for p in products}
        
        # Get Customers
        cursor.execute("SELECT id FROM customers")
        customers = [row[0] for row in cursor.fetchall()]

        if not products:
            print("No products found! Skipping generation.")
            return

        current_date = datetime.now()
        is_weekend = current_date.weekday() >= 5
        
        # Receipts per generation cycle
        # 1-3 receipts per cycle (weekday), 2-4 per cycle (weekend)
        num_receipts = random.randint(2, 4) if is_weekend else random.randint(1, 3)
        
        # --- Random Trend Logic ---
        # Pick 2 random products to be "correlated" just for this hourly batch
        trend_pair = random.sample(products, k=2) if len(products) >= 2 else []
        
        transactions = []
        
        for _ in range(num_receipts):
            if len(transactions) >= remaining_slots:
                break

            cust_id = random.choice(customers) if customers and random.random() < 0.3 else None
            receipt_id = str(uuid.uuid4())
            # Use current hour for more realistic real-time simulation
            current_hour = current_date.hour
            ts_str = current_date.replace(hour=current_hour, minute=random.randint(0, 59), second=random.randint(0, 59)).strftime("%Y-%m-%d %H:%M:%S")
            
            # Helper to find products
            def find_products(keyword):
                return [p for p in products if keyword.lower() in p[1].lower()]

            # Determine items to pick
            intent_roll = random.random()
            if intent_roll < 0.4: prods_to_pick = random.randint(3, 8)
            elif intent_roll < 0.7: prods_to_pick = random.randint(1, 3)
            else: prods_to_pick = random.randint(1, 5)

            basket_items = random.sample(products, k=min(len(products), prods_to_pick))
            
            # Add the "Trend Pair" 50% of the time to create organic-looking correlations
            if trend_pair and random.random() < 0.5:
                for tp in trend_pair:
                    if tp not in basket_items:
                        basket_items.append(tp)

            # Expand basket with rules (Keep the logical ones too)
            extra_items = []
            for p in basket_items:
                p_name = p[1]
                if "Pasta" in p_name and random.random() < 0.8:
                    sauces = find_products("Sauce")
                    if sauces: extra_items.append(random.choice(sauces))
                if "Cereal" in p_name and random.random() < 0.75:
                    milks = find_products("Milk")
                    if milks: extra_items.append(random.choice(milks))
                if "Bread" in p_name and random.random() < 0.6:
                    spreads = find_products("Butter")
                    if spreads: extra_items.append(random.choice(spreads))
                if "Chips" in p_name and random.random() < 0.5:
                    drinks = find_products("Cola")
                    if drinks: extra_items.append(random.choice(drinks))
            
            basket_items.extend(extra_items)
            
            # Deduplicate and format
            basket_summary = {}
            for p in basket_items:
                p_id = p[0]
                basket_summary[p_id] = basket_summary.get(p_id, 0) + 1
            
            for p_id, qty in basket_summary.items():
                if len(transactions) >= remaining_slots:
                    break

                available_stock = product_stock.get(p_id, 0)
                if available_stock <= 0:
                    continue

                sell_qty = min(qty, available_stock)
                transactions.append((p_id, 'sale', sell_qty, receipt_id, ts_str, cust_id))
                product_stock[p_id] = available_stock - sell_qty

        if transactions:
            cursor.executemany("""
                INSERT INTO transactions (product_id, transaction_type, quantity, receipt_id, timestamp, customer_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, transactions)

            stock_updates = [(stock_qty, product_id) for product_id, stock_qty in product_stock.items()]
            cursor.executemany(
                "UPDATE products SET stock_quantity = ? WHERE id = ?",
                stock_updates
            )

            conn.commit()
            print(
                f"Successfully inserted {len(transactions)} transactions. "
                f"Daily total: {current_daily_count + len(transactions)}/{MAX_DAILY_TRANSACTIONS}."
            )
        else:
            print(f"No transactions inserted this cycle. Daily total remains {current_daily_count}/{MAX_DAILY_TRANSACTIONS}.")
        
    except Exception as e:
        print(f"Error generating transactions: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    # If run directly as a script, it will keep generating data
    print("Continuous Data Generation Pipeline started.")
    print("Generating minutely batches of sales data...")
    
    while True:
        generate_daily_transactions()
        # Wait for 1 minute
        time.sleep(60)
