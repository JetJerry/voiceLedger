import { Platform } from 'react-native';

// Default API base URL
let customApiBase = null;

export const getApiBase = () => {
  if (customApiBase) {
    return customApiBase;
  }
  
  if (Platform.OS === 'web') {
    if (typeof window !== 'undefined' && window.location) {
      const hostname = window.location.hostname;
      // If served directly from FastAPI (port 8000), use relative /api
      if (window.location.port === '8000') {
        return '/api';
      }
      // If running on Metro web dev server (port 8081), point to backend at port 8000
      return `http://${hostname}:8000/api`;
    }
    return 'http://localhost:8000/api';
  }
  
  // Mobile (Android / iOS simulator or physical device via Expo Go)
  // For physical devices, user can configure their PC's LAN IP via the header settings modal
  return 'http://localhost:8000/api';
};

export const setCustomApiBase = (url) => {
  customApiBase = url ? (url.endsWith('/api') ? url : `${url.replace(/\/+$/, '')}/api`) : null;
};
