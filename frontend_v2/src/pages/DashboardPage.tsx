import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { useMerchantEvents } from '../hooks/useMerchantEvents';
import { getHealthApi } from '../api/auth';
import { ConnectionBadge } from '../components/dashboard/ConnectionBadge';
import { LivePaymentHero } from '../components/dashboard/LivePaymentHero';
import { PaymentFeedTable } from '../components/dashboard/PaymentFeedTable';
import { ActivityFeed } from '../components/dashboard/ActivityFeed';
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
  Trash2,
  Speaker,
  Cpu,
} from 'lucide-react';

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const { merchant } = useAuth();
  const { payments, latestPayment, activityLogs, clearEvents } = useMerchantEvents();

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
      {/* Top Banner: Merchant Identity & Live Connection Badge */}
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
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                Active Merchant
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Business: {merchant?.business_type || 'Retail Grocery'} • Default Currency: {merchant?.currency || 'INR'} (₹) • Authorized as{' '}
              <span className="font-semibold text-slate-700">{merchant?.user_role || 'OWNER'}</span>
            </p>
            <p className="text-2xs text-slate-400 font-mono mt-0.5">
              Merchant UUID: {merchant?.id || 'Pending'}
            </p>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 shrink-0">
          <ConnectionBadge />

          {payments.length > 0 && (
            <button
              onClick={clearEvents}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 text-xs font-medium text-slate-600 hover:text-red-600 hover:bg-red-50 transition-colors shadow-2xs"
              title="Reset session payment cards for next presentation"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Clear Session Feed</span>
            </button>
          )}
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
            <span className="text-sm font-bold text-slate-800">
              FastAPI v{health?.version || '1.0.0'}
            </span>
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
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                health?.database === 'connected' ? 'bg-emerald-500' : 'bg-amber-500'
              }`}
            />
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
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                health?.redis === 'connected' ? 'bg-emerald-500' : 'bg-amber-500'
              }`}
            />
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

      {/* Main Operations Body: Hero Payment OR Honest Empty State */}
      {latestPayment ? (
        <div className="space-y-6">
          {/* Latest Payment Hero Card */}
          <LivePaymentHero payment={latestPayment} />

          {/* Grid: Payment Feed Table & Compact Activity Stream */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-8">
              <PaymentFeedTable payments={payments} />
            </div>
            <div className="lg:col-span-4">
              <ActivityFeed logs={activityLogs} />
            </div>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Honest Empty State Banner */}
          <div className="lg:col-span-8 bg-white border border-slate-200 rounded-2xl p-8 shadow-xs text-center flex flex-col justify-center">
            <div className="max-w-md mx-auto">
              <div className="w-14 h-14 rounded-2xl bg-blue-50 border border-blue-200 flex items-center justify-center text-blue-600 mx-auto mb-4 shadow-2xs">
                <Activity className="w-7 h-7 animate-pulse" />
              </div>
              <h2 className="text-base font-bold text-slate-900">
                Listening for Inbound Payment Webhooks
              </h2>
              <p className="text-xs text-slate-500 mt-2 leading-relaxed">
                VoiceLedger is subscribed to the merchant Redis event stream via WebSocket. When a customer pays via UPI or card, the verified transaction card and verification steps will appear here in real time.
              </p>

              <div className="mt-6 inline-flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-600">
                <Clock className="w-3.5 h-3.5 text-blue-600 animate-spin" />
                <span>Waiting for live payment events...</span>
              </div>

              {/* Demo presentation shortcuts */}
              <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
                <button
                  type="button"
                  onClick={() => navigate('/devices')}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-indigo-50 border border-indigo-200 text-indigo-700 text-xs font-semibold hover:bg-indigo-100 transition-colors shadow-2xs"
                >
                  <Speaker className="w-3.5 h-3.5" />
                  <span>Launch Soundbox Simulator</span>
                </button>
                <button
                  type="button"
                  onClick={() => navigate('/architecture')}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-100 border border-slate-200 text-slate-700 text-xs font-semibold hover:bg-slate-200 transition-colors shadow-2xs"
                >
                  <Cpu className="w-3.5 h-3.5 text-amber-600" />
                  <span>View System Architecture</span>
                </button>
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
                    Soundbox ready for audio dispatch
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Activity Stream in Empty State */}
          <div className="lg:col-span-4">
            <ActivityFeed logs={activityLogs} />
          </div>
        </div>
      )}
    </div>
  );
};
