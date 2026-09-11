from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from . import models, schemas

def get_product(db: Session, product_id: int):
    return db.query(models.Product).filter(models.Product.id == product_id).first()

def get_product_by_barcode(db: Session, barcode: str):
    return db.query(models.Product).filter(models.Product.barcode == barcode).first()

def get_products(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Product).offset(skip).limit(limit).all()

def create_product(db: Session, product: schemas.ProductCreate):
    db_product = models.Product(**product.dict())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

def create_customer(db: Session, customer: schemas.CustomerCreate):
    db_customer = models.Customer(**customer.dict())
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)
    return db_customer

def get_customer_by_phone(db: Session, phone: str):
    return db.query(models.Customer).filter(models.Customer.phone == phone).first()

def create_transaction(db: Session, transaction: schemas.TransactionCreate):
    db_transaction = models.Transaction(**transaction.dict())
    db.add(db_transaction)
    
    # Update product stock
    product = get_product(db, transaction.product_id)
    if product:
        if transaction.transaction_type == 'restock':
            product.stock_quantity += transaction.quantity
        elif transaction.transaction_type == 'sale':
            product.stock_quantity -= transaction.quantity
    
    db.commit()
    db.refresh(db_transaction)
    return db_transaction

def get_customers(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Customer).offset(skip).limit(limit).all()

def get_transactions(db: Session, skip: int = 0, limit: int = 200):
    return db.query(models.Transaction).order_by(models.Transaction.timestamp.desc()).offset(skip).limit(limit).all()

def get_transactions_filtered(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    transaction_type: str | None = None,
    product_id: int | None = None,
    receipt_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    query = db.query(models.Transaction)

    if transaction_type:
        query = query.filter(models.Transaction.transaction_type == transaction_type)

    if product_id:
        query = query.filter(models.Transaction.product_id == product_id)

    if receipt_id:
        query = query.filter(func.lower(models.Transaction.receipt_id).like(f"%{receipt_id.lower()}%"))

    if start_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        query = query.filter(models.Transaction.timestamp >= start_dt)

    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        query = query.filter(models.Transaction.timestamp < end_dt)

    total = query.count()
    items = query.order_by(models.Transaction.timestamp.desc()).offset(skip).limit(limit).all()

    return items, total
