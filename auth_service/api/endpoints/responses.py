from auth_service.models.common import Error, ErrorResponse

unprocessable_entity = {
    "model": ErrorResponse,
    "description": "Error: Unprocessable Entity",
    "content": {
        "application/json": {
            "example": ErrorResponse(
                errors=[
                    Error(
                        error_key="error_type.attr.desc",
                        error_message="error message",
                        error_loc=["body", "some_place"],
                    ),
                ],
            ),
        },
    },
}


unprocessable_entity_or_password_invalid = {
    "model": ErrorResponse,
    "description": "Error: Unprocessable Entity",
    "content": {
        "application/json": {
            "example": ErrorResponse(
                errors=[
                    Error(
                        error_key="error_type.attr.desc",
                        error_message="error message",
                        error_loc=["body", "some_place"],
                    ),
                    Error(
                        error_key="value_error.password.invalid",
                        error_message="Password is invalid",
                        error_loc=["body", "password"],
                    ),
                ],
            ),
        },
    },
}


conflict = {
    "model": ErrorResponse,
    "description": "Error: Conflict",
    "content": {
        "application/json": {
            "example": ErrorResponse(
                errors=[
                    Error(
                        error_key="email.already_exists",
                        error_message="User is already exists",
                        error_loc=None,
                    ),
                    Error(
                        error_key="conflict",
                        error_message="Conflict",
                        error_loc=None,
                    ),
                ],
            ),
        },
    },
}
