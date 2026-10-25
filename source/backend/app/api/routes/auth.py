"""Маршруты /api/v1/auth/*."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.api.dependencies import get_auth_service, get_client_ip, get_current_user
from app.auth.cookies import clear_session_cookies, set_session_cookies
from app.auth.models import UserRecord, UserRole
from app.auth.service import AuthService, client_rate_key
from app.schemas.auth import (
    AuthMessageResponse,
    AuthUserResponse,
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RegisterRequest,
    ResendVerificationRequest,
    UpdateProfileRequest,
    VerifyEmailRequest,
)
from app.texts import auth as auth_texts

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_response(user: UserRecord) -> AuthUserResponse:
    return AuthUserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        role=user.role.value,  # type: ignore[arg-type]
        email_verified=user.is_email_verified,
        created_at=user.created_at,
    )


@router.post(
    "/register",
    operation_id="auth_register",
    summary="Регистрация (email + username + пароль)",
    response_model=AuthMessageResponse,
    status_code=202,
)
def auth_register(
    body: RegisterRequest,
    auth: Annotated[AuthService, Depends(get_auth_service)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
) -> AuthMessageResponse:
    auth.register(
        email=str(body.email),
        username=body.username,
        password=body.password,
        role=UserRole(body.role),
        client_key=client_rate_key(ip=client_ip, email=str(body.email)),
    )
    return AuthMessageResponse(message=auth_texts.REGISTER_ACCEPTED)


@router.post(
    "/login",
    operation_id="auth_login",
    summary="Вход по email и паролю",
    response_model=LoginResponse,
)
def auth_login(
    body: LoginRequest,
    response: Response,
    auth: Annotated[AuthService, Depends(get_auth_service)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
) -> LoginResponse:
    issued = auth.login(
        email=str(body.email),
        password=body.password,
        client_key=client_rate_key(ip=client_ip, email=str(body.email)),
    )
    set_session_cookies(
        response,
        settings=auth.cookie_settings,
        session_token=issued.session_token,
        csrf_token=issued.csrf_token,
    )
    return LoginResponse(
        user=_user_response(issued.user),
        csrf_token=issued.csrf_token,
        expires_at=issued.expires_at,
    )


@router.post(
    "/logout",
    operation_id="auth_logout",
    summary="Выход и отзыв сессии",
    response_model=AuthMessageResponse,
)
def auth_logout(
    request: Request,
    response: Response,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthMessageResponse:
    token = request.cookies.get(auth.cookie_settings.session_cookie_name)
    auth.logout(session_token=token)
    clear_session_cookies(response, settings=auth.cookie_settings)
    return AuthMessageResponse(message=auth_texts.LOGOUT_OK)


@router.get(
    "/me",
    operation_id="auth_me",
    summary="Текущий пользователь",
    response_model=AuthUserResponse,
)
def auth_me(
    user: Annotated[UserRecord, Depends(get_current_user)],
) -> AuthUserResponse:
    return _user_response(user)


@router.post(
    "/change-password",
    operation_id="auth_change_password",
    summary="Смена пароля в личном кабинете",
    response_model=LoginResponse,
)
def auth_change_password(
    body: ChangePasswordRequest,
    response: Response,
    user: Annotated[UserRecord, Depends(get_current_user)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> LoginResponse:
    issued = auth.change_password(
        user=user,
        current_password=body.current_password,
        new_password=body.new_password,
    )
    set_session_cookies(
        response,
        settings=auth.cookie_settings,
        session_token=issued.session_token,
        csrf_token=issued.csrf_token,
    )
    return LoginResponse(
        user=_user_response(issued.user),
        csrf_token=issued.csrf_token,
        expires_at=issued.expires_at,
    )


@router.patch(
    "/profile",
    operation_id="auth_update_profile",
    summary="Обновление профиля (роль на этапе разработки)",
    response_model=AuthUserResponse,
)
def auth_update_profile(
    body: UpdateProfileRequest,
    user: Annotated[UserRecord, Depends(get_current_user)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthUserResponse:
    updated = auth.update_role(user=user, role=UserRole(body.role))
    return _user_response(updated)


@router.post(
    "/verify-email",
    operation_id="auth_verify_email",
    summary="Подтверждение email по токену",
    response_model=AuthMessageResponse,
)
def auth_verify_email(
    body: VerifyEmailRequest,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthMessageResponse:
    auth.verify_email(token=body.token)
    return AuthMessageResponse(message=auth_texts.VERIFY_OK)


@router.post(
    "/resend-verification",
    operation_id="auth_resend_verification",
    summary="Повторная отправка письма подтверждения",
    response_model=AuthMessageResponse,
    status_code=202,
)
def auth_resend_verification(
    body: ResendVerificationRequest,
    auth: Annotated[AuthService, Depends(get_auth_service)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
) -> AuthMessageResponse:
    auth.resend_verification(
        email=str(body.email),
        client_key=client_rate_key(ip=client_ip, email=str(body.email)),
    )
    return AuthMessageResponse(message=auth_texts.RESEND_OK)


@router.post(
    "/password-reset/request",
    operation_id="auth_password_reset_request",
    summary="Запрос сброса пароля",
    response_model=AuthMessageResponse,
    status_code=202,
)
def auth_password_reset_request(
    body: PasswordResetRequest,
    auth: Annotated[AuthService, Depends(get_auth_service)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
) -> AuthMessageResponse:
    auth.request_password_reset(
        email=str(body.email),
        client_key=client_rate_key(ip=client_ip, email=str(body.email)),
    )
    return AuthMessageResponse(message=auth_texts.RESET_REQUESTED)


@router.post(
    "/password-reset/confirm",
    operation_id="auth_password_reset_confirm",
    summary="Подтверждение сброса пароля",
    response_model=AuthMessageResponse,
)
def auth_password_reset_confirm(
    body: PasswordResetConfirmRequest,
    auth: Annotated[AuthService, Depends(get_auth_service)],
    client_ip: Annotated[str | None, Depends(get_client_ip)],
) -> AuthMessageResponse:
    auth.confirm_password_reset(
        token=body.token,
        new_password=body.new_password,
        client_key=client_rate_key(ip=client_ip),
    )
    return AuthMessageResponse(message=auth_texts.RESET_CONFIRMED)
