import { useContext } from 'react';
import { WebSocketContext, WebSocketContextType } from '../context/WebSocketContext';

export function useMerchantEvents(): WebSocketContextType {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useMerchantEvents must be used within a WebSocketProvider');
  }
  return context;
}
