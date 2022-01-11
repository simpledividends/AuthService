from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends
from starlette.requests import Request

from auth_service.api import responses
from auth_service.api.auth import get_request_admin
from auth_service.api.exceptions import NotFoundException
from auth_service.api.services import get_db_service
from auth_service.db.exceptions import UserNotExists
from auth_service.log import app_logger
from auth_service.models.user import User

router = APIRouter()


@router.get(
    path="/users/{user_id}",
    tags=["Admin"],
    status_code=HTTPStatus.OK,
    response_model=User,
    responses={
        404: responses.not_found,
        422: responses.unprocessable_entity,
    }
)
async def get_user(
    request: Request,
    user_id: UUID,
    admin: User = Depends(get_request_admin),
) -> User:
    app_logger.info(f"Admin {admin.user_id} asks for user {user_id}")
    db_service = get_db_service(request.app)
    try:
        user = await db_service.get_user(user_id)
    except UserNotExists:
        app_logger.info(f"Requested user {user_id} not found")
        raise NotFoundException()

    return user
