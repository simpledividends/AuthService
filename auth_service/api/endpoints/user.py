from http import HTTPStatus

from fastapi import APIRouter, Depends

from auth_service.api.endpoints import responses
from auth_service.auth import get_request_user
from auth_service.models.user import User

router = APIRouter()


@router.post(
    path="/auth/users/me",
    tags=["User"],
    status_code=HTTPStatus.OK,
    response_model=User,
    responses={
        403: responses.forbidden,
    }
)
def get_me(
    user: User = Depends(get_request_user)
):
    return user
