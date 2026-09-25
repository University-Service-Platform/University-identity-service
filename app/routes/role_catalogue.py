from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import require_permission
from app.models.user import User
from app.schemas.role import RoleCatalogueEntryResponse, RoleCatalogueListResponse
from app.services.role_catalogue_service import RoleCatalogueService

router = APIRouter(tags=["Role Catalogue"])

@router.get(
    "/roles",
    response_model=RoleCatalogueListResponse,
    status_code=status.HTTP_200_OK,
    summary="List System Roles",
    description="List every valid system role with the Identity Service permissions it grants. Requires the 'roles:read' permission."
)
def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("roles:read"))
):
    return RoleCatalogueListResponse(success=True, data=RoleCatalogueService(db).list_roles())

@router.get(
    "/roles/{role_name}",
    response_model=RoleCatalogueEntryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get System Role",
    description="Retrieve one system role and its permissions (case-insensitive name). Requires the 'roles:read' permission."
)
def get_role(
    role_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("roles:read"))
):
    return RoleCatalogueEntryResponse(success=True, data=RoleCatalogueService(db).get_role(role_name))
