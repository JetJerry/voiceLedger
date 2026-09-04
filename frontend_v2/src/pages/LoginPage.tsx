import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Volume2, ShieldCheck, Lock, Mail, ArrowRight, Sparkles, AlertCircle, Server } from 'lucide-react';
import { getHealthApi } from '../api/auth';
import { useAuth } from '../hooks/useAuth';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { login, isAuthenticated } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [healthStatus, setHealthStatus] = useState<'checking' | 'healthy' | 'offline'>('checking');
  const [backendMeta, setBackendMeta] = useState<{ version?: string; database?: string; redis?: string } | null>(null);

  // If already authenticated, redirect to dashboard
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/', { replace: true });
    }
  }, [isAuthenticated, navigate]);

  // Check optional demo env vars without hardcoding any secrets in source code
  const demoEmail = import.meta.env.VITE_DEMO_EMAIL || '';
  const demoPassword = import.meta.env.VITE_DEMO_PASSWORD || '';
  const hasDemoEnv = Boolean(demoEmail && demoPassword);

  useEffect(() => {
    let isMounted = true;
    getHealthApi()
      .then((res) => {
        if (isMounted) {
          if (res.status === 'healthy' || res.status === 'ok') {
            setHealthStatus('healthy');
            setBackendMeta({
              version: res.version,
              database: res.database,
              redis: res.redis,
            });
          } else {
            setHealthStatus('offline');
          }
        }
      })
      .catch(() => {
        if (isMounted) {
          setHealthStatus('offline');
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const handleQuickFill = () => {
    if (hasDemoEnv) {
      setEmail(demoEmail);
      setPassword(demoPassword);
      setError(null);
    } else {
      setError('Demo credentials not set. Configure VITE_DEMO_EMAIL and VITE_DEMO_PASSWORD in local .env');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password) {
      setError('Please enter both email and password.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await login({ email: email.trim(), password });
      navigate('/');
    } catch (err: any) {
      setError(err.message || 'Login failed. Please verify your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      {/* Top Header Branding */}
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <div className="flex items-center justify-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-blue-600 flex items-center justify-center text-white shadow-md shadow-blue-500/20">
            <Volume2 className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
              VoiceLedger
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
                v2.0
              </span>
            </h1>
            <p className="text-xs text-slate-500 font-medium">Real-Time Payment Voice Notification Engine</p>
          </div>
        </div>

        {/* Live System Health Pill */}
        <div className="mt-4 flex items-center justify-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white border border-slate-200 text-xs shadow-sm">
            <span
              className={`w-2 h-2 rounded-full ${
                healthStatus === 'healthy'
                  ? 'bg-emerald-500 animate-pulse'
                  : healthStatus === 'checking'
                  ? 'bg-amber-400'
                  : 'bg-red-500'
              }`}
            />
            <Server className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-600 font-medium">
              {healthStatus === 'healthy'
                ? `API ${backendMeta?.version ? `v${backendMeta.version}` : 'Online'} • PostgreSQL & Redis Connected`
                : healthStatus === 'checking'
                ? 'Connecting to VoiceLedger API...'
                : 'Backend API Unreachable'}
            </span>
          </div>
        </div>
      </div>

      {/* Main Login Card */}
      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md px-4 sm:px-0">
        <div className="bg-white py-8 px-6 shadow-sm border border-slate-200 rounded-2xl sm:px-10">
          <div className="mb-6 flex items-center justify-between border-b border-slate-100 pb-4">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Merchant Portal Access</h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Sign in to monitor live payments & soundboxes.
              </p>
            </div>
            <Link
              to="/register"
              className="text-xs font-semibold text-blue-600 hover:text-blue-700 hover:underline shrink-0"
            >
              Register →
            </Link>
          </div>

          {/* Quick-Fill Demo Helper */}
          <div className="mb-6 p-3 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs text-slate-600">
              <Sparkles className="w-4 h-4 text-blue-600" />
              <span>Demo Quick-Fill</span>
            </div>
            <button
              type="button"
              onClick={handleQuickFill}
              className="text-xs font-medium px-2.5 py-1 rounded-lg bg-white border border-slate-200 text-slate-700 hover:bg-slate-100 hover:text-blue-600 transition-colors shadow-2xs"
            >
              Autofill Credentials
            </button>
          </div>

          {error && (
            <div className="mb-5 p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-start gap-2">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-xs font-medium text-slate-700">
                Merchant Email
              </label>
              <div className="mt-1 relative rounded-lg">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <Mail className="w-4 h-4" />
                </div>
                <input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="merchant@voiceledger.internal"
                  className="block w-full pl-9 pr-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent bg-white text-slate-900 placeholder:text-slate-400"
                />
              </div>
            </div>

            <div>
              <label htmlFor="password" className="block text-xs font-medium text-slate-700">
                Password
              </label>
              <div className="mt-1 relative rounded-lg">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  id="password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="block w-full pl-9 pr-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent bg-white text-slate-900 placeholder:text-slate-400"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-2.5 px-4 border border-transparent rounded-lg shadow-sm text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              {loading ? (
                <>
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Authenticating...</span>
                </>
              ) : (
                <>
                  <span>Sign In to Dashboard</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          {/* Registration Link */}
          <div className="mt-4 text-center">
            <span className="text-xs text-slate-500">Need a new merchant account? </span>
            <Link to="/register" className="text-xs font-semibold text-blue-600 hover:underline">
              Create Account
            </Link>
          </div>

          {/* Security & Verification Callout */}
          <div className="mt-6 pt-5 border-t border-slate-100 text-xs text-slate-500 flex items-center justify-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>Argon2id Hashing • JWT Token Rotation • Tenant Isolated</span>
          </div>
        </div>

        {/* Footer Technical Note */}
        <div className="mt-6 text-center text-xs text-slate-400">
          VoiceLedger Buildathon Platform — Zero Financial Mutation Invariant
        </div>
      </div>
    </div>
  );
};
