"""
MODULE: Database Models - Product Catalog
PURPOSE: SQLModel definitions for Products and Categories.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlmodel import Field, Relationship, SQLModel, Column, JSON
from sqlalchemy import UniqueConstraint

class ProductCategory(SQLModel, table=True):
    __tablename__ = "et_product_categories"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="et_tenants.id", index=True)
    name: str = Field(index=True)
    parent_id: Optional[int] = Field(default=None, foreign_key="et_product_categories.id")
    
    # Relationships
    parent: Optional["ProductCategory"] = Relationship(
        back_populates="children", 
        sa_relationship_kwargs={"remote_side": "ProductCategory.id"}
    )
    children: List["ProductCategory"] = Relationship(back_populates="parent")
    products: List["Product"] = Relationship(back_populates="category")

class Product(SQLModel, table=True):
    __tablename__ = "et_products"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="et_tenants.id", index=True)
    category_id: Optional[int] = Field(default=None, foreign_key="et_product_categories.id")
    
    title: str = Field(index=True)
    price: Optional[float] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    attachment_url: Optional[str] = None
    
    # Advanced metadata (features, specs, versions)
    details: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    category: Optional[ProductCategory] = Relationship(back_populates="products")

# --- DTOs / Schemas ---

class ProductCategoryCreate(SQLModel):
    name: str
    parent_id: Optional[int] = None

class ProductCategoryRead(SQLModel):
    id: int
    name: str
    parent_id: Optional[int] = None

class ProductCreate(SQLModel):
    category_id: Optional[int] = None
    title: str
    price: Optional[float] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    attachment_url: Optional[str] = None
    details: Dict[str, Any] = {}

class ProductUpdate(SQLModel):
    category_id: Optional[int] = None
    title: Optional[str] = None
    price: Optional[float] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    attachment_url: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

class ProductRead(SQLModel):
    id: int
    category_id: Optional[int] = None
    title: str
    price: Optional[float] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    attachment_url: Optional[str] = None
    details: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
