import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.models import Merchant
from backend.app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RegisterMerchantRequest,
    UserProfileResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication & Roles"])

ADMIN_DEFAULT_USER = "admin"
ADMIN_DEFAULT_PASS = "admin123"


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate either an Admin or a Shopkeeper/Vendor.
    """
    clean_user = req.username.strip().lower()
    clean_pass = req.password.strip()

    # 1. Check Admin Login
    if req.role == "admin" or clean_user == ADMIN_DEFAULT_USER:
        if clean_user == ADMIN_DEFAULT_USER and clean_pass == ADMIN_DEFAULT_PASS:
            token = f"admin-token-{uuid.uuid4().hex[:12]}"
            return LoginResponse(
                success=True,
                token=token,
                role="admin",
                user=UserProfileResponse(
                    id=0,
                    name="Platform Administrator",
                    username="admin",
                    role="admin",
                    business_type="Platform Admin",
                ),
                message="Admin login successful",
            )
        elif req.role == "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid admin credentials. Use admin / admin123",
            )

    # 2. Check Shopkeeper / Merchant Login
    merchant = db.query(Merchant).filter(
        (Merchant.username == clean_user) | (Merchant.name.ilike(clean_user)) | (Merchant.phone == clean_user)
    ).first()

    if not merchant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"No shopkeeper found with username/identifier '{req.username}'",
        )

    # Validate password
    expected_pass = merchant.password or "shop123"
    if clean_pass != expected_pass:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password for this shopkeeper account.",
        )

    if not merchant.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This shopkeeper account has been deactivated by the platform admin.",
        )

    # Set as currently active store terminal context
    db.query(Merchant).update({Merchant.is_current_active: False})
    merchant.is_current_active = True
    db.commit()
    db.refresh(merchant)

    token = f"merchant-token-{merchant.id}-{uuid.uuid4().hex[:8]}"
    return LoginResponse(
        success=True,
        token=token,
        role="merchant",
        user=UserProfileResponse(
            id=merchant.id,
            name=merchant.name,
            username=merchant.username or clean_user,
            role="merchant",
            business_type=merchant.business_type,
            phone=merchant.phone,
            currency=merchant.currency,
            is_active=merchant.is_active,
        ),
        message=f"Welcome back, {merchant.name}!",
    )


@router.post("/register", response_model=LoginResponse)
def register_shopkeeper(req: RegisterMerchantRequest, db: Session = Depends(get_db)):
    """
    Register a new shopkeeper / vendor account with username and password.
    """
    clean_username = req.username.strip().lower()
    clean_name = req.name.strip()

    # Check if username exists
    existing = db.query(Merchant).filter(
        (Merchant.username == clean_username) | (Merchant.name == clean_name)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Shopkeeper with username '{clean_username}' or store name '{clean_name}' already exists.",
        )

    # Deactivate others and set new as active
    db.query(Merchant).update({Merchant.is_current_active: False})

    new_merchant = Merchant(
        name=clean_name,
        username=clean_username,
        password=req.password.strip() or "shop123",
        business_type=req.business_type or "General Retail",
        phone=req.phone,
        currency=(req.currency or "INR").upper(),
        is_active=True,
        is_current_active=True,
    )
    db.add(new_merchant)
    db.commit()
    db.refresh(new_merchant)

    token = f"merchant-token-{new_merchant.id}-{uuid.uuid4().hex[:8]}"
    return LoginResponse(
        success=True,
        token=token,
        role="merchant",
        user=UserProfileResponse(
            id=new_merchant.id,
            name=new_merchant.name,
            username=new_merchant.username,
            role="merchant",
            business_type=new_merchant.business_type,
            phone=new_merchant.phone,
            currency=new_merchant.currency,
            is_active=new_merchant.is_active,
        ),
        message=f"Store '{new_merchant.name}' created and logged in successfully!",
    )


@router.get("/demo-accounts")
def get_demo_accounts(db: Session = Depends(get_db)):
    """
    Returns available demo accounts for 1-click login on login portal.
    """
    merchants = db.query(Merchant).filter(Merchant.is_active == True).limit(5).all()
    accounts = []
    for m in merchants:
        accounts.append({
            "name": m.name,
            "username": m.username or m.name.lower().replace(" ", "_"),
            "password": m.password or "shop123",
            "business_type": m.business_type,
            "role": "merchant",
        })

    return {
        "admin": {
            "name": "Platform Administrator",
            "username": "admin",
            "password": "admin123",
            "role": "admin",
        },
        "merchants": accounts,
    }
