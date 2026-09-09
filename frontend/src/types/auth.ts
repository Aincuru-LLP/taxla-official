/**
 * Mirrors backend `UserResponse` (app/schemas/auth.py).
 *
 * Kept in /types so both components and stores can share one shape.
 */
export interface AuthUser {
  id: string;
  name: string;
  email: string;
  role: "OPERATOR" | "REVIEWER_AUDITOR" | "BRANCH_ADMIN" | "SUPER_ADMIN" | string;
  branch_id: string | null;
  status: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  user: AuthUser;
}

export interface RefreshResponse {
  access_token: string;
  token_type: "bearer";
}