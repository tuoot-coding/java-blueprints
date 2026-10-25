export type UserRole = "user" | "admin";

export interface AuthUser {
  id: string;
  email: string;
  username: string;
  role: UserRole;
  email_verified: boolean;
  created_at: string;
}

export interface LoginResponse {
  user: AuthUser;
  csrf_token: string;
  expires_at: string;
}

export interface AuthMessageResponse {
  message: string;
}
