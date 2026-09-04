import React, { useEffect, useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { getHealthApi } from '../api/auth';
import {
  Activity,
  Server,
  Database,
  Radio,
  Clock,
  ShieldCheck,
  Store,
  CreditCard,
  Volume2,
} from 'lucide-react';

export const DashboardPage: React.FC = () => {
  const { merchant, user } = useAuth();
  const [health, setHealth] = useState<{
    status: string;
    database: string;
    redis: string;
    version: string;
  } | null>(null);

  useEffect(() => {
    let isMounted = true;
    getHealthApi()
      .then((res) => {
        if (isMounted) {
          setHealth({
            status: res.status,
            database: res.database,
            redis: res.redis,
            version: res.version,
          });
        }
      })
      .catch((err) => {
        console.error('Failed to query backend health:', err);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <div className="space-y-6">
      {/* Top Banner: Merchant Identity & Status */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-blue-50 border border-blue-200 flex items-center justify-center text-blue-600 shrink-0">
            <Store className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-bold text-slate-900 tracking-tight">
                {merchant?.name || 'Ramesh Kirana Store'}
              </h1>
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                Active Organization
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Business: {merchant?.business_type || 'Retail'} • Default Currency: {merchant?.currency || 'INR'} (₹) • Authorized as <span className="font-semibold text-slate-700">{merchant?.user_role || 'OWNER'}</span>
            </p>
            <p className="text-2xs text-slate-400 font-mono mt-0.5">
              Merchant UUID: {merchant?.id || 'Pending resolution'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <div className="px-3 py-2 rounded-xl bg-slate-50 border border-slate-200 text-right">
            <span className="text-2xs text-slate-400 block font-medium">Logged In Operator</span>
            <span className="text-xs font-semibold text-slate-800">{user?.full_name || user?.email}</span>
          </div>
        </div>
      </div>

      {/* System Infrastructure Telemetry Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* API Gateway */}
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">API Gateway</span>
            <Server className="w-4 h-4 text-blue-600" />
          </div>
          <div className="mt-2 flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-sm font-bold text-slate-800">FastAPI v{health?.version || '1.0.0'}</span>
          </div>
          <span className="text-2xs text-slate-400 mt-1 block">Live Render Cluster</span>
        </div>

        {/* PostgreSQL Database */}
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Ledger Database</span>
            <Database className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="mt-2 flex items-center gap-2">
            <span className={`w-2.5 h-2.5 rounded-full ${health?.database === 'connected' ? 'bg-emerald-500' : 'bg-amber-500'}`} />
            <span className="text-sm font-bold text-slate-800">
              {health?.database === 'connected' ? 'PostgreSQL 16' : 'Connecting...'}
            </span>
          </div>
          <span className="text-2xs text-slate-400 mt-1 block">ACID Ledger Isolation</span>
        </div>

        {/* Redis Event Bus */}
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Transactional Bus</span>
            <Radio className="w-4 h-4 text-indigo-600" />
          </div>
          <div className="mt-2 flex items-center gap-2">
            <span className={`w-2.5 h-2.5 rounded-full ${health?.redis === 'connected' ? 'bg-emerald-500' : 'bg-amber-500'}`} />
            <span className="text-sm font-bold text-slate-800">
              {health?.redis === 'connected' ? 'Redis Pub/Sub' : 'Connecting...'}
            </span>
          </div>
          <span className="text-2xs text-slate-400 mt-1 block">Tenant Channel Streaming</span>
        </div>

        {/* Financial Boundary Invariant */}
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Security Invariant</span>
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="mt-2 flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
            <span className="text-sm font-bold text-slate-800">Zero Mutation</span>
          </div>
          <span className="text-2xs text-slate-400 mt-1 block">WebSockets Cannot Mutate</span>
        </div>
      </div>

      {/* Honest Empty State Container (Prepared for Batch 3 Real-time Events) */}
      <div className="bg-white border border-slate-200 rounded-2xl p-8 shadow-xs text-center">
        <div className="max-w-md mx-auto">
          <div className="w-14 h-14 rounded-2xl bg-blue-50 border border-blue-200 flex items-center justify-center text-blue-600 mx-auto mb-4">
            <Activity className="w-7 h-7 animate-pulse" />
          </div>
          <h2 className="text-base font-bold text-slate-900">
            Listening for Inbound Payment Webhooks
          </h2>
          <p className="text-xs text-slate-500 mt-2 leading-relaxed">
            VoiceLedger is actively connected to the tenant Redis stream. When a customer scans your Razorpay QR code and makes a payment, the verified transaction card and voice notification will appear here in real time.
          </p>

          <div className="mt-6 inline-flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-600">
            <Clock className="w-3.5 h-3.5 text-blue-600 animate-spin" />
            <span>Waiting for live payment events...</span>
          </div>

          <div className="mt-6 pt-6 border-t border-slate-100 grid grid-cols-2 gap-4 text-left">
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
              <span className="text-2xs font-semibold text-slate-700 flex items-center gap-1.5">
                <CreditCard className="w-3 h-3 text-emerald-600" />
                Payment Stream
              </span>
              <p className="text-2xs text-slate-500 mt-1">
                Subscribed to /ws/merchant
              </p>
            </div>
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
              <span className="text-2xs font-semibold text-slate-700 flex items-center gap-1.5">
                <Volume2 className="w-3 h-3 text-indigo-600" />
                Voice Synthesizer
              </span>
              <p className="text-2xs text-slate-500 mt-1">
                Soundbox ready for audio playback
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
