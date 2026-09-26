class CollectorException(Exception):
    def __init__(self, message: str, error_code: str = "UNKNOWN_ERROR"):
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class InvalidTargetURLError(CollectorException):
    def __init__(self, message: str = "L’URL de la cible fournie est invalide."):
        super().__init__(message, error_code="INVALID_URL")


class PageNotFoundError(CollectorException):
    def __init__(self, message: str = "La page Facebook demandée est introuvable."):
        super().__init__(message, error_code="PAGE_NOT_FOUND")


class LoginRequiredError(CollectorException):
    def __init__(self, message: str = "Une authentification Facebook est requise."):
        super().__init__(message, error_code="LOGIN_REQUIRED")


class AccessRestrictedError(CollectorException):
    def __init__(self, message: str = "L’accès à cette page Facebook est actuellement restreint."):
        super().__init__(message, error_code="ACCESS_RESTRICTED")


class CaptchaDetectedError(CollectorException):
    def __init__(self, message: str = "Une vérification CAPTCHA bloque actuellement la collecte."):
        super().__init__(message, error_code="CAPTCHA")


class LayoutUnknownError(CollectorException):
    def __init__(self, message: str = "La structure de la page n’est pas reconnue et nécessite un examen manuel."):
        super().__init__(message, error_code="LAYOUT_UNKNOWN")


class CrawlTimeoutError(CollectorException):
    def __init__(self, message: str = "Le délai maximal de traitement a été dépassé."):
        super().__init__(message, error_code="TIMEOUT")
