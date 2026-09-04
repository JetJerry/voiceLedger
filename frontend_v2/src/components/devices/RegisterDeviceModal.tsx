import React, { useState } from 'react';
import { X, Speaker, KeyRound, Copy, Check, ShieldAlert, Zap } from 'lucide-react';
import { registerDeviceApi } from '../../api/devices';
import { DeviceRegisterResponse } from '../../types/device';

interface RegisterDeviceModalProps {
  isOpen: boolean;
  onClose: () => void;
  merchantId: string;
  onDeviceRegistered: (device: DeviceRegisterResponse, autoConnect: boolean) => void;
}

export const RegisterDeviceModal: React.FC<RegisterDeviceModalProps> = ({
  isOpen,
  onClose,
  merchantId,
  onDeviceRegistered,
}) => {
  const [deviceName, setDeviceName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [provisionedData, setProvisionedData] = useState<DeviceRegisterResponse | null>(null);
  const [copied, setCopied] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!deviceName.trim()) {
      setError('Please provide a name for this Soundbox.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await registerDeviceApi(merchantId, {
        device_name: deviceName.trim(),
        device_type: 'SOUNDBOX',
      });
      setProvisionedData(response);
    } catch (err: any) {
      setError(err.message || 'Failed to register Soundbox device.');
    } finally {
      setLoading(false);
    }
  };

  const handleCopySecret = () => {
    if (provisionedData?.device_secret) {
      navigator.clipboard.writeText(provisionedData.device_secret);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleClose = () => {
    setProvisionedData(null);
    setDeviceName('');
    setError(null);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-xl max-w-md w-full p-6 animate-scaleIn relative">
        <button
          onClick={handleClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        {!provisionedData ? (
          <div>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-600">
                <Speaker className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900">Provision Soundbox</h3>
                <p className="text-xs text-slate-500">Register a hardware or virtual audio terminal</p>
              </div>
            </div>

            {error && (
              <div className="mb-4 p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs">
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Device Label / Location
                </label>
                <input
                  type="text"
                  required
                  value={deviceName}
                  onChange={(e) => setDeviceName(e.target.value)}
                  placeholder="e.g. Counter Soundbox 02"
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent bg-white text-slate-900 placeholder:text-slate-400"
                />
                <span className="text-2xs text-slate-400 mt-1 block">
                  Hardware Type: SOUNDBOX • Enforces Level 1 Audio Telemetry
                </span>
              </div>

              <div className="pt-2 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={handleClose}
                  className="px-4 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm disabled:opacity-50 transition-all flex items-center gap-1.5"
                >
                  {loading ? 'Generating Provision Keys...' : 'Register Hardware'}
                </button>
              </div>
            </form>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-600">
                <KeyRound className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900">Device Provisioned</h3>
                <p className="text-xs text-slate-500">{provisionedData.device_name}</p>
              </div>
            </div>

            <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs flex items-start gap-2">
              <ShieldAlert className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <p>
                <strong>One-Time Device Secret:</strong> This secret is returned <em>only once</em> upon registration. Save it or immediately connect it to the simulator.
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Provision Secret
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  readOnly
                  value={provisionedData.device_secret}
                  className="flex-1 font-mono text-xs px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-800 select-all"
                />
                <button
                  type="button"
                  onClick={handleCopySecret}
                  className="p-2 border border-slate-200 rounded-lg hover:bg-slate-100 text-slate-600 transition-colors shrink-0 shadow-2xs"
                  title="Copy secret"
                >
                  {copied ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div className="pt-3 border-t border-slate-100 flex flex-col gap-2">
              <button
                type="button"
                onClick={() => {
                  onDeviceRegistered(provisionedData, true);
                  handleClose();
                }}
                className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-bold shadow-sm transition-colors flex items-center justify-center gap-2"
              >
                <Zap className="w-4 h-4" />
                <span>Launch in Virtual Soundbox Simulator</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  onDeviceRegistered(provisionedData, false);
                  handleClose();
                }}
                className="w-full py-2 px-4 text-xs font-medium text-slate-600 hover:bg-slate-50 rounded-lg transition-colors border border-slate-200"
              >
                Done (Save Secret Later)
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
