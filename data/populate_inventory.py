import sqlite3
import os

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DB_PATH = os.path.join(PROJECT_ROOT, "backend", "smart_inventory.db")

items = [
    ("Fresh Milk 1L", "DAIRY001", 2.50, 1.80, "Dairy", 50),
    ("Cheddar CheeseBlock", "DAIRY002", 5.50, 3.50, "Dairy", 40),
    ("Greek Yogurt 500g", "DAIRY003", 4.50, 2.90, "Dairy", 60),
    ("Salted Butter", "DAIRY004", 3.80, 2.50, "Dairy", 30),
    ("Whole Wheat Bread", "BAKERY001", 3.20, 2.00, "Bakery", 40),
    ("Croissant (Pack of 4)", "BAKERY002", 5.00, 2.50, "Bakery", 30),
    ("Bagels (Pack of 6)", "BAKERY003", 4.50, 2.00, "Bakery", 40),
    ("Chocolate Muffin", "BAKERY004", 2.50, 1.00, "Bakery", 35),
    ("Mineral Water 600ml", "DRINK001", 1.00, 0.30, "Beverage", 200),
    ("Orange Juice 1L", "DRINK002", 3.50, 2.20, "Beverage", 50),
    ("Cola Can 330ml", "DRINK003", 1.20, 0.60, "Beverage", 100),
    ("Craft Beer IPA", "DRINK004", 4.50, 2.80, "Alcohol", 80),
    ("Red Wine (Cab Sauv)", "DRINK005", 18.00, 12.00, "Alcohol", 20),
    ("Energy Drink", "DRINK006", 3.00, 1.50, "Beverage", 60),
    ("Banana (Bunch)", "FRUIT001", 2.50, 1.50, "Produce", 100),
    ("Gala Apples (1kg)", "FRUIT002", 4.00, 2.50, "Produce", 80),
    ("Avocado", "FRUIT003", 1.50, 0.90, "Produce", 60),
    ("Baby Spinach Mix", "VEG001", 3.00, 1.80, "Produce", 40),
    ("Tomatoes (500g)", "VEG002", 2.50, 1.20, "Produce", 50),
    ("Carrots (1kg)", "VEG003", 1.80, 0.90, "Produce", 70),
    ("Pasta Spaghetti 500g", "PANTRY001", 2.00, 1.10, "Pantry", 100),
    ("Pasta Sauce (Tomato)", "PANTRY002", 3.50, 2.00, "Pantry", 80),
    ("Olive Oil 500ml", "PANTRY003", 8.00, 5.50, "Pantry", 40),
    ("Jasmine Rice 5kg", "PANTRY004", 12.00, 9.00, "Pantry", 30),
    ("Breakfast Cereal", "PANTRY005", 5.50, 3.50, "Pantry", 50),
    ("Instant Noodles (5pk)", "PANTRY006", 3.50, 2.00, "Pantry", 120),
    ("Tomato Ketchup", "PANTRY007", 3.00, 1.80, "Pantry", 60),
    ("Toilet Paper (12pk)", "HOME001", 8.50, 5.00, "Household", 60),
    ("Laundry Detergent 2L", "HOME002", 12.00, 8.00, "Household", 40),
    ("Dish Soap 500ml", "HOME003", 3.50, 2.00, "Household", 50),
    ("AA Batteries (4pk)", "HOME004", 6.00, 3.00, "Household", 45),
    ("Toothpaste Mint", "PERSONAL001", 4.00, 2.50, "Personal Care", 60),
    ("Shampoo 400ml", "PERSONAL002", 6.50, 4.00, "Personal Care", 50),
    ("Body Wash", "PERSONAL003", 5.50, 3.00, "Personal Care", 50),
    ("Hand Sanitizer", "PERSONAL004", 3.00, 1.00, "Personal Care", 100),
    ("Potato Chips (Salt)", "SNACK001", 3.00, 1.50, "Snacks", 80),
    ("Chocolate Bar", "SNACK002", 1.80, 1.00, "Snacks", 100),
    ("Cookies (Choc Chip)", "SNACK003", 2.50, 1.50, "Snacks", 60),
    ("Roasted Nuts", "SNACK004", 4.50, 3.00, "Snacks", 50)
]

def populate():
    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("Adding products...")
    added = 0
    for item in items:
        name, barcode, price, cost, category, stock = item
        # Check integrity
        try:
            cursor.execute("""
                INSERT INTO products (name, barcode, price, cost, category, stock_quantity)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, barcode, price, cost, category, stock))
            added += 1
        except sqlite3.IntegrityError:
            print(f"Skipping {name} (already exists or barcode collision)")
    
    conn.commit()
    conn.close()
    print(f"Successfully added {added} new products.")

if __name__ == "__main__":
    populate()
