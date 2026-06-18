from fastapi import APIRouter, Depends

from app.api.deps import require_admin
from app.models.user import User


router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/ping")
def admin_ping(_current_user: User = Depends(require_admin)) -> dict[str, str]:
    return {"status": "ok"}
