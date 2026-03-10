from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import crud, schemas, database, models

from typing import List

router = APIRouter(
    prefix="/inventory",
    tags=["inventory"],
    responses={404: {"description": "Not found"}},
)

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/transactions", response_model=List[schemas.Transaction])
def read_transactions(skip: int = 0, limit: int = 200, db: Session = Depends(get_db)):
    return crud.get_transactions(db, skip=skip, limit=limit)

@router.get("/transactions/query")
def read_transactions_query(
    skip: int = 0,
    limit: int = 50,
    transaction_type: str | None = None,
    product_id: int | None = None,
    receipt_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_db)
):
    items, total = crud.get_transactions_filtered(
        db,
        skip=skip,
        limit=limit,
        transaction_type=transaction_type,
        product_id=product_id,
        receipt_id=receipt_id,
        start_date=start_date,
        end_date=end_date
    )

    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@router.post("/transaction", response_model=schemas.Transaction)
def create_transaction(transaction: schemas.TransactionCreate, db: Session = Depends(get_db)):
    # 1. Check if product exists
    product = crud.get_product(db, transaction.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # 2. Check stock for sales
    if transaction.transaction_type == 'sale':
        if product.stock_quantity < transaction.quantity:
             raise HTTPException(status_code=400, detail="Insufficient stock")

    return crud.create_transaction(db=db, transaction=transaction)

@router.post("/batch_transaction", response_model=List[schemas.Transaction])
def create_batch_transaction(batch: schemas.BatchTransactionCreate, db: Session = Depends(get_db)):
    # 1. Validation Phase (Check all BEFORE saving anything)
    products_to_update = []
    
    for item in batch.items:
        product = crud.get_product(db, item.product_id)
        if not product:
            raise HTTPException(status_code=404, detail=f"Product ID {item.product_id} not found")
            
        if item.transaction_type == 'sale':
            if product.stock_quantity < item.quantity:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Insufficient stock for '{product.name}'. Req: {item.quantity}, Avail: {product.stock_quantity}"
                )
        
        products_to_update.append((product, item))
        
    # 2. Execution Phase (All validations passed)
    created_transactions = []
    try:
        for product, item in products_to_update:
            # Overwrite the receipt_id just in case one wasn't passed per item
            item.receipt_id = batch.receipt_id 
            item.customer_id = batch.customer_id
            
            # Use logic from crud.py but we do it here to keep session atomic
            db_txn = models.Transaction(
                product_id=item.product_id,
                transaction_type=item.transaction_type,
                quantity=item.quantity,
                receipt_id=item.receipt_id,
                customer_id=item.customer_id
            )
            
            if item.transaction_type == "restock":
                product.stock_quantity += item.quantity
            elif item.transaction_type == "sale":
                product.stock_quantity -= item.quantity
                
            db.add(db_txn)
            created_transactions.append(db_txn)
            
        db.commit()
        for txn in created_transactions:
            db.refresh(txn)
            
        return created_transactions
        
    except Exception as e:
        db.rollback() # Undo EVERYTHING if one write fails
        raise HTTPException(status_code=500, detail=str(e))
