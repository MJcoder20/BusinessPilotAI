from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Product, OrderItem
from app.schemas.product import ProductCreate, ProductResponse

router = APIRouter(prefix="/products", tags=["Products"])


@router.post(
    "/",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED
)
def create_product(
    product_data: ProductCreate,
    db: Session = Depends(get_db)
):
    existing = db.query(Product).filter(
        Product.sku == product_data.sku
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="A product with this SKU already exists."
        )

    product = Product(**product_data.model_dump())

    db.add(product)
    db.commit()
    db.refresh(product)

    return product


@router.get("/", response_model=list[ProductResponse])
def get_products(db: Session = Depends(get_db)):
    return db.query(Product).order_by(Product.id.desc()).all()


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: int,
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(
        Product.id == product_id
    ).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    return product


@router.put("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int,
    product_data: ProductCreate,
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(
        Product.id == product_id
    ).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    duplicate = db.query(Product).filter(
        Product.sku == product_data.sku,
        Product.id != product_id
    ).first()

    if duplicate:
        raise HTTPException(status_code=409, detail="SKU already exists.")

    for key, value in product_data.model_dump().items():
        setattr(product, key, value)

    db.commit()
    db.refresh(product)

    return product


@router.delete("/{product_id}", status_code=204)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(
        Product.id == product_id
    ).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    # Prevent deletion if the product is referenced by an order item.
    used_in_orders = db.query(OrderItem).filter(
        OrderItem.product_id == product_id
    ).first()

    if used_in_orders:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete a product associated with sales orders."
        )

    db.delete(product)
    db.commit()

    return Response(status_code=204)