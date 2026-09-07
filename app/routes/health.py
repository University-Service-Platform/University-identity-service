from fastapi import APIRouter, status

router = APIRouter(tags=["Health"])

@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Health Check",
    description="Check identity service health status"
)
def health_check():
    return {
        "status": "healthy",
        "service": "identity-service",
        "version": "1.0.0"
    }
