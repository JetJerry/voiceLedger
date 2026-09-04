import { TokenRefreshResponse } from '../types/auth';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const REFRESH_TOKEN_KEY = 'voiceledger_refresh_token';

let inMemoryAccessToken: string | null = null;
let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

function onTokenRefreshed(token: string) {
  refreshSubscribers.forEach((callback) => callback(token));
  refreshSubscribers = [];
}

function addRefreshSubscriber(callback: (token: string) => void) {
  refreshSubscribers.push(callback);
}

export function getAccessToken(): string | null {
  return inMemoryAccessToken;
}

export function setTokens(accessToken: string, refreshToken?: string): void {
  inMemoryAccessToken = accessToken;
  if (refreshToken && typeof localStorage !== 'undefined') {
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  }
}

export function getStoredRefreshToken(): string | null {
  if (typeof localStorage === 'undefined') return null;
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function clearTokens(): void {
  inMemoryAccessToken = null;
  if (typeof localStorage !== 'undefined') {
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  }
}

export interface RequestOptions extends RequestInit {
  requiresAuth?: boolean;
}

export class ApiError extends Error {
  status: number;
  data: any;

  constructor(message: string, status: number, data?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

export async function request<T = any>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const { requiresAuth = true, headers = {}, ...restOptions } = options;

  const url = endpoint.startsWith('http') ? endpoint : `${BASE_URL}${endpoint}`;
  const requestHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(headers as Record<string, string>),
  };

  if (requiresAuth && inMemoryAccessToken) {
    requestHeaders['Authorization'] = `Bearer ${inMemoryAccessToken}`;
  }

  let response = await fetch(url, {
    ...restOptions,
    headers: requestHeaders,
  });

  // Handle 401 Unauthorized with silent token refresh
  if (response.status === 401 && requiresAuth) {
    const refreshToken = getStoredRefreshToken();

    if (!refreshToken) {
      clearTokens();
      throw new ApiError('Session expired. Please log in again.', 401);
    }

    if (!isRefreshing) {
      isRefreshing = true;
      try {
        const refreshResponse = await fetch(`${BASE_URL}/api/v1/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });

        if (!refreshResponse.ok) {
          clearTokens();
          throw new ApiError('Failed to refresh token', refreshResponse.status);
        }

        const data: TokenRefreshResponse = await refreshResponse.json();
        setTokens(data.access_token, data.refresh_token);
        isRefreshing = false;
        onTokenRefreshed(data.access_token);
      } catch (refreshErr) {
        isRefreshing = false;
        clearTokens();
        throw new ApiError('Session expired. Please log in again.', 401);
      }
    }

    // Wait for the token refresh to complete
    const retryPromise = new Promise<T>((resolve, reject) => {
      addRefreshSubscriber(async (newToken: string) => {
        try {
          requestHeaders['Authorization'] = `Bearer ${newToken}`;
          const retryResponse = await fetch(url, {
            ...restOptions,
            headers: requestHeaders,
          });

          if (!retryResponse.ok) {
            const errorBody = await retryResponse.json().catch(() => ({}));
            const message = errorBody.detail || `Request failed with status ${retryResponse.status}`;
            reject(new ApiError(message, retryResponse.status, errorBody));
            return;
          }

          resolve(await retryResponse.json());
        } catch (err) {
          reject(err);
        }
      });
    });

    return retryPromise;
  }

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    let message = `Request failed with status ${response.status}`;
    if (typeof errorBody.detail === 'string') {
      message = errorBody.detail;
    } else if (Array.isArray(errorBody.detail) && errorBody.detail[0]?.msg) {
      message = errorBody.detail[0].msg;
    }
    throw new ApiError(message, response.status, errorBody);
  }

  // Handle empty bodies (e.g. 204 No Content)
  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

export const apiClient = {
  get: <T = any>(endpoint: string, options?: RequestOptions) =>
    request<T>(endpoint, { ...options, method: 'GET' }),
  post: <T = any>(endpoint: string, body?: any, options?: RequestOptions) =>
    request<T>(endpoint, {
      ...options,
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    }),
  put: <T = any>(endpoint: string, body?: any, options?: RequestOptions) =>
    request<T>(endpoint, {
      ...options,
      method: 'PUT',
      body: body ? JSON.stringify(body) : undefined,
    }),
  delete: <T = any>(endpoint: string, options?: RequestOptions) =>
    request<T>(endpoint, { ...options, method: 'DELETE' }),
};
