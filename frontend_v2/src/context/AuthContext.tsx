import React, { createContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { User, UserLoginRequest, UserRegisterRequest, UserRegisterResponse } from '../types/auth';
import { MerchantContext } from '../types/merchant';
import { loginApi, registerApi, logoutApi, getMeApi, refreshTokenApi } from '../api/auth';
import { getMerchantContextApi } from '../api/merchants';
import { getStoredRefreshToken, getAccessToken, clearTokens } from '../api/client';

export interface AuthContextType {
  user: User | null;
  merchant: MerchantContext | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: UserLoginRequest) => Promise<void>;
  register: (data: UserRegisterRequest) => Promise<UserRegisterResponse>;
  logout: () => Promise<void>;
  refreshMerchantContext: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [merchant, setMerchant] = useState<MerchantContext | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(getAccessToken());
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const fetchMerchantContext = useCallback(async () => {
    try {
      const ctx = await getMerchantContextApi();
      setMerchant(ctx);
    } catch (err) {
      console.warn('Could not load merchant context:', err);
      setMerchant(null);
    }
  }, []);

  // Initialize session from stored refresh token upon app load
  useEffect(() => {
    let isMounted = true;

    async function initAuth() {
      const storedRefreshToken = getStoredRefreshToken();
      if (!storedRefreshToken) {
        if (isMounted) setIsLoading(false);
        return;
      }

      try {
        // Exchange refresh token for fresh access token
        const refreshRes = await refreshTokenApi(storedRefreshToken);
        if (!isMounted) return;
        setAccessToken(refreshRes.access_token);

        // Fetch user profile and merchant tenancy
        const [meUser, merchantCtx] = await Promise.all([
          getMeApi().catch(() => null),
          getMerchantContextApi().catch(() => null),
        ]);

        if (isMounted) {
          if (meUser) {
            setUser(meUser);
            setMerchant(merchantCtx);
          } else {
            clearTokens();
            setUser(null);
            setMerchant(null);
            setAccessToken(null);
          }
        }
      } catch (err) {
        if (isMounted) {
          clearTokens();
          setUser(null);
          setMerchant(null);
          setAccessToken(null);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    initAuth();

    return () => {
      isMounted = false;
    };
  }, []);

  const login = async (credentials: UserLoginRequest) => {
    setIsLoading(true);
    try {
      const authRes = await loginApi(credentials);
      setUser(authRes.user);
      setAccessToken(authRes.access_token);

      // Fetch active merchant context
      try {
        const merchantCtx = await getMerchantContextApi();
        setMerchant(merchantCtx);
      } catch (ctxErr) {
        console.warn('User authenticated but merchant context could not be resolved:', ctxErr);
        setMerchant(null);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (data: UserRegisterRequest): Promise<UserRegisterResponse> => {
    setIsLoading(true);
    try {
      const regRes = await registerApi(data);
      return regRes;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    setIsLoading(true);
    try {
      await logoutApi();
    } catch (err) {
      console.warn('Logout API error:', err);
    } finally {
      setUser(null);
      setMerchant(null);
      setAccessToken(null);
      clearTokens();
      setIsLoading(false);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        merchant,
        accessToken,
        isAuthenticated: Boolean(user && accessToken),
        isLoading,
        login,
        register,
        logout,
        refreshMerchantContext: fetchMerchantContext,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};
