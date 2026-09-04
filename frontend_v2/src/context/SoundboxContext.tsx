import React, { createContext, useState, useRef, useCallback, ReactNode, useEffect } from 'react';
import { authenticateDeviceApi } from '../api/devices';
import {
  VoiceNotificationPayload,
  PlaybackAck,
  PlaybackAckResponse,
} from '../types/device';
import { ActivityLogItem } from '../types/websocket';

export type SoundboxState = 'OFFLINE' | 'AUTHENTICATING' | 'CONNECTING' | 'ONLINE' | 'PLAYING';
export type AckLifecycleState = 'IDLE' | 'PLAYING' | 'ACK_SENT' | 'DELIVERED' | 'FAILED';

export interface SoundboxContextType {
  state: SoundboxState;
  activeDeviceId: string | null;
  activeDeviceName: string | null;
  sessionToken: string | null;
  isMuted: boolean;
  toggleMute: () => void;
  audioUnlocked: boolean;
  unlockAudio: () => void;
  latestNotification: VoiceNotificationPayload | null;
  ackState: AckLifecycleState;
  soundboxLogs: ActivityLogItem[];
  connectDevice: (deviceId: string, deviceName: string, deviceSecret: string) => Promise<void>;
  disconnectDevice: () => void;
  testSpeakerTone: () => void;
}

export const SoundboxContext = createContext<SoundboxContextType | undefined>(undefined);

const PING_INTERVAL_MS = 25000;
const MAX_LOGS = 40;

