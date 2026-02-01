from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List
from .. import crud, models, schemas, database

router = APIRouter(
    prefix="/products",
    tags=["products"],
    responses={404: {"description": "Not found"}},
)

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/customers/", response_model=schemas.Customer, tags=["customers"])
def create_customer(customer: schemas.CustomerCreate, db: Session = Depends(get_db)):
    db_customer = crud.get_customer_by_phone(db, phone=customer.phone)
    if db_customer:
        raise HTTPException(status_code=400, detail="Customer already exists")
    return crud.create_customer(db=db, customer=customer)

@router.get("/customers/", response_model=List[schemas.Customer], tags=["customers"])
def read_customers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_customers(db, skip=skip, limit=limit)

@router.get("/customers/{phone}", response_model=schemas.Customer, tags=["customers"])
def get_customer(phone: str, db: Session = Depends(get_db)):
    db_customer = crud.get_customer_by_phone(db, phone=phone)
    if not db_customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return db_customer

@router.get("/customers/id/{customer_id}/profile", response_model=schemas.CustomerProfile, tags=["customers"])
def get_customer_profile(customer_id: int, db: Session = Depends(get_db)):
    customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Aggregations
    # Total Spend & Visits (Count unique receipts)
    stats = db.query(
        func.sum(models.Product.price * models.Transaction.quantity).label("spent"),
        func.count(models.Transaction.receipt_id.distinct()).label("visits"),
        func.max(models.Transaction.timestamp).label("last_visit")
    ).join(models.Product).filter(models.Transaction.customer_id == customer_id).first()
    
    total_spent = stats.spent if stats.spent else 0
    visit_count = stats.visits if stats.visits else 0
    last_visit = stats.last_visit
    
    # Top Items
    top_items_query = db.query(
        models.Product.name,
        func.sum(models.Transaction.quantity).label("qty")
    ).join(models.Transaction).filter(models.Transaction.customer_id == customer_id)\
    .group_by(models.Product.id).order_by(desc("qty")).limit(3).all()
    
    top_items = [{"name": r.name, "qty": r.qty} for r in top_items_query]
    
    # Segmentation Logic
    segment = "New"
    if total_spent > 500:
        segment = "VIP 🌟"
    elif total_spent > 100:
        segment = "Regular 😊"
    elif visit_count > 1:
        segment = "Returning"
        
    return {
        "customer": customer,
        "total_spent": total_spent,
        "visit_count": visit_count,
        "last_visit": last_visit,
        "top_items": top_items,
        "segment": segment
    }

@router.post("/", response_model=schemas.Product)
def create_product(product: schemas.ProductCreate, db: Session = Depends(get_db)):
    db_product = crud.get_product_by_barcode(db, barcode=product.barcode)
    if db_product:
        raise HTTPException(status_code=400, detail="Product with this barcode already registered")
    return crud.create_product(db=db, product=product)

@router.get("/", response_model=List[schemas.Product])
def read_products(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    products = crud.get_products(db, skip=skip, limit=limit)
    return products

@router.get("/{barcode}", response_model=schemas.Product)
def read_product(barcode: str, db: Session = Depends(get_db)):
    db_product = crud.get_product_by_barcode(db, barcode=barcode)
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return db_product
