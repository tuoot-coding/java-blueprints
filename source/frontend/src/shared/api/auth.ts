import { apiGetJson, apiPatchJson, apiPostJson } from "@/shared/api/client";
import type {
  AuthMessageResponse,
  AuthUser,
  LoginResponse,
  UserRole,
} from "@/shared/types/auth";

export async function authRegister(input: {
  email: string;
  username: string;
  password: string;
  role: UserRole;
}): Promise<AuthMessageResponse> {
  return apiPostJson<AuthMessageResponse>("/api/v1/auth/register", input);
}

export async function authLogin(input: {
  email: string;
  password: string;
}): Promise<LoginResponse> {
  return apiPostJson<LoginResponse>("/api/v1/auth/login", input);
}

export async function authLogout(): Promise<AuthMessageResponse> {
  return apiPostJson<AuthMessageResponse>("/api/v1/auth/logout", {});
}

export async function authMe(): Promise<AuthUser> {
  return apiGetJson<AuthUser>("/api/v1/auth/me");
}

export async function authChangePassword(input: {
  current_password: string;
  new_password: string;
}): Promise<LoginResponse> {
  return apiPostJson<LoginResponse>("/api/v1/auth/change-password", input);
}

export async function authUpdateProfile(input: {
  role: UserRole;
}): Promise<AuthUser> {
  return apiPatchJson<AuthUser>("/api/v1/auth/profile", input);
}

export async function authResendVerification(email: string): Promise<AuthMessageResponse> {
  return apiPostJson<AuthMessageResponse>("/api/v1/auth/resend-verification", { email });
}
