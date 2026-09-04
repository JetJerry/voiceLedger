import React, { useState } from 'react';
import {
  Volume2,
  VolumeX,
  Radio,
  Power,
  Zap,
  CheckCircle2,
  Speaker,
  Play,
  Terminal,
  Activity,
} from 'lucide-react';
import { useSoundbox } from '../../hooks/useSoundbox';
import { formatTimestamp } from '../../services/websocketParser';

interface VirtualSoundboxProps {
  initialDeviceId?: string;
  initialDeviceName?: string;
  initialSecret?: string;
}

export const VirtualSoundbox: React.FC<VirtualSoundboxProps> = ({
  initialDeviceId = '',
  initialDeviceName = '',
  initialSecret = '',
}) => {
  const {
    state,
    activeDeviceId,
    activeDeviceName,
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
    sendHeartbeat,
  } = useSoundbox();

  const [inputDeviceId, setInputDeviceId] = useState(initialDeviceId);
  const [inputDeviceName, setInputDeviceName] = useState(initialDeviceName);
  const [inputSecret, setInputSecret] = useState(initialSecret);
  const [connecting, setConnecting] = useState(false);
  const [connError, setConnError] = useState<string | null>(null);
  const [heartbeatLoading, setHeartbeatLoading] = useState(false);

  const isOnline = state === 'ONLINE' || state === 'PLAYING';
  const isPlaying = state === 'PLAYING';

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputDeviceId.trim() || !inputSecret.trim()) {
      setConnError('Please provide both Device UUID and Device Secret.');
      return;
    }

    setConnecting(true);
    setConnError(null);
    unlockAudio();

    try {
      await connectDevice(
        inputDeviceId.trim(),
        inputDeviceName.trim() || 'Counter Speaker',
        inputSecret.trim()
      );
    } catch (err: any) {
      setConnError(err.message || 'Device authentication failed.');
    } finally {
      setConnecting(false);
    }
  };

  return (
    <div className="bg-slate-900 text-slate-100 rounded-3xl p-6 shadow-xl border-4 border-slate-800 relative overflow-hidden flex flex-col justify-between max-w-md w-full mx-auto">
      {/* Top Hardware Accent Bar */}
      <div className="flex items-center justify-between pb-4 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white shadow-xs">
            <Speaker className="w-4 h-4" />
          </div>
          <div>
            <span className="text-xs font-bold tracking-wider text-slate-100 uppercase block leading-none">
              VoiceLedger Soundbox
            </span>
            <span className="text-2xs text-slate-400 font-mono">
              Hardware Simulator v1.0
            </span>
          </div>
        </div>

        {/* Triple Hardware LED Status Indicators */}
        <div className="flex items-center gap-3 bg-slate-950/70 px-3 py-1.5 rounded-full border border-slate-800">
          {/* PWR LED */}
          <div className="flex items-center gap-1">
            <span
              className={`w-2 h-2 rounded-full ${
                isOnline ? 'bg-emerald-400 shadow-sm shadow-emerald-400/50' : 'bg-slate-600'
              }`}
            />
            <span className="text-3xs font-mono text-slate-400">PWR</span>
          </div>

          {/* NET / WS LED */}
          <div className="flex items-center gap-1">
            <span
              className={`w-2 h-2 rounded-full ${
                isOnline
                  ? 'bg-blue-400 shadow-sm shadow-blue-400/50'
                  : state === 'CONNECTING'
                  ? 'bg-amber-400 animate-ping'
                  : 'bg-slate-600'
              }`}
            />
            <span className="text-3xs font-mono text-slate-400">NET</span>
          </div>

          {/* SPK / Audio LED */}
          <div className="flex items-center gap-1">
            <span
              className={`w-2 h-2 rounded-full ${
                isPlaying
                  ? 'bg-amber-400 animate-pulse shadow-sm shadow-amber-400/50'
                  : 'bg-slate-600'
              }`}
            />
            <span className="text-3xs font-mono text-slate-400">AUDIO</span>
          </div>
        </div>
      </div>

      {/* Main Hardware Display LCD Screen */}
      <div className="my-5 bg-slate-950 border border-slate-800 rounded-2xl p-4 font-mono shadow-inner relative">
        <div className="flex items-center justify-between text-2xs text-slate-500 mb-2 border-b border-slate-900 pb-1">
          <span className="flex items-center gap-1">
            <Radio className="w-3 h-3 text-blue-400" />
            <span>STREAM: /ws/device</span>
          </span>
          <span
            className={`font-bold ${
              isPlaying
                ? 'text-amber-400 animate-pulse'
                : isOnline
                ? 'text-emerald-400'
                : 'text-slate-500'
            }`}
          >
            [{state}]
          </span>
        </div>

        {/* LCD Center Text */}
        <div className="py-2 text-center">
          {isPlaying && latestNotification ? (
            <div className="space-y-1 animate-pulse">
              <span className="text-3xs uppercase tracking-widest text-amber-400">
                Incoming Voice Audio
              </span>
              <p className="text-sm font-bold text-white tracking-wide">
                "{latestNotification.text}"
              </p>
              <div className="text-3xs text-slate-400">
                Payment: {latestNotification.payment_id.slice(0, 13)}...
              </div>
            </div>
          ) : isOnline ? (
            <div className="space-y-1">
              <span className="text-3xs uppercase tracking-widest text-emerald-400">
                Hardware Online & Ready
              </span>
              <p className="text-sm font-bold text-slate-100 truncate">
                {activeDeviceName || 'Counter Soundbox'}
              </p>
              <div className="text-3xs text-slate-500 truncate">
                ID: {activeDeviceId?.slice(0, 18)}...
              </div>
            </div>
          ) : (
            <div className="space-y-1 text-slate-500">
              <span className="text-3xs uppercase tracking-widest">Device Offline</span>
              <p className="text-xs">Authenticate with Device Secret to connect</p>
            </div>
          )}
        </div>

        {/* Hardware Equalizer Waveform Visualization */}
        <div className="mt-3 pt-2 border-t border-slate-900 flex items-center justify-center gap-1 h-6">
          {[40, 70, 30, 90, 60, 100, 45, 80, 50, 95, 35, 75, 55, 85].map((height, i) => (
            <span
              key={i}
              className={`w-1 rounded-full transition-all duration-150 ${
                isPlaying
                  ? 'bg-amber-400 animate-pulse'
                  : isOnline
                  ? 'bg-blue-600/40 h-1.5'
                  : 'bg-slate-800 h-1'
              }`}
              style={{
                height: isPlaying ? `${Math.max(4, (height * (i % 3 + 1)) % 22)}px` : undefined,
              }}
            />
          ))}
        </div>
      </div>

      {/* Acknowledgement Status Indicator */}
      {isOnline && (
        <div className="mb-4 bg-slate-950/60 border border-slate-800/80 rounded-xl px-3 py-2 text-2xs font-mono flex items-center justify-between">
          <span className="text-slate-400 flex items-center gap-1.5">
            <Zap className="w-3 h-3 text-emerald-400" />
            <span>ACK Lifecycle:</span>
          </span>
          <span
            className={`font-bold ${
              ackState === 'DELIVERED'
                ? 'text-emerald-400'
                : ackState === 'ACK_SENT'
                ? 'text-blue-400'
                : ackState === 'PLAYING'
                ? 'text-amber-400'
                : 'text-slate-500'
            }`}
          >
            {ackState === 'DELIVERED'
              ? '✓ DELIVERED (Server Confirmed)'
              : ackState === 'ACK_SENT'
              ? '→ PLAYED ACK SENT'
              : ackState === 'PLAYING'
              ? '▶ PLAYING AUDIO'
              : 'IDLE (Awaiting Payment)'}
          </span>
        </div>
      )}

      {/* Hardware Connection Form OR Active Controls */}
      {!isOnline ? (
        <form onSubmit={handleConnect} className="space-y-3 pt-2">
          {connError && (
            <div className="p-2 rounded-lg bg-red-950/80 border border-red-800 text-red-300 text-xs font-sans">
              {connError}
            </div>
          )}

          <div>
            <label className="block text-2xs font-mono text-slate-400 mb-1">
              Device Label
            </label>
            <input
              type="text"
              value={inputDeviceName}
              onChange={(e) => setInputDeviceName(e.target.value)}
              placeholder="e.g. Counter Speaker 1"
              className="w-full px-3 py-1.5 text-xs font-mono bg-slate-950 border border-slate-700 rounded-lg text-slate-100 placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-2xs font-mono text-slate-400 mb-1">
              Device UUID
            </label>
            <input
              type="text"
              required
              value={inputDeviceId}
              onChange={(e) => setInputDeviceId(e.target.value)}
              placeholder="e.g. ab5ac1ad-70d2-4f1a-a3b8-288502e24994"
              className="w-full px-3 py-1.5 text-xs font-mono bg-slate-950 border border-slate-700 rounded-lg text-slate-100 placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-2xs font-mono text-slate-400 mb-1">
              One-Time Device Secret
            </label>
            <input
              type="password"
              required
              value={inputSecret}
              onChange={(e) => setInputSecret(e.target.value)}
              placeholder="••••••••••••••••••••"
              className="w-full px-3 py-1.5 text-xs font-mono bg-slate-950 border border-slate-700 rounded-lg text-slate-100 placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <button
            type="submit"
            disabled={connecting}
            className="w-full mt-2 py-2 px-4 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 disabled:opacity-50 transition-all flex items-center justify-center gap-2 shadow-sm"
          >
            <Power className="w-3.5 h-3.5" />
            <span>{connecting ? 'Authenticating...' : 'Power On & Connect'}</span>
          </button>
        </form>
      ) : (
        <div className="space-y-3 pt-2 border-t border-slate-800">
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={toggleMute}
              className={`py-2 px-3 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 border transition-colors ${
                isMuted
                  ? 'bg-amber-950/60 border-amber-800 text-amber-300'
                  : 'bg-slate-800 hover:bg-slate-700 border-slate-700 text-slate-200'
              }`}
            >
              {isMuted ? <VolumeX className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5" />}
              <span>{isMuted ? 'Muted' : 'Audio On'}</span>
            </button>

            <button
              type="button"
              onClick={testSpeakerTone}
              className="py-2 px-3 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 flex items-center justify-center gap-1.5 transition-colors"
              title="Test physical browser speaker audio output"
            >
              <Play className="w-3.5 h-3.5 text-blue-400" />
              <span>Speaker Test</span>
            </button>
          </div>

          <button
            type="button"
            disabled={heartbeatLoading}
            onClick={async () => {
              setHeartbeatLoading(true);
              try {
                await sendHeartbeat();
              } catch (e) {
                // Handled in context logs
              } finally {
                setHeartbeatLoading(false);
              }
            }}
            className="w-full py-1.5 px-3 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 text-emerald-400 text-2xs font-semibold flex items-center justify-center gap-1.5 transition-colors disabled:opacity-50"
            title="Send live hardware heartbeat to update server telemetry (/api/v1/devices/{id}/heartbeat)"
          >
            <Activity className={`w-3 h-3 ${heartbeatLoading ? 'animate-spin' : 'text-emerald-400'}`} />
            <span>{heartbeatLoading ? 'Sending Heartbeat...' : 'Send Hardware Heartbeat Ping'}</span>
          </button>

          {!audioUnlocked && (
            <button
              type="button"
              onClick={unlockAudio}
              className="w-full py-1.5 px-3 rounded-lg bg-indigo-900/60 border border-indigo-700 text-indigo-300 text-2xs font-semibold flex items-center justify-center gap-1.5"
            >
              <CheckCircle2 className="w-3 h-3 text-indigo-400" />
              <span>Click to Enable Unmuted Browser Audio</span>
            </button>
          )}

          <button
            type="button"
            onClick={disconnectDevice}
            className="w-full py-2 px-4 rounded-xl text-xs font-semibold text-slate-400 hover:text-red-400 bg-slate-950 hover:bg-red-950/30 border border-slate-800 hover:border-red-900 transition-colors flex items-center justify-center gap-1.5"
          >
            <Power className="w-3.5 h-3.5" />
            <span>Power Off Soundbox</span>
          </button>
        </div>
      )}

      {/* Mini Terminal Log */}
      <div className="mt-4 pt-3 border-t border-slate-800 text-3xs font-mono">
        <div className="flex items-center justify-between text-slate-500 mb-1.5">
          <span className="flex items-center gap-1">
            <Terminal className="w-3 h-3 text-slate-400" />
            <span>TELEMETRY CONSOLE</span>
          </span>
          <span>{soundboxLogs.length} frames</span>
        </div>
        <div className="max-h-20 overflow-y-auto space-y-1 text-slate-400 bg-slate-950/70 p-2 rounded-lg border border-slate-900">
          {soundboxLogs.length === 0 ? (
            <span className="text-slate-600 block">Awaiting hardware frames...</span>
          ) : (
            soundboxLogs.slice(0, 5).map((log) => (
              <div key={log.id} className="truncate">
                <span className="text-slate-600">{formatTimestamp(log.timestamp).slice(12)}</span>{' '}
                <span className={log.level === 'error' ? 'text-red-400' : log.level === 'success' ? 'text-emerald-400' : 'text-slate-300'}>
                  {log.title}:
                </span>{' '}
                {log.detail}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
