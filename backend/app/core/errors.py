class AppError(Exception):
    status_code = 400

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


class GoneError(AppError):
    """It existed and is finished with - as opposed to 404, which may never have existed.
    Worth the distinction for single-use links: a parent re-tapping the invitation in
    WhatsApp has already accepted it, and telling them to ask their coach is wrong."""

    status_code = 410


class ValidationError(AppError):
    status_code = 422


class AuthError(AppError):
    status_code = 401


class ForbiddenError(AppError):
    status_code = 403