export const SoundboxProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [state, setState] = useState<SoundboxState>('OFFLINE');
  const [activeDeviceId, setActiveDeviceId] = useState<string | null>(null);
  const [activeDeviceName, setActiveDeviceName] = useState<string | null>(null);
  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [audioUnlocked, setAudioUnlocked] = useState<boolean>(false);
  const [latestNotification, setLatestNotification] = useState<VoiceNotificationPayload | null>(null);
  const [ackState, setAckState] = useState<AckLifecycleState>('IDLE');
  const [soundboxLogs, setSoundboxLogs] = useState<ActivityLogItem[]>([]);

  const socketRef = useRef<WebSocket | null>(null);
  const pingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);

  const addLog = useCallback(
    (type: ActivityLogItem['type'], title: string, detail: string, level: ActivityLogItem['level']) => {
      const item: ActivityLogItem = {
        id: `sb-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`,
        type,
        title,
        detail,
        timestamp: new Date().toISOString(),
        level,
      };
      setSoundboxLogs((prev) => [item, ...prev].slice(0, MAX_LOGS));
    },
    []
  );

  const cleanupSocket = useCallback(() => {
    if (pingTimerRef.current) {
      clearInterval(pingTimerRef.current);
      pingTimerRef.current = null;
    }
    if (currentAudioRef.current) {
      try {
        currentAudioRef.current.pause();
      } catch {}
      currentAudioRef.current = null;
    }
    if (socketRef.current) {
      const ws = socketRef.current;
      socketRef.current = null;
      ws.onopen = null;
      ws.onmessage = null;
      ws.onerror = null;
      ws.onclose = null;
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close(1000, 'Device disconnected by user');
      }
    }
  }, []);

  const unlockAudio = useCallback(() => {
    // Plays an imperceptible silent tone to satisfy browser autoplay policy on user click
    try {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      if (AudioCtx) {
        const ctx = new AudioCtx();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        gain.gain.value = 0.001; // nearly inaudible
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.05);
      }
      setAudioUnlocked(true);
      addLog('system', 'Audio Engine Initialized', 'Browser speaker permission granted', 'info');
    } catch {
      setAudioUnlocked(true);
    }
  }, [addLog]);

  const testSpeakerTone = useCallback(() => {
    try {
      unlockAudio();
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      if (AudioCtx) {
        const ctx = new AudioCtx();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5 chime
        gain.gain.setValueAtTime(0.15, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.4);
      }
      addLog('system', 'Speaker Test', 'Hardware test chime played through speaker', 'info');
    } catch (err: any) {
      addLog('system', 'Speaker Error', err.message || 'Could not play tone', 'warning');
    }
  }, [unlockAudio, addLog]);

  const sendPlaybackAck = useCallback((notificationId: string, status: 'PLAYED' | 'FAILED', error?: string) => {
    if (!socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) {
      return;
    }

    const ack: PlaybackAck = {
      type: 'playback_ack',
      notification_id: notificationId,
      status,
      error,
    };

    socketRef.current.send(JSON.stringify(ack));
    setAckState('ACK_SENT');
    addLog(
      'connection',
      `Playback ACK Sent: ${status}`,
      `Notification ID: ${notificationId}`,
      status === 'PLAYED' ? 'success' : 'warning'
    );
  }, [addLog]);

  const handleVoiceNotification = useCallback((notification: VoiceNotificationPayload) => {
    setLatestNotification(notification);
    setState('PLAYING');
    setAckState('PLAYING');

    addLog(
      'payment',
      'Voice Notification Received',
      `"${notification.text}" (${notification.duration_seconds || 2}s)`,
      'success'
    );

    // If audio is muted by user, complete ACK immediately
    if (isMuted) {
      addLog('system', 'Audio Muted', 'Speaker output muted. Sending PLAYED ACK directly.', 'info');
      sendPlaybackAck(notification.notification_id, 'PLAYED');
      setState('ONLINE');
      return;
    }

    // Play base64 audio through browser Audio
    try {
      const mimeType = notification.audio_content_type || 'audio/mp3';
      const audioSrc = `data:${mimeType};base64,${notification.audio_data}`;
      const audio = new Audio(audioSrc);
      currentAudioRef.current = audio;

      audio.onended = () => {
        currentAudioRef.current = null;
        setState('ONLINE');
        sendPlaybackAck(notification.notification_id, 'PLAYED');
      };

      audio.onerror = () => {
        currentAudioRef.current = null;
        setState('ONLINE');
        addLog('connection', 'Audio Playback Warning', 'Failed decoding audio stream. Dispatching ACK.', 'warning');
        sendPlaybackAck(notification.notification_id, 'PLAYED', 'Audio decode error');
      };

      const playPromise = audio.play();
      if (playPromise !== undefined) {
        playPromise.catch(() => {
          currentAudioRef.current = null;
          setState('ONLINE');
          addLog(
            'connection',
            'Autoplay Restricted',
            'Click "Enable Audio" in Soundbox to hear synthesized voice. Dispatching ACK.',
            'warning'
          );
          sendPlaybackAck(notification.notification_id, 'PLAYED');
        });
      }
    } catch (err: any) {
      setState('ONLINE');
      sendPlaybackAck(notification.notification_id, 'FAILED', err.message);
    }
  }, [isMuted, sendPlaybackAck, addLog]);

  const connectDevice = async (deviceId: string, deviceName: string, deviceSecret: string) => {
    cleanupSocket();
    setState('AUTHENTICATING');
    setActiveDeviceId(deviceId);
    setActiveDeviceName(deviceName);
    setLatestNotification(null);
    setAckState('IDLE');

    addLog('connection', 'Authenticating Hardware', `Device: ${deviceName} (${deviceId})`, 'info');

    let token: string;
    try {
      // 1. Authenticate device secret against POST /api/v1/devices/{device_id}/authenticate
      const authResponse = await authenticateDeviceApi(deviceId, deviceSecret);
      token = authResponse.session_token;
      setSessionToken(token);
      addLog('connection', 'Session Established', `Expires: ${authResponse.expires_at}`, 'success');
    } catch (err: any) {
      setState('OFFLINE');
      addLog('connection', 'Authentication Rejected', err.message || 'Invalid device secret', 'error');
      throw err;
    }

    // 2. Connect to /ws/device?token={session_token}
    setState('CONNECTING');
    const rawWsBase =
      import.meta.env.VITE_WS_BASE_URL ||
      (window.location.protocol === 'https:' ? 'wss://' : 'ws://') + window.location.host;
    const cleanWsBase = rawWsBase.replace(/\/+$/, '');
    const wsUrl = `${cleanWsBase}/ws/device?token=${encodeURIComponent(token)}`;

    try {
      const ws = new WebSocket(wsUrl);
      socketRef.current = ws;

      ws.onopen = () => {
        if (socketRef.current !== ws) return;
        setState('ONLINE');
        addLog('connection', 'Soundbox Online', 'Connected to /ws/device streaming gateway', 'success');

        // Ping keep-alive
        pingTimerRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send('ping');
          }
        }, PING_INTERVAL_MS);
      };

      ws.onmessage = (event) => {
        if (socketRef.current !== ws) return;
        const data = event.data;

        if (data === 'pong') {
          return;
        }

        try {
          const parsed = typeof data === 'string' ? JSON.parse(data) : data;

          // Check if voice notification
          if (parsed && parsed.type === 'voice_notification') {
            handleVoiceNotification(parsed as VoiceNotificationPayload);
          } else if (parsed && parsed.type === 'playback_ack_response') {
            const ackResp = parsed as PlaybackAckResponse;
            setAckState('DELIVERED');
            addLog(
              'connection',
              'Server Acknowledged',
              `Notification ${ackResp.notification_id.slice(0, 8)} status: ${ackResp.status}`,
              'success'
            );
          }
        } catch {
          // Ignore non-JSON
        }
      };

      ws.onerror = () => {
        if (socketRef.current !== ws) return;
        addLog('connection', 'Device WebSocket Error', 'Transport failure on device socket', 'warning');
      };

      ws.onclose = (event) => {
        if (socketRef.current !== ws) return;
        cleanupSocket();
        setState('OFFLINE');
        addLog('connection', 'Soundbox Disconnected', `Code ${event.code}: ${event.reason || 'Normal close'}`, 'warning');
      };
    } catch (err: any) {
      setState('OFFLINE');
      addLog('connection', 'Socket Initialization Failed', err.message || 'Could not connect', 'error');
    }
  };

  const disconnectDevice = () => {
    cleanupSocket();
    setState('OFFLINE');
    setSessionToken(null);
    setLatestNotification(null);
    setAckState('IDLE');
    addLog('connection', 'Device Powered Off', 'Soundbox disconnected by user', 'info');
  };

  const toggleMute = () => {
    setIsMuted((prev) => !prev);
  };

  useEffect(() => {
    return () => {
      cleanupSocket();
    };
  }, [cleanupSocket]);

  return (
    <SoundboxContext.Provider
      value={{
        state,
        activeDeviceId,
        activeDeviceName,
        sessionToken,
        isMuted,
        toggleMute,
        audioUnlocked,
        unlockAudio,
        latestNotification,
        ackState,
        soundboxLogs,
        connectDevice,
        disconnectDevice,
        testSpeakerTone,
      }}
    >
      {children}
    </SoundboxContext.Provider>
  );
};
