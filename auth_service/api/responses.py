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


unprocessable_entity_or_password_improper = {
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
                        error_key="value_error.password.improper",
                        error_message="Password is improper or too weak",
                        error_loc=["body", "password"],
                    ),
                ],
            ),
        },
    },
}


conflict_register = {
    "model": ErrorResponse,
    "description": "Error: Conflict when register new user",
    "content": {
        "application/json": {
            "example": ErrorResponse(
                errors=[
                    Error(
                        error_key="email.already_exists",
                        error_message="User with this email is already exists",
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


conflict_register_verify = {
    "model": ErrorResponse,
    "description": "Error: Conflict when verify new user",
    "content": {
        "application/json": {
            "example": ErrorResponse(
                errors=[
                    Error(
                        error_key="email.already_verified",
                        error_message="User with this email is already exists",
                        error_loc=None,
                    ),
                ],
            ),
        },
    },
}


forbidden = {
    "model": ErrorResponse,
    "description": "Error: Forbidden",
    "content": {
        "application/json": {
            "example": ErrorResponse(
                errors=[
                    Error(
                        error_key="forbidden",
                        error_message="Forbidden",
                        error_loc=None,
                    ),
                ],
            ),
        },
    },
}


not_found = {
    "model": ErrorResponse,
    "description": "Error: Not found",
    "content": {
        "application/json": {
            "example": ErrorResponse(
                errors=[
                    Error(
                        error_key="not_found",
                        error_message="Resource not found",
                        error_loc=None,
                    ),
                ],
            ),
        },
    },
}
