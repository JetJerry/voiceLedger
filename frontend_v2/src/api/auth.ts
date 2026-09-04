import { apiClient, setTokens, clearTokens, getStoredRefreshToken } from './client';
import {
  UserLoginRequest,
  UserLoginResponse,
  UserRegisterRequest,
  UserRegisterResponse,
  TokenRefreshResponse,
  LogoutResponse,
  User,
} from '../types/auth';

export async function registerApi(data: UserRegisterRequest): Promise<UserRegisterResponse> {
  return apiClient.post<UserRegisterResponse>(
    '/api/v1/auth/register',
    data,
    { requiresAuth: false }
  );
}

export async function loginApi(credentials: UserLoginRequest): Promise<UserLoginResponse> {
  const response = await apiClient.post<UserLoginResponse>(
    '/api/v1/auth/login',
    credentials,
    { requiresAuth: false }
  );
  setTokens(response.access_token, response.refresh_token);
  return response;
}

export async function refreshTokenApi(refreshToken: string): Promise<TokenRefreshResponse> {
  const response = await apiClient.post<TokenRefreshResponse>(
    '/api/v1/auth/refresh',
    { refresh_token: refreshToken },
    { requiresAuth: false }
  );
  setTokens(response.access_token, response.refresh_token);
  return response;
}

export async function logoutApi(): Promise<LogoutResponse> {
  const refreshToken = getStoredRefreshToken();
  try {
    if (refreshToken) {
      await apiClient.post<LogoutResponse>(
        '/api/v1/auth/logout',
        { refresh_token: refreshToken },
        { requiresAuth: false }
      );
    }
  } finally {
    clearTokens();
  }
  return { success: true, message: 'Logged out successfully' };
}

export async function getMeApi(): Promise<User> {
  return apiClient.get<User>('/api/v1/auth/me', { requiresAuth: true });
}

export async function getHealthApi(): Promise<{
  status: string;
  database: string;
  redis: string;
  service: string;
  version: string;
}> {
  return apiClient.get('/health', { requiresAuth: false });
}
