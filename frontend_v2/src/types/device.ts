export interface Device {
  id: string;
  merchant_id: string;
  device_name: string;
  device_type: string;
  status: string;
  is_online: boolean;
  last_seen_at: string | null;
  created_at: string;
}

export interface DeviceCreateRequest {
  device_name: string;
  device_type?: string;
}

export interface DeviceRegisterResponse {
  id: string;
  merchant_id: string;
  device_name: string;
  device_type: string;
  status: string;
  created_at: string;
  device_secret: string;
}

export interface DeviceAuthRequest {
  device_secret: string;
}

export interface DeviceAuthResponse {
  session_token: string;
  device_id: string;
  merchant_id: string;
  status: string;
  expires_at: string;
}

export interface VoiceNotificationPayload {
  type: 'voice_notification';
  notification_id: string;
  payment_id: string;
  device_id: string;
  merchant_id: string;
  audio_content_type: string;
  audio_data: string; // base64
  text: string;
  duration_seconds?: number;
}

export interface PlaybackAck {
  type: 'playback_ack';
  notification_id: string;
  status: 'PLAYED' | 'FAILED';
  error?: string;
}

export interface PlaybackAckResponse {
  type: 'playback_ack_response';
  notification_id: string;
  status: string;
}

export interface DeviceHeartbeatResponse {
  status: string;
  device_id: string;
  device_status: string;
  last_seen_at: string;
}
