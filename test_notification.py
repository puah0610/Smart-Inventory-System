import sys
import os
from datetime import datetime, timedelta
import random

# Add root to sys.path to allow imports
sys.path.append(os.getcwd())

from backend.app.database import SessionLocal, engine
from backend.app import models
from backend.app.services.analytics_service import AnalyticsService

def test_trigger():
    # Ensure tables exist (in case we are hitting a new DB instance)
    models.Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        print("--- Setting up Test Scenario ---")
        
        # 1. Create a specific test product
        test_product_name = "Notification Test Item"
        product = db.query(models.Product).filter(models.Product.name == test_product_name).first()
        
        if not product:
            product = models.Product(
                name=test_product_name,
                barcode="TEST999",
                price=50.0,
                cost=30.0,
                category="Test",
                stock_quantity=100
            )
            db.add(product)
            db.commit()
            db.refresh(product)
            print(f"Created product: {product.name}")
        else:
             print(f"Using existing product: {product.name}")

        # 2. Clear old transactions for this test product to ensure clean data
        db.query(models.Transaction).filter(models.Transaction.product_id == product.id).delete()
        db.commit()
        print("Cleared old test transactions.")

        # 3. Inject High Sales (2 Weeks Ago)
        # Logic: prev_sales (2 weeks ago) vs recent_sales (last week)
        # Target: prev = 10, recent = 1.  (1 <= 10 * 0.4) -> True
        
        two_weeks_ago = datetime.utcnow() - timedelta(days=10) # 10 days ago is within the 7-14 day window
        
        print("Injecting High Sales (2 weeks ago)...")
        for _ in range(10): # 10 sales
            t = models.Transaction(
                product_id=product.id,
                transaction_type="sale",
                quantity=1,
                timestamp=two_weeks_ago,
                receipt_id=f"TEST_OLD_{random.randint(1000,9999)}"
            )
            db.add(t)
        
        # 4. Inject Low Sales (This Week)
        current_week = datetime.utcnow() - timedelta(days=2)
        
        print("Injecting Low Sales (This week)...")
        t = models.Transaction(
            product_id=product.id,
            transaction_type="sale",
            quantity=1,
            timestamp=current_week,
            receipt_id=f"TEST_NEW_{random.randint(1000,9999)}"
        )
        db.add(t)
        db.commit()
        
        # 5. Run Analytics
        print("\n--- Running Analytics Engine ---")
        service = AnalyticsService(engine)
        insights = service.generate_insights(db)
        
        # 6. Check results
        found = False
        for i in insights:
            if i['type'] == 'alert' and test_product_name in i['message']:
                print(f"\n[SUCCESS] Feature Verified! Found Alert in System: {i['message']}")
                found = True
                break
        
        if not found:
            print("\n[FAILED] No alert generated. Logic conditions might not be met.")
            
    finally:
        db.close()

if __name__ == "__main__":
    test_trigger()
