"""Сообщения об ошибках для клиента по машинному коду."""

from __future__ import annotations

from types import MappingProxyType

from app.schemas.errors import ErrorCode

ERROR_MESSAGES: MappingProxyType[ErrorCode, str] = MappingProxyType(
    {
        ErrorCode.BAD_REQUEST: "Некорректный запрос.",
        ErrorCode.NOT_FOUND: "Ресурс не найден.",
        ErrorCode.METHOD_NOT_ALLOWED: "HTTP-метод не поддерживается для этого ресурса.",
        ErrorCode.VALIDATION_ERROR: "Параметры запроса не прошли валидацию.",
        ErrorCode.PAYLOAD_TOO_LARGE: "Размер исходного текста превышает допустимый лимит.",
        ErrorCode.REVISION_CONFLICT: (
            "Исходник или ревизия изменились. Обновите состояние и повторите."
        ),
        ErrorCode.FIX_NOT_APPLICABLE: "Исправление нельзя применить к этой версии исходника.",
        ErrorCode.GENERATION_REFUSED: "Структурная генерация Java отклонена.",
        ErrorCode.LLM_UNAVAILABLE: (
            "DeepSeek недоступен или ключ не принят. Проверьте API Key в файле api "
            "(Provider deepseek, API Key sk-...) или LLM_API_KEY."
        ),
        ErrorCode.LLM_PAYMENT_REQUIRED: (
            "DeepSeek отклонил запрос: недостаточно средств или лимит (HTTP 402). "
            "Проверьте баланс на platform.deepseek.com."
        ),
        ErrorCode.LLM_TIMEOUT: (
            "DeepSeek не ответил вовремя, лимит запросов или обрыв на большом файле. "
            "Подождите и повторите; для >1000 строк используются точечные replacements."
        ),
        ErrorCode.HTTP_ERROR: "Запрос не может быть обработан.",
        ErrorCode.INTERNAL_ERROR: "Внутренняя ошибка сервера. Повторите запрос позже.",
        ErrorCode.AUTH_REQUIRED: "Требуется вход в систему.",
        ErrorCode.AUTH_INVALID_CREDENTIALS: "Неверный email или пароль.",
        ErrorCode.AUTH_EMAIL_NOT_VERIFIED: (
            "Email ещё не подтверждён. Проверьте почту или запросите письмо снова."
        ),
        ErrorCode.AUTH_CSRF_FAILED: "Запрос отклонён проверкой CSRF.",
        ErrorCode.AUTH_RATE_LIMITED: "Слишком много попыток. Подождите и повторите позже.",
        ErrorCode.AUTH_TOKEN_INVALID: "Ссылка недействительна или устарела.",
        ErrorCode.AUTH_PASSWORD_POLICY: (
            "Пароль не соответствует требованиям (минимальная длина, не только цифры)."
        ),
        ErrorCode.AUTH_PASSWORD_PWNED: (
            "Этот пароль найден в известных утечках. Выберите другой пароль."
        ),
        ErrorCode.AUTH_USERNAME_TAKEN: "Это имя пользователя уже занято.",
        ErrorCode.AUTH_USERNAME_INVALID: (
            "Имя пользователя: 3-32 символа, латиница, цифры и _."
        ),
    }
)


def get_error_message(error_code: ErrorCode) -> str:
    """Возвращает текст для кода ошибки; отсутствие текста является ошибкой разработки."""
    return ERROR_MESSAGES[error_code]


def llm_failure_error_code(reason: str | None) -> ErrorCode:
    """Сопоставляет причину сбоя LLM с машинным кодом для клиента."""
    if reason == "http_402":
        return ErrorCode.LLM_PAYMENT_REQUIRED
    if reason in {"timeout", "transport", "http_429", "http_502", "http_503", "http_504"}:
        # Сеть, лимит запросов, перегрузка - не ошибка ключа.
        return ErrorCode.LLM_TIMEOUT
    if reason in {
        "http_401",
        "http_403",
        "llm_not_configured",
        "oauth_credentials_mismatch",
        "oauth_authorization_header_invalid",
        "oauth_scope_mismatch",
    }:
        return ErrorCode.LLM_UNAVAILABLE
    if reason and reason.startswith("http_"):
        return ErrorCode.LLM_UNAVAILABLE
    return ErrorCode.LLM_UNAVAILABLE
