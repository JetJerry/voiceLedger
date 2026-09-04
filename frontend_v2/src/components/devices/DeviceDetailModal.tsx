import React, { useEffect, useState } from 'react';
import {
  X,
  Speaker,
  ShieldCheck,
  Clock,
  Key,
  Radio,
  Check,
  Copy,
} from 'lucide-react';
import { Device } from '../../types/device';
import { ResourceAccessResponse } from '../../types/merchant';
import { checkDeviceAccessApi, checkDeviceSessionAccessApi } from '../../api/merchants';
import { formatTimestamp } from '../../services/websocketParser';

interface DeviceDetailModalProps {
  device: Device | null;
  sessionId?: string;
  isOpen: boolean;
  onClose: () => void;
}

export const DeviceDetailModal: React.FC<DeviceDetailModalProps> = ({
  device,
  sessionId,
  isOpen,
  onClose,
}) => {
  const [deviceAccess, setDeviceAccess] = useState<ResourceAccessResponse | null>(null);
  const [sessionAccess, setSessionAccess] = useState<ResourceAccessResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<boolean>(false);

  useEffect(() => {
    if (!isOpen || !device?.id) {
      setDeviceAccess(null);
      setSessionAccess(null);
      setError(null);
      return;
    }

    let isMounted = true;
    setLoading(true);
    setError(null);

    Promise.all([
      checkDeviceAccessApi(device.id).catch((err) => {
        console.error('Device access probe failed:', err);
        return null;
      }),
      sessionId
        ? checkDeviceSessionAccessApi(sessionId).catch((err) => {
            console.error('Session access probe failed:', err);
            return null;
          })
        : Promise.resolve(null),
    ])
      .then(([devRes, sessRes]) => {
        if (isMounted) {
          setDeviceAccess(devRes);
          setSessionAccess(sessRes);
          if (!devRes) {
            setError('Tenant verification failed: Device not authorized under active merchant.');
          }
        }
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, device?.id, sessionId]);

  if (!isOpen || !device) return null;

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-fadeIn">
      <div className="bg-white rounded-2xl max-w-lg w-full shadow-2xl border border-slate-200 overflow-hidden">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/60">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-100 text-indigo-700 flex items-center justify-center font-bold">
              <Speaker className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">Soundbox Hardware Audit</h3>
              <p className="text-2xs text-slate-500">
                Verified via <code className="bg-slate-100 px-1 py-0.5 rounded text-3xs font-mono">GET /api/v1/merchants/devices/{'{id}'}</code>
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-5">
          {error && (
            <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs">
              {error}
            </div>
          )}

          {/* Device Summary Card */}
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-sm font-bold text-slate-900">{device.device_name}</h4>
                <span className="text-2xs text-slate-500 font-medium">Model: {device.device_type || 'VoiceLedger V1 Pro'}</span>
              </div>
              <span
                className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-2xs font-semibold ${
                  device.is_online
                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                    : 'bg-slate-100 text-slate-600 border border-slate-200'
                }`}
              >
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    device.is_online ? 'bg-emerald-500 animate-pulse' : 'bg-slate-400'
                  }`}
                />
                {device.is_online ? 'Online' : 'Offline'}
              </span>
            </div>

            <div className="space-y-1.5 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-slate-500 flex items-center gap-1.5">
                  <Key className="w-3.5 h-3.5 text-slate-400" />
                  Device UUID:
                </span>
                <div className="flex items-center gap-1.5">
                  <span className="font-mono text-2xs text-slate-700">{device.id}</span>
                  <button
                    type="button"
                    onClick={() => handleCopy(device.id)}
                    className="p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-200 transition-colors"
                  >
                    {copied ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-slate-500 flex items-center gap-1.5">
                  <Radio className="w-3.5 h-3.5 text-slate-400" />
                  Last Heartbeat:
                </span>
                <span className="font-mono text-2xs text-slate-700">
                  {device.last_seen_at ? formatTimestamp(device.last_seen_at) : 'Never'}
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-slate-500 flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5 text-slate-400" />
                  Provisioned On:
                </span>
                <span className="text-2xs text-slate-700">
                  {new Date(device.created_at).toLocaleDateString(undefined, {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric',
                  })}
                </span>
              </div>
            </div>
          </div>

          {/* Database Verification Status */}
          <div className="p-3.5 rounded-xl bg-blue-50/60 border border-blue-100 space-y-2 text-xs">
            <span className="text-2xs font-bold uppercase tracking-wider text-blue-700 flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5" />
              Tenant Authorization Audit
            </span>

            {loading ? (
              <p className="text-2xs text-slate-500 animate-pulse">Verifying database record...</p>
            ) : deviceAccess ? (
              <div className="space-y-1 text-2xs font-mono">
                <div className="flex justify-between">
                  <span className="text-slate-500">Query Status:</span>
                  <span className="text-emerald-700 font-semibold">200 OK (AUTHORIZED)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Resource Type:</span>
                  <span className="text-slate-700">{deviceAccess.resource_type}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Bound Merchant:</span>
                  <span className="text-slate-700 truncate max-w-[200px]">{deviceAccess.merchant_id}</span>
                </div>
              </div>
            ) : null}

            {sessionAccess && (
              <div className="pt-2 border-t border-blue-100 space-y-1 text-2xs font-mono">
                <div className="flex justify-between">
                  <span className="text-slate-500">Session Resource:</span>
                  <span className="text-emerald-700 font-semibold">ACTIVE SESSION VALIDATED</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Session ID:</span>
                  <span className="text-slate-700 truncate max-w-[200px]">{sessionAccess.resource_id}</span>
                </div>
              </div>
            )}
          </div>

          {/* Security Invariants Callout */}
          <div className="p-3 rounded-xl bg-slate-50 border border-slate-100 text-3xs text-slate-500 space-y-1">
            <span className="font-semibold text-slate-700 block">Soundbox Security Architecture:</span>
            <p>• Secrets hashed via Argon2id upon provisioning; never displayed again</p>
            <p>• Short-lived session bearer token (`devsess_...`) used for WebSocket streaming</p>
            <p>• Strictly partitioned by merchant UUID in PostgreSQL</p>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3.5 border-t border-slate-100 bg-slate-50 flex items-center justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg text-xs font-semibold text-slate-700 bg-white border border-slate-200 hover:bg-slate-100 transition-colors shadow-2xs"
          >
            Close Audit
          </button>
        </div>
      </div>
    </div>
  );
};
