import React, { useEffect, useState } from 'react';
import {
  X,
  User as UserIcon,
  Mail,
  Shield,
  Clock,
  CheckCircle2,
  Copy,
  Check,
  Store,
  LogOut,
  Key,
  RefreshCw,
} from 'lucide-react';
import { getMeApi } from '../../api/auth';
import { useAuth } from '../../hooks/useAuth';
import { User } from '../../types/auth';

interface UserProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const UserProfileModal: React.FC<UserProfileModalProps> = ({ isOpen, onClose }) => {
  const { user: cachedUser, merchant, logout } = useAuth();
  const [profile, setProfile] = useState<User | null>(cachedUser);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<boolean>(false);

  useEffect(() => {
    if (!isOpen) return;

    let isMounted = true;
    setLoading(true);
    setError(null);

    getMeApi()
      .then((data) => {
        if (isMounted) setProfile(data);
      })
      .catch((err) => {
        if (isMounted) {
          console.error('Failed to fetch user profile:', err);
          setError('Could not refresh profile from server.');
        }
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(true);
    setTimeout(() => setCopiedId(false), 2000);
  };

  const handleSignOut = async () => {
    onClose();
    await logout();
  };

  const currentUser = profile || cachedUser;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-fadeIn">
      <div className="bg-white rounded-2xl max-w-lg w-full shadow-2xl border border-slate-200 overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/60">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center font-bold">
              <UserIcon className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-1.5">
                User Account Profile
                {loading && <RefreshCw className="w-3 h-3 text-blue-600 animate-spin" />}
              </h3>
              <p className="text-2xs text-slate-500">Verified via <code className="bg-slate-100 px-1 py-0.5 rounded text-3xs font-mono">GET /api/v1/auth/me</code></p>
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

        {/* Content Body */}
        <div className="p-6 space-y-5">
          {error && (
            <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs">
              {error}
            </div>
          )}

          {/* User Identity Card */}
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-900">
                {currentUser?.full_name || 'Merchant User'}
              </span>
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-2xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                Active Account
              </span>
            </div>

            <div className="space-y-1.5 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-slate-500 flex items-center gap-1.5">
                  <Mail className="w-3.5 h-3.5 text-slate-400" />
                  Email Address:
                </span>
                <span className="font-mono text-slate-800 font-medium">{currentUser?.email}</span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-slate-500 flex items-center gap-1.5">
                  <Key className="w-3.5 h-3.5 text-slate-400" />
                  User UUID:
                </span>
                <div className="flex items-center gap-1.5">
                  <span className="font-mono text-2xs text-slate-700">
                    {currentUser?.id ? `${currentUser.id.slice(0, 16)}...` : 'N/A'}
                  </span>
                  {currentUser?.id && (
                    <button
                      type="button"
                      onClick={() => handleCopy(currentUser.id)}
                      className="p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-200 transition-colors"
                      title="Copy full UUID"
                    >
                      {copiedId ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                    </button>
                  )}
                </div>
              </div>

              {currentUser?.created_at && (
                <div className="flex items-center justify-between">
                  <span className="text-slate-500 flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-slate-400" />
                    Member Since:
                  </span>
                  <span className="text-slate-700 text-2xs">
                    {new Date(currentUser.created_at).toLocaleDateString(undefined, {
                      year: 'numeric',
                      month: 'short',
                      day: 'numeric',
                    })}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Organization & Role Tenancy */}
          <div className="p-4 rounded-xl bg-blue-50/50 border border-blue-100 space-y-2.5">
            <span className="text-2xs font-bold uppercase tracking-wider text-blue-700 flex items-center gap-1.5">
              <Store className="w-3.5 h-3.5" />
              Active Merchant Organization
            </span>

            {merchant ? (
              <div className="space-y-1.5 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">Store Name:</span>
                  <span className="font-bold text-slate-800">{merchant.name}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">Authorized Role:</span>
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-white text-blue-700 border border-blue-200 font-bold text-2xs">
                    <Shield className="w-2.5 h-2.5 text-blue-600" />
                    {merchant.user_role}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">Merchant UUID:</span>
                  <span className="font-mono text-3xs text-slate-600 truncate max-w-[200px]">
                    {merchant.id}
                  </span>
                </div>
              </div>
            ) : (
              <p className="text-2xs text-slate-500 leading-relaxed">
                No active merchant organization attached. User is authenticated at the platform root.
              </p>
            )}
          </div>

          {/* Security Summary */}
          <div className="p-3 rounded-xl bg-slate-50 border border-slate-100 text-3xs text-slate-500 space-y-1">
            <span className="font-semibold text-slate-700 block">Security Invariants Upheld:</span>
            <p>• Argon2id password hashing with timing attack mitigation</p>
            <p>• Dual JWT rotation with client memory access token</p>
            <p>• Multi-tenant PostgreSQL query-level row authorization</p>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="px-6 py-3.5 border-t border-slate-100 bg-slate-50 flex items-center justify-between">
          <button
            type="button"
            onClick={handleSignOut}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-red-600 hover:bg-red-50 transition-colors border border-transparent hover:border-red-200"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Sign Out</span>
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
