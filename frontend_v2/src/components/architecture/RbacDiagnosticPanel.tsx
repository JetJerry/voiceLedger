import React, { useState } from 'react';
import {
  Shield,
  ShieldCheck,
  Lock,
  CheckCircle2,
  AlertTriangle,
  Code2,
  Sparkles,
} from 'lucide-react';
import {
  testOwnerRoleApi,
  testAdminRoleApi,
  testStaffRoleApi,
  RbacTestResponse,
} from '../../api/merchants';
import { useAuth } from '../../hooks/useAuth';

export const RbacDiagnosticPanel: React.FC = () => {
  const { merchant } = useAuth();

  const [activeTest, setActiveTest] = useState<'OWNER' | 'ADMIN' | 'STAFF' | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [testResult, setTestResult] = useState<{
    endpoint: string;
    requiredRole: string;
    statusCode: number;
    data?: RbacTestResponse;
    error?: string;
    testedAt: Date;
  } | null>(null);

  const runTest = async (type: 'OWNER' | 'ADMIN' | 'STAFF') => {
    setActiveTest(type);
    setLoading(true);
    setTestResult(null);

    const endpoints = {
      OWNER: { path: '/api/v1/merchants/owner-only', fn: testOwnerRoleApi },
      ADMIN: { path: '/api/v1/merchants/admin-only', fn: testAdminRoleApi },
      STAFF: { path: '/api/v1/merchants/staff-accessible', fn: testStaffRoleApi },
    };

    const target = endpoints[type];

    try {
      const res = await target.fn();
      setTestResult({
        endpoint: target.path,
        requiredRole: type === 'OWNER' ? 'OWNER' : type === 'ADMIN' ? 'OWNER or ADMIN' : 'OWNER, ADMIN, or STAFF',
        statusCode: 200,
        data: res,
        testedAt: new Date(),
      });
    } catch (err: any) {
      setTestResult({
        endpoint: target.path,
        requiredRole: type === 'OWNER' ? 'OWNER' : type === 'ADMIN' ? 'OWNER or ADMIN' : 'OWNER, ADMIN, or STAFF',
        statusCode: err.status_code || 403,
        error: err.message || '403 Forbidden: Insufficient role within merchant organization.',
        testedAt: new Date(),
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-6 sm:p-8 shadow-xs space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-5 border-b border-slate-100">
        <div>
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 mb-2">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Database RBAC Verification</span>
          </div>
          <h2 className="text-lg font-bold text-slate-900">
            Live Role-Based Access Control (RBAC) Inspector
          </h2>
          <p className="text-xs text-slate-500 mt-1 max-w-2xl leading-relaxed">
            Roles are resolved dynamically from PostgreSQL <code className="bg-slate-100 px-1 py-0.5 rounded text-2xs font-mono">merchant_users</code> on every API call. Run live probes against the backend to verify that privilege escalation is prevented at the database boundary.
          </p>
        </div>

        {merchant && (
          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs text-right shrink-0">
            <span className="text-slate-400 block text-2xs">Your Active Role:</span>
            <span className="font-bold text-blue-700 font-mono text-sm">{merchant.user_role}</span>
          </div>
        )}
      </div>

      {/* Probing Buttons Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {/* OWNER Probe */}
        <button
          type="button"
          onClick={() => runTest('OWNER')}
          disabled={loading}
          className={`p-4 rounded-xl border text-left transition-all ${
            activeTest === 'OWNER'
              ? 'border-blue-600 bg-blue-50/50 ring-2 ring-blue-600/10'
              : 'border-slate-200 bg-white hover:bg-slate-50'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-900">Probe OWNER Role</span>
            <Shield className="w-4 h-4 text-blue-600" />
          </div>
          <code className="text-3xs font-mono text-slate-400 block mt-1">/merchants/owner-only</code>
          <p className="text-2xs text-slate-500 mt-2">Requires active OWNER role</p>
        </button>

        {/* ADMIN Probe */}
        <button
          type="button"
          onClick={() => runTest('ADMIN')}
          disabled={loading}
          className={`p-4 rounded-xl border text-left transition-all ${
            activeTest === 'ADMIN'
              ? 'border-blue-600 bg-blue-50/50 ring-2 ring-blue-600/10'
              : 'border-slate-200 bg-white hover:bg-slate-50'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-900">Probe ADMIN Role</span>
            <ShieldCheck className="w-4 h-4 text-indigo-600" />
          </div>
          <code className="text-3xs font-mono text-slate-400 block mt-1">/merchants/admin-only</code>
          <p className="text-2xs text-slate-500 mt-2">Requires ADMIN or OWNER role</p>
        </button>

        {/* STAFF Probe */}
        <button
          type="button"
          onClick={() => runTest('STAFF')}
          disabled={loading}
          className={`p-4 rounded-xl border text-left transition-all ${
            activeTest === 'STAFF'
              ? 'border-blue-600 bg-blue-50/50 ring-2 ring-blue-600/10'
              : 'border-slate-200 bg-white hover:bg-slate-50'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-900">Probe STAFF Role</span>
            <Lock className="w-4 h-4 text-emerald-600" />
          </div>
          <code className="text-3xs font-mono text-slate-400 block mt-1">/merchants/staff-accessible</code>
          <p className="text-2xs text-slate-500 mt-2">Requires STAFF, ADMIN, or OWNER</p>
        </button>
      </div>

      {/* Live Probe Result Box */}
      {loading ? (
        <div className="p-8 rounded-xl bg-slate-50 border border-slate-200 text-center text-xs text-slate-500">
          <Sparkles className="w-5 h-5 text-blue-600 animate-spin mx-auto mb-2" />
          <span>Dispatching live authorization request to Render API...</span>
        </div>
      ) : testResult ? (
        <div className="p-5 rounded-xl border border-slate-200 bg-slate-50 space-y-4 animate-fadeIn">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {testResult.statusCode === 200 ? (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  HTTP {testResult.statusCode} OK — AUTHORIZED
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-red-100 text-red-800 border border-red-300">
                  <AlertTriangle className="w-3.5 h-3.5 text-red-600" />
                  HTTP {testResult.statusCode} FORBIDDEN
                </span>
              )}
              <span className="text-xs font-mono text-slate-500">{testResult.endpoint}</span>
            </div>
            <span className="text-3xs text-slate-400 font-mono">
              Tested at: {testResult.testedAt.toLocaleTimeString()}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs font-mono">
            <div className="p-3 rounded-lg bg-white border border-slate-200">
              <span className="text-slate-400 text-3xs block">Required Permission:</span>
              <span className="font-semibold text-slate-800">{testResult.requiredRole}</span>
            </div>
            <div className="p-3 rounded-lg bg-white border border-slate-200">
              <span className="text-slate-400 text-3xs block">Resolved Role from DB:</span>
              <span className="font-semibold text-blue-600">{testResult.data?.role || merchant?.user_role || 'N/A'}</span>
            </div>
            <div className="p-3 rounded-lg bg-white border border-slate-200">
              <span className="text-slate-400 text-3xs block">Bound Merchant ID:</span>
              <span className="font-semibold text-slate-700 truncate block">{testResult.data?.merchant_id || merchant?.id || 'N/A'}</span>
            </div>
          </div>

          <div>
            <span className="text-2xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1 mb-1.5">
              <Code2 className="w-3 h-3" />
              Live Server Response Body
            </span>
            <pre className="p-3 rounded-xl bg-slate-900 text-slate-200 text-3xs font-mono overflow-x-auto">
              {JSON.stringify(testResult.data || { detail: testResult.error }, null, 2)}
            </pre>
          </div>
        </div>
      ) : (
        <div className="p-6 rounded-xl bg-slate-50 border border-slate-200 text-center text-xs text-slate-500">
          Click any probe button above to test real-time server authorization on the live Render cluster.
        </div>
      )}
    </div>
  );
};
