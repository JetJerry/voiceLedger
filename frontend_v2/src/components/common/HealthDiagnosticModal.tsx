import React, { useEffect, useState } from 'react';
import {
  X,
  Activity,
  Database,
  Radio,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Code2,
} from 'lucide-react';
import { getHealthApi } from '../../api/auth';

interface HealthDiagnosticModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const HealthDiagnosticModal: React.FC<HealthDiagnosticModalProps> = ({
  isOpen,
  onClose,
}) => {
  const [data, setData] = useState<{
    status: string;
    database: string;
    redis: string;
    service: string;
    version: string;
  } | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  const fetchHealth = () => {
    setLoading(true);
    const start = performance.now();
    getHealthApi()
      .then((res) => {
        const elapsed = Math.round(performance.now() - start);
        setData(res);
        setLatencyMs(elapsed);
        setLastChecked(new Date());
      })
      .catch((err) => {
        console.error('Health probe failed:', err);
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    if (isOpen) {
      fetchHealth();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const isHealthy = data?.status === 'healthy' || data?.status === 'ok';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-fadeIn">
      <div className="bg-white rounded-2xl max-w-lg w-full shadow-2xl border border-slate-200 overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/60">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center font-bold">
              <Activity className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">System Health & Telemetry</h3>
              <p className="text-2xs text-slate-500">Live probe against <code className="bg-slate-100 px-1 py-0.5 rounded text-3xs font-mono">GET /health</code></p>
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

        {/* Body */}
        <div className="p-6 space-y-5">
          {/* Overall Health Status Banner */}
          <div
            className={`p-4 rounded-xl border flex items-center justify-between ${
              isHealthy
                ? 'bg-emerald-50/70 border-emerald-200 text-emerald-900'
                : 'bg-red-50 border-red-200 text-red-900'
            }`}
          >
            <div className="flex items-center gap-3">
              <div
                className={`w-3 h-3 rounded-full ${
                  isHealthy ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'
                }`}
              />
              <div>
                <span className="text-xs font-bold block">
                  {isHealthy ? 'All Systems Operational' : 'System Disruption Detected'}
                </span>
                <span className="text-2xs opacity-80">
                  {data?.service || 'VoiceLedger'} • v{data?.version || '2.0.0'}
                </span>
              </div>
            </div>

            {latencyMs !== null && (
              <span className="inline-flex items-center gap-1 text-2xs font-mono font-semibold px-2 py-0.5 rounded bg-white/80 border border-emerald-300">
                <Clock className="w-3 h-3 text-emerald-600" />
                {latencyMs}ms latency
              </span>
            )}
          </div>

          {/* Component Health Grid */}
          <div className="grid grid-cols-2 gap-3">
            {/* Database Component */}
            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-700 flex items-center gap-1.5">
                  <Database className="w-3.5 h-3.5 text-blue-600" />
                  PostgreSQL
                </span>
                {data?.database === 'connected' ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                ) : (
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
                )}
              </div>
              <p className="text-2xs font-mono text-slate-600">
                Status: <strong className="uppercase text-slate-800">{data?.database || 'checking'}</strong>
              </p>
              <span className="text-3xs text-slate-400 block">ACID Ledger Tables</span>
            </div>

            {/* Redis Bus Component */}
            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-700 flex items-center gap-1.5">
                  <Radio className="w-3.5 h-3.5 text-indigo-600" />
                  Redis Valkey
                </span>
                {data?.redis === 'connected' ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                ) : (
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
                )}
              </div>
              <p className="text-2xs font-mono text-slate-600">
                Status: <strong className="uppercase text-slate-800">{data?.redis || 'checking'}</strong>
              </p>
              <span className="text-3xs text-slate-400 block">Event Outbox Pub/Sub</span>
            </div>
          </div>

          {/* Raw JSON Schema Output */}
          <div>
            <span className="text-2xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1 mb-1.5">
              <Code2 className="w-3 h-3" />
              Live Health Payload
            </span>
            <pre className="p-3 rounded-xl bg-slate-900 text-slate-200 text-3xs font-mono overflow-x-auto">
              {JSON.stringify(data, null, 2)}
            </pre>
          </div>

          {lastChecked && (
            <p className="text-3xs text-slate-400 text-center font-mono">
              Last probe sent at: {lastChecked.toLocaleTimeString()}
            </p>
          )}
        </div>

        {/* Footer Actions */}
        <div className="px-6 py-3.5 border-t border-slate-100 bg-slate-50 flex items-center justify-between">
          <button
            type="button"
            onClick={fetchHealth}
            disabled={loading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-blue-600 hover:bg-blue-50 transition-colors border border-blue-200"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Probe Health Again</span>
          </button>

          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg text-xs font-semibold text-slate-700 bg-white border border-slate-200 hover:bg-slate-100 transition-colors shadow-2xs"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
