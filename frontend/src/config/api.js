import { Platform } from 'react-native';

export const DEFAULT_MODAL_API_URL = 'https://rishil-cloud-mail--voiceledger-backend-fastapi-app.modal.run/api';

// Custom API base override (can be set at runtime or loaded from localStorage)
let customApiBase = null;

export const getApiBase = () => {
  // 1. Runtime override
  if (customApiBase) {
    return customApiBase;
  }

  // 2. Build-time environment variable (Vercel / Expo Web production build)
  const envApiUrl = process.env.EXPO_PUBLIC_API_URL;
  if (envApiUrl && envApiUrl.trim()) {
    const cleanUrl = envApiUrl.trim().replace(/\/+$/, '');
    return cleanUrl.endsWith('/api') ? cleanUrl : `${cleanUrl}/api`;
  }

  // 3. Web browser environment
  if (Platform.OS === 'web' && typeof window !== 'undefined' && window.location) {
    // Check localStorage for saved custom backend URL
    try {
      const saved = window.localStorage.getItem('voiceledger_backend_url');
      if (saved && saved.trim()) {
        const clean = saved.trim().replace(/\/+$/, '');
        return clean.endsWith('/api') ? clean : `${clean}/api`;
      }
    } catch (e) {
      // localStorage may be restricted in some sandboxes
    }

    const { hostname, port, origin } = window.location;

    // If served locally on port 8000 (monolithic FastAPI + React bundle), use relative /api
    if (port === '8000') {
      return '/api';
    }

    // If running on local Metro bundler (port 8081 / 19006)
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      return `http://${hostname}:8000/api`;
    }

    // If deployed on Vercel or cloud web: use Modal Backend API
    return DEFAULT_MODAL_API_URL;
  }

  // 4. Mobile Simulator / Physical Device fallback
  return DEFAULT_MODAL_API_URL;
};

export const setCustomApiBase = (url) => {
  if (url && url.trim()) {
    const clean = url.trim().replace(/\/+$/, '');
    customApiBase = clean.endsWith('/api') ? clean : `${clean}/api`;
    if (Platform.OS === 'web' && typeof window !== 'undefined') {
      try {
        window.localStorage.setItem('voiceledger_backend_url', customApiBase);
      } catch (e) {}
    }
  } else {
    customApiBase = null;
    if (Platform.OS === 'web' && typeof window !== 'undefined') {
      try {
        window.localStorage.removeItem('voiceledger_backend_url');
      } catch (e) {}
    }
  }
};
