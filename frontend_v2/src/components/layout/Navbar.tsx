import React, { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { Volume2, Activity, Speaker, Cpu, LogOut, Store, Shield, User as UserIcon } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { UserProfileModal } from '../common/UserProfileModal';
import { HealthDiagnosticModal } from '../common/HealthDiagnosticModal';

export const Navbar: React.FC = () => {
  const { user, merchant, logout } = useAuth();
  const navigate = useNavigate();
  const [isProfileModalOpen, setIsProfileModalOpen] = useState<boolean>(false);
  const [isHealthModalOpen, setIsHealthModalOpen] = useState<boolean>(false);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const navItemClasses = ({ isActive }: { isActive: boolean }) =>
    `inline-flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
      isActive
        ? 'bg-blue-50 text-blue-700 font-semibold'
        : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
    }`;

  return (
    <header className="sticky top-0 z-30 bg-white border-b border-slate-200 shadow-2xs">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Left: Branding & Merchant Organization */}
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center text-white shadow-xs">
                <Volume2 className="w-5 h-5" />
              </div>
              <div>
                <span className="text-base font-bold tracking-tight text-slate-900 flex items-center gap-1.5">
                  VoiceLedger
                  <span className="text-2xs font-semibold px-1.5 py-0.5 rounded-sm bg-blue-50 text-blue-700 border border-blue-200">
                    v2.0
                  </span>
                </span>
                <span className="block text-2xs text-slate-500 font-medium leading-none">
                  Payment Voice Engine
                </span>
              </div>
            </div>

            {/* Active Merchant Context Badge */}
            {merchant && (
              <div className="hidden md:flex items-center gap-2 pl-4 border-l border-slate-200">
                <div className="w-7 h-7 rounded-lg bg-slate-100 flex items-center justify-center text-slate-600">
                  <Store className="w-4 h-4 text-blue-600" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-slate-900">{merchant.name}</span>
                    <span className="inline-flex items-center gap-1 text-2xs font-medium px-1.5 py-0.2 rounded bg-slate-100 text-slate-600 border border-slate-200">
                      <Shield className="w-2.5 h-2.5 text-blue-600" />
                      {merchant.user_role}
                    </span>
                  </div>
                  <span className="text-2xs text-slate-500 block">
                    {merchant.business_type || 'Retail'} • Currency: {merchant.currency}
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Center: Navigation Links */}
          <nav className="hidden sm:flex items-center gap-1">
            <NavLink to="/" end className={navItemClasses}>
              <Activity className="w-4 h-4 text-emerald-600" />
              <span>Live Operations</span>
            </NavLink>
            <NavLink to="/devices" className={navItemClasses}>
              <Speaker className="w-4 h-4 text-indigo-600" />
              <span>Soundboxes</span>
            </NavLink>
            <NavLink to="/architecture" className={navItemClasses}>
              <Cpu className="w-4 h-4 text-amber-600" />
              <span>System Architecture</span>
            </NavLink>
          </nav>

          {/* Right: System Health, User Profile & Logout */}
          <div className="flex items-center gap-3">
            {/* Live Health Probe Button */}
            <button
              type="button"
              onClick={() => setIsHealthModalOpen(true)}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 text-2xs font-semibold rounded-lg bg-emerald-50 text-emerald-800 border border-emerald-200 hover:bg-emerald-100 transition-colors shadow-2xs"
              title="Inspect Live System Health & Latency"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span className="hidden md:inline">API Online</span>
            </button>

            {/* Clickable User Profile Badge */}
            <button
              type="button"
              onClick={() => setIsProfileModalOpen(true)}
              className="flex items-center gap-2 hover:bg-slate-50 p-1.5 rounded-xl transition-colors text-right border border-transparent hover:border-slate-200"
              title="Click to view full user account profile (/api/v1/auth/me)"
            >
              <div className="w-7 h-7 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center font-bold text-xs shrink-0">
                <UserIcon className="w-3.5 h-3.5" />
              </div>
              <div className="hidden lg:flex flex-col text-left">
                <span className="text-xs font-semibold text-slate-800 truncate max-w-[140px]">
                  {user?.full_name || user?.email || 'Merchant User'}
                </span>
                <span className="text-3xs text-slate-400 font-mono truncate max-w-[140px]">
                  {user?.email}
                </span>
              </div>
            </button>

            <button
              onClick={handleLogout}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-600 hover:text-red-600 hover:bg-red-50 rounded-lg border border-slate-200 transition-colors"
              title="Sign out of VoiceLedger"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Sign Out</span>
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Sub-Navigation Bar */}
      <div className="sm:hidden border-t border-slate-100 px-3 py-1.5 flex items-center justify-around bg-slate-50">
        <NavLink
          to="/"
          end
          className={({ isActive }) =>
            `inline-flex items-center gap-1 px-2.5 py-1 text-2xs font-semibold rounded-md ${
              isActive ? 'bg-blue-100 text-blue-800' : 'text-slate-600'
            }`
          }
        >
          <Activity className="w-3 h-3 text-emerald-600" />
          <span>Live Ops</span>
        </NavLink>
        <NavLink
          to="/devices"
          className={({ isActive }) =>
            `inline-flex items-center gap-1 px-2.5 py-1 text-2xs font-semibold rounded-md ${
              isActive ? 'bg-blue-100 text-blue-800' : 'text-slate-600'
            }`
          }
        >
          <Speaker className="w-3 h-3 text-indigo-600" />
          <span>Soundboxes</span>
        </NavLink>
        <NavLink
          to="/architecture"
          className={({ isActive }) =>
            `inline-flex items-center gap-1 px-2.5 py-1 text-2xs font-semibold rounded-md ${
              isActive ? 'bg-blue-100 text-blue-800' : 'text-slate-600'
            }`
          }
        >
          <Cpu className="w-3 h-3 text-amber-600" />
          <span>Architecture</span>
        </NavLink>
      </div>

      {/* Modals */}
      <UserProfileModal
        isOpen={isProfileModalOpen}
        onClose={() => setIsProfileModalOpen(false)}
      />
      <HealthDiagnosticModal
        isOpen={isHealthModalOpen}
        onClose={() => setIsHealthModalOpen(false)}
      />
    </header>
  );
};
