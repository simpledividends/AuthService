class UserAlreadyExists(Exception):
    pass


class TooManyNewcomersWithSameEmail(Exception):
    pass


class TooManyChangeSameEmailRequests(Exception):
    pass


class TooManyPasswordTokens(Exception):
    pass


class TokenNotFound(Exception):
    pass


class NotExists(Exception):
    pass


class UserNotExists(NotExists):
    pass


class PasswordInvalid(Exception):
    pass


class TransactionError(Exception):
    pass
