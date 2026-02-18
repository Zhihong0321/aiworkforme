"""
MODULE: Product Catalog Router
PURPOSE: API endpoints for managing products and categories with tenant isolation.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, func
from typing import List, Optional
from datetime import datetime

from src.infra.database import get_session
from src.adapters.api.dependencies import require_tenant_access, AuthContext
from src.adapters.db.catalog_models import (
    Product, ProductCreate, ProductRead, ProductUpdate,
    ProductCategory, ProductCategoryCreate, ProductCategoryRead
)

router = APIRouter(prefix="/api/v1/catalog", tags=["Product Catalog"])

# --- Category Endpoints ---

@router.get("/categories", response_model=List[ProductCategoryRead])
def list_categories(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    """List all categories for the current tenant."""
    categories = session.exec(
        select(ProductCategory).where(ProductCategory.tenant_id == auth.tenant.id)
    ).all()
    return categories

@router.post("/categories", response_model=ProductCategoryRead)
def create_category(
    payload: ProductCategoryCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    """Create a new category. Max depth is 2 levels."""
    # Validation: Limit depth to 2
    if payload.parent_id:
        parent = session.get(ProductCategory, payload.parent_id)
        if not parent or parent.tenant_id != auth.tenant.id:
            raise HTTPException(status_code=404, detail="Parent category not found")
        if parent.parent_id is not None:
            raise HTTPException(status_code=400, detail="Maximum category depth is 2 levels")

    category = ProductCategory(
        **payload.dict(),
        tenant_id=auth.tenant.id
    )
    session.add(category)
    session.commit()
    session.refresh(category)
    return category

@router.delete("/categories/{category_id}")
def delete_category(
    category_id: int,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    """Delete a category. Products in this category will be orphaned (category_id set to null)."""
    category = session.get(ProductCategory, category_id)
    if not category or category.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Category not found")
    
    session.delete(category)
    session.commit()
    return {"message": "Category deleted"}

# --- Product Endpoints ---

@router.get("/products", response_model=List[ProductRead])
def list_products(
    category_id: Optional[int] = None,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    """List all products, optionally filtered by category."""
    query = select(Product).where(Product.tenant_id == auth.tenant.id)
    if category_id:
        query = query.where(Product.category_id == category_id)
    
    products = session.exec(query).all()
    return products

@router.post("/products", response_model=ProductRead)
def create_product(
    payload: ProductCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    """Create a new product. Subject to tenant product limits."""
    # Validation: Tenant limit (100 products for MVP)
    MAX_PRODUCTS = 100
    count = session.exec(
        select(func.count(Product.id)).where(Product.tenant_id == auth.tenant.id)
    ).one()
    
    if count >= MAX_PRODUCTS:
        raise HTTPException(status_code=400, detail=f"Maximum product limit reached ({MAX_PRODUCTS})")

    if payload.category_id:
        category = session.get(ProductCategory, payload.category_id)
        if not category or category.tenant_id != auth.tenant.id:
            raise HTTPException(status_code=404, detail="Category not found")

    product = Product(
        **payload.dict(),
        tenant_id=auth.tenant.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    session.add(product)
    session.commit()
    session.refresh(product)
    return product

@router.get("/products/{product_id}", response_model=ProductRead)
def get_product(
    product_id: int,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    """Get detailed information for a specific product."""
    product = session.get(Product, product_id)
    if not product or product.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@router.put("/products/{product_id}", response_model=ProductRead)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    """Update product information."""
    product = session.get(Product, product_id)
    if not product or product.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Product not found")
    
    data = payload.dict(exclude_unset=True)
    for key, value in data.items():
        setattr(product, key, value)
    
    product.updated_at = datetime.utcnow()
    session.add(product)
    session.commit()
    session.refresh(product)
    return product

@router.delete("/products/{product_id}")
def delete_product(
    product_id: int,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_tenant_access)
):
    """Delete a product from the catalog."""
    product = session.get(Product, product_id)
    if not product or product.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Product not found")
    
    session.delete(product)
    session.commit()
    return {"message": "Product deleted"}
