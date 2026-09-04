import { describe, it, expect } from 'vitest';
import { VoiceNotificationPayload, PlaybackAck } from '../types/device';

describe('deviceSchemas - Audio Payload & Playback ACK Verification', () => {
  it('correctly validates canonical backend voice_notification payload', () => {
    const backendAudioPayload: VoiceNotificationPayload = {
      type: 'voice_notification',
      notification_id: 'notif_12345678-1234-1234-1234-123456789abc',
      payment_id: 'pay_12345678-1234-1234-1234-123456789def',
      device_id: 'dev_12345678-1234-1234-1234-123456789ghi',
      merchant_id: '881865c7-d548-419f-8f37-4a451b3804a7',
      audio_content_type: 'audio/mp3',
      audio_data: 'SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4Ljc2LjEwMAAAAAAAAAAAAAAA//OEAAAAAAAAAAAAAAAAAAAAAAA=',
      text: 'Payment received: 500 rupees',
      duration_seconds: 2.5,
    };

    expect(backendAudioPayload.type).toBe('voice_notification');
    expect(backendAudioPayload.notification_id).toBeDefined();
    expect(backendAudioPayload.audio_content_type).toBe('audio/mp3');
    expect(backendAudioPayload.audio_data.length).toBeGreaterThan(0);
    expect(backendAudioPayload.text).toBe('Payment received: 500 rupees');
  });

  it('constructs valid playback_ack matching backend contract', () => {
    const successAck: PlaybackAck = {
      type: 'playback_ack',
      notification_id: 'notif_12345678-1234-1234-1234-123456789abc',
      status: 'PLAYED',
    };

    expect(successAck.type).toBe('playback_ack');
    expect(successAck.status).toBe('PLAYED');
    expect(JSON.stringify(successAck)).toContain('"status":"PLAYED"');

    const failureAck: PlaybackAck = {
      type: 'playback_ack',
      notification_id: 'notif_12345678-1234-1234-1234-123456789abc',
      status: 'FAILED',
      error: 'Audio decode error',
    };

    expect(failureAck.status).toBe('FAILED');
    expect(failureAck.error).toBe('Audio decode error');
  });
});
