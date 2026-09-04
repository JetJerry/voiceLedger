import React, { createContext, useState, useEffect, useRef, useCallback, ReactNode } from 'react';
import { useAuth } from '../hooks/useAuth';
import {
  WsConnectionStatus,
  MerchantPaymentEvent,
  ActivityLogItem,
} from '../types/websocket';
import { validateAndParsePaymentEvent } from '../services/websocketParser';

export interface WebSocketContextType {
  status: WsConnectionStatus;
  payments: MerchantPaymentEvent[];
  latestPayment: MerchantPaymentEvent | null;
  activityLogs: ActivityLogItem[];
  reconnectAttempts: number;
  lastHeartbeat: string | null;
  reconnect: () => void;
  clearEvents: () => void;
}

export const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined);

const MAX_ACTIVITY_LOGS = 50;
const PING_INTERVAL_MS = 25000;
const INITIAL_BACKOFF_MS = 1000;
const MAX_BACKOFF_MS = 15000;

export const WebSocketProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const { accessToken, merchant, isAuthenticated } = useAuth();

  const [status, setStatus] = useState<WsConnectionStatus>('DISCONNECTED');
  const [payments, setPayments] = useState<MerchantPaymentEvent[]>([]);
  const [latestPayment, setLatestPayment] = useState<MerchantPaymentEvent | null>(null);
  const [activityLogs, setActivityLogs] = useState<ActivityLogItem[]>([]);
  const [reconnectAttempts, setReconnectAttempts] = useState<number>(0);
  const [lastHeartbeat, setLastHeartbeat] = useState<string | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const pingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isManuallyClosedRef = useRef<boolean>(false);
  const currentBackoffRef = useRef<number>(INITIAL_BACKOFF_MS);

  const addActivityLog = useCallback(
    (type: ActivityLogItem['type'], title: string, detail: string, level: ActivityLogItem['level']) => {
      const newItem: ActivityLogItem = {
        id: `${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
        type,
        title,
        detail,
        timestamp: new Date().toISOString(),
        level,
      };
      setActivityLogs((prev) => [newItem, ...prev].slice(0, MAX_ACTIVITY_LOGS));
    },
    []
  );

  const cleanupSocket = useCallback(() => {
    if (pingTimerRef.current) {
      clearInterval(pingTimerRef.current);
      pingTimerRef.current = null;
    }
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (socketRef.current) {
      const ws = socketRef.current;
      socketRef.current = null;
      ws.onopen = null;
      ws.onmessage = null;
      ws.onerror = null;
      ws.onclose = null;
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close(1000, 'Client cleanup');
      }
    }
  }, []);

  const connect = useCallback(() => {
    if (!isAuthenticated || !accessToken || !merchant?.id) {
      cleanupSocket();
      setStatus('DISCONNECTED');
      return;
    }

    // Guard against duplicate active connections
    if (
      socketRef.current &&
      (socketRef.current.readyState === WebSocket.OPEN ||
        socketRef.current.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    cleanupSocket();
    isManuallyClosedRef.current = false;
    setStatus('CONNECTING');

    // Construct WebSocket URL matching backend /ws/merchant
    const rawWsBase =
      import.meta.env.VITE_WS_BASE_URL ||
      (window.location.protocol === 'https:' ? 'wss://' : 'ws://') + window.location.host;
    const cleanWsBase = rawWsBase.replace(/\/+$/, '');
    const wsUrl = `${cleanWsBase}/ws/merchant?token=${encodeURIComponent(
      accessToken
    )}&merchant_id=${encodeURIComponent(merchant.id)}`;

    try {
      const ws = new WebSocket(wsUrl);
      socketRef.current = ws;

      ws.onopen = () => {
        if (socketRef.current !== ws) return;
        setStatus('CONNECTED');
        setReconnectAttempts(0);
        currentBackoffRef.current = INITIAL_BACKOFF_MS;

        addActivityLog(
          'connection',
          'WebSocket Connected',
          `Bound to merchant channel: ${merchant.name}`,
          'success'
        );

        // Start 25s ping keep-alive interval
        pingTimerRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send('ping');
          }
        }, PING_INTERVAL_MS);
      };

      ws.onmessage = (event) => {
        if (socketRef.current !== ws) return;
        const data = event.data;

        // Handle text ping/pong keep-alive
        if (data === 'pong') {
          setLastHeartbeat(new Date().toISOString());
          return;
        }

        // Parse JSON payload
        try {
          const parsed = typeof data === 'string' ? JSON.parse(data) : data;
          const validated = validateAndParsePaymentEvent(parsed, merchant.id);

          if (validated) {
            setPayments((prev) => [validated, ...prev]);
            setLatestPayment(validated);

            addActivityLog(
              'payment',
              `Payment Received: ₹${validated.amountInr.toFixed(2)}`,
              `${validated.eventType} • ${validated.status} • ${validated.providerPaymentId}`,
              'success'
            );
          } else {
            addActivityLog(
              'system',
              'Non-Payment Event Message',
              typeof data === 'string' ? data.slice(0, 100) : 'Binary/Object payload',
              'info'
            );
          }
        } catch {
          // Ignore non-JSON text frames
        }
      };

      ws.onerror = () => {
        if (socketRef.current !== ws) return;
        addActivityLog(
          'connection',
          'WebSocket Transport Warning',
          'Encountered network error on event socket',
          'warning'
        );
      };

      ws.onclose = (event) => {
        if (socketRef.current !== ws) return;
        cleanupSocket();

        if (isManuallyClosedRef.current) {
          setStatus('DISCONNECTED');
          return;
        }

        const reasonText = event.reason || `Code ${event.code}`;
        addActivityLog(
          'connection',
          'WebSocket Disconnected',
          `Closed: ${reasonText}. Scheduling reconnect...`,
          'warning'
        );

        setStatus('RECONNECTING');
        setReconnectAttempts((prev) => prev + 1);

        // Schedule exponential backoff reconnect
        const backoff = currentBackoffRef.current;
        currentBackoffRef.current = Math.min(backoff * 2, MAX_BACKOFF_MS);

        reconnectTimerRef.current = setTimeout(() => {
          connect();
        }, backoff);
      };
    } catch (err: any) {
      setStatus('DISCONNECTED');
      addActivityLog(
        'connection',
        'Connection Initialization Failed',
        err.message || 'Unable to instantiate WebSocket',
        'error'
      );
    }
  }, [accessToken, merchant?.id, merchant?.name, isAuthenticated, cleanupSocket, addActivityLog]);

  // Connect whenever authentication and merchant are resolved
  useEffect(() => {
    if (isAuthenticated && merchant?.id && accessToken) {
      connect();
    } else {
      cleanupSocket();
      setStatus('DISCONNECTED');
    }

    return () => {
      isManuallyClosedRef.current = true;
      cleanupSocket();
    };
  }, [isAuthenticated, merchant?.id, accessToken, connect, cleanupSocket]);

  const manualReconnect = () => {
    currentBackoffRef.current = INITIAL_BACKOFF_MS;
    connect();
  };

  const clearEvents = () => {
    setPayments([]);
    setLatestPayment(null);
  };

  return (
    <WebSocketContext.Provider
      value={{
        status,
        payments,
        latestPayment,
        activityLogs,
        reconnectAttempts,
        lastHeartbeat,
        reconnect: manualReconnect,
        clearEvents,
      }}
    >
      {children}
    </WebSocketContext.Provider>
  );
};
