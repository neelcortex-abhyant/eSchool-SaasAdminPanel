from fastapi import APIRouter

from app.api.v1 import auth, payments, school_admin, school_admin_people, school_payments, school_registration, users
from app.api.v1.super_admin import router as super_admin_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(school_registration.router)
router.include_router(school_payments.router)
router.include_router(users.router)
router.include_router(school_admin.router)
router.include_router(school_admin_people.router)
router.include_router(school_admin_people.files_router)
router.include_router(payments.router)
router.include_router(super_admin_router)
