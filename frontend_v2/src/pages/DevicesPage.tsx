import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { listDevicesApi } from '../api/devices';
import { Device, DeviceRegisterResponse } from '../types/device';
import { RegisterDeviceModal } from '../components/devices/RegisterDeviceModal';
import { VirtualSoundbox } from '../components/devices/VirtualSoundbox';
import { useSoundbox } from '../hooks/useSoundbox';
import {
  Speaker,
  Plus,
  Radio,
  CheckCircle2,
  RefreshCw,
  Cpu,
  ArrowRight,
} from 'lucide-react';
import { formatTimestamp } from '../services/websocketParser';

export const DevicesPage: React.FC = () => {
  const navigate = useNavigate();
  const { merchant } = useAuth();
  const { connectDevice } = useSoundbox();

  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);

  // Auto-fill props for the simulator
  const [simDeviceId, setSimDeviceId] = useState<string>('');
  const [simDeviceName, setSimDeviceName] = useState<string>('');
  const [simSecret, setSimSecret] = useState<string>('');

  const fetchDevices = useCallback(async () => {
    if (!merchant?.id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await listDevicesApi(merchant.id);
      setDevices(data);
      if (data.length > 0 && !simDeviceId) {
        setSimDeviceId(data[0].id);
        setSimDeviceName(data[0].device_name);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to fetch registered Soundboxes.');
    } finally {
      setLoading(false);
    }
  }, [merchant?.id, simDeviceId]);

  useEffect(() => {
    fetchDevices();
  }, [fetchDevices]);

  const handleDeviceRegistered = async (device: DeviceRegisterResponse, autoConnect: boolean) => {
    await fetchDevices();
    setSimDeviceId(device.id);
    setSimDeviceName(device.device_name);
    setSimSecret(device.device_secret);

    if (autoConnect) {
      try {
        await connectDevice(device.id, device.device_name, device.device_secret);
      } catch (err) {
        console.error('Auto-connect to simulator failed:', err);
      }
    }
  };

  const handleSelectForSimulator = (d: Device) => {
    setSimDeviceId(d.id);
    setSimDeviceName(d.device_name);
  };

  return (
    <div className="space-y-6">
      {/* Top Banner: Fleet Telemetry & Provision Action */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-600 shrink-0">
            <Speaker className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-bold text-slate-900 tracking-tight">
                Soundbox Fleet & Telemetry
              </h1>
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
                {devices.length} Registered
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Manage physical soundboxes and launch the interactive Virtual Soundbox simulator.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={fetchDevices}
            disabled={loading}
            className="p-2 border border-slate-200 rounded-xl hover:bg-slate-50 text-slate-600 transition-colors shadow-2xs"
            title="Refresh device fleet"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>

          <button
            onClick={() => setIsModalOpen(true)}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 shadow-sm transition-all"
          >
            <Plus className="w-4 h-4" />
            <span>Provision New Soundbox</span>
          </button>
        </div>
      </div>

      {/* Main Split Content: Device Fleet Table (Left) + Hardware Simulator (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column (7 cols): Fleet Inventory */}
        <div className="lg:col-span-7 space-y-4">
          <div className="bg-white border border-slate-200 rounded-2xl shadow-xs overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-slate-900">Provisioned Audio Terminals</h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Devices authenticated against <code className="text-2xs bg-slate-100 px-1 py-0.5 rounded">/ws/device</code>.
                </p>
              </div>
            </div>

            {loading && devices.length === 0 ? (
              <div className="py-12 text-center text-xs text-slate-400">
                <Radio className="w-6 h-6 mx-auto mb-2 text-slate-300 animate-pulse" />
                <span>Loading fleet telemetry...</span>
              </div>
            ) : error ? (
              <div className="p-6 text-center text-xs text-red-600">
                <span>{error}</span>
              </div>
            ) : devices.length === 0 ? (
              <div className="py-12 text-center text-xs text-slate-400">
                <Speaker className="w-8 h-8 mx-auto mb-2 text-slate-300" />
                <p className="font-semibold text-slate-600">No Soundbox Devices Provisioned Yet</p>
                <p className="text-2xs mt-1 max-w-sm mx-auto">
                  Click "Provision New Soundbox" to register a hardware terminal and generate your one-time secret.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
                  <thead className="bg-slate-50 text-slate-500 font-semibold uppercase tracking-wider">
                    <tr>
                      <th scope="col" className="px-6 py-3">Device Label</th>
                      <th scope="col" className="px-6 py-3">Status</th>
                      <th scope="col" className="px-6 py-3">Last Seen</th>
                      <th scope="col" className="px-6 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 bg-white">
                    {devices.map((d) => {
                      const isSimTarget = d.id === simDeviceId;

                      return (
                        <tr
                          key={d.id}
                          className={`hover:bg-slate-50 transition-colors ${
                            isSimTarget ? 'bg-indigo-50/40' : ''
                          }`}
                        >
                          <td className="px-6 py-3.5 whitespace-nowrap">
                            <div className="flex items-center gap-2.5">
                              <div className="w-7 h-7 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center shrink-0">
                                <Speaker className="w-4 h-4" />
                              </div>
                              <div>
                                <span className="font-bold text-slate-900 block">{d.device_name}</span>
                                <span className="text-3xs text-slate-400 font-mono">
                                  {d.id.slice(0, 16)}...
                                </span>
                              </div>
                            </div>
                          </td>

                          <td className="px-6 py-3.5 whitespace-nowrap">
                            <span
                              className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-2xs font-semibold ${
                                d.is_online
                                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                  : 'bg-slate-100 text-slate-600 border border-slate-200'
                              }`}
                            >
                              <span
                                className={`w-1.5 h-1.5 rounded-full ${
                                  d.is_online ? 'bg-emerald-500 animate-pulse' : 'bg-slate-400'
                                }`}
                              />
                              {d.is_online ? 'Online' : 'Offline'}
                            </span>
                          </td>

                          <td className="px-6 py-3.5 whitespace-nowrap font-mono text-2xs text-slate-500">
                            {d.last_seen_at ? formatTimestamp(d.last_seen_at) : 'Never'}
                          </td>

                          <td className="px-6 py-3.5 whitespace-nowrap text-right">
                            <button
                              type="button"
                              onClick={() => handleSelectForSimulator(d)}
                              className="px-2.5 py-1 text-2xs font-semibold rounded-lg bg-white border border-slate-200 hover:bg-indigo-50 hover:text-indigo-600 transition-colors shadow-2xs"
                            >
                              Select in Simulator
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Architecture Callout */}
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-600 space-y-2">
            <span className="font-bold text-slate-800 flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              Physical & Virtual Audio Telemetry
            </span>
            <p className="text-2xs text-slate-500 leading-relaxed">
              Every soundbox exchanges its one-time provision secret for an active session bearer token. When a verified payment is captured, the backend synthesizes voice audio and pushes it to <code className="bg-white px-1 border rounded">/ws/device</code>. The device plays the audio and sends a <code className="bg-white px-1 border rounded">playback_ack</code>, transitioning the ledger notification to <strong>DELIVERED</strong>.
            </p>
            <div>
              <button
                type="button"
                onClick={() => navigate('/architecture')}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 text-2xs font-semibold rounded-lg bg-white border border-slate-200 text-slate-700 hover:bg-slate-100 hover:text-blue-600 transition-colors shadow-2xs"
              >
                <Cpu className="w-3 h-3 text-amber-600" />
                <span>Inspect End-to-End Pipeline & Invariants</span>
                <ArrowRight className="w-3 h-3" />
              </button>
            </div>
          </div>
        </div>

        {/* Right Column (5 cols): Hardware Simulator */}
        <div className="lg:col-span-5">
          <VirtualSoundbox
            key={simDeviceId + simSecret}
            initialDeviceId={simDeviceId}
            initialDeviceName={simDeviceName}
            initialSecret={simSecret}
          />
        </div>
      </div>

      {/* Modal for Provisioning */}
      <RegisterDeviceModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        merchantId={merchant?.id || ''}
        onDeviceRegistered={handleDeviceRegistered}
      />
    </div>
  );
};
