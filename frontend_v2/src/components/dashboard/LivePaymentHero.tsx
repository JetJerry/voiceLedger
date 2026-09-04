import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CheckCircle2,
  CreditCard,
  Speaker,
  ShieldCheck,
  Zap,
  ArrowRight,
} from 'lucide-react';
import { MerchantPaymentEvent } from '../../types/websocket';
import { formatCurrency, formatTimestamp } from '../../services/websocketParser';

interface LivePaymentHeroProps {
  payment: MerchantPaymentEvent;
}

export const LivePaymentHero: React.FC<LivePaymentHeroProps> = ({ payment }) => {
  const navigate = useNavigate();
  const isCaptured = payment.status.toUpperCase() === 'CAPTURED';

  return (
    <div className="bg-white border-2 border-emerald-500/80 rounded-2xl p-6 shadow-sm relative overflow-hidden transition-all animate-fadeIn">
      {/* Visual Accent Top Bar */}
      <div className="absolute top-0 left-0 right-0 h-1.5 bg-gradient-to-r from-emerald-500 via-teal-500 to-blue-500" />

      {/* Header with Badges */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <Zap className="w-3.5 h-3.5 fill-emerald-600 text-emerald-600" />
            LIVE PAYMENT CAPTURED
          </span>
          <span className="text-xs font-mono text-slate-400">
            Event: {payment.eventType}
          </span>
        </div>

        <div className="text-xs text-slate-500 flex items-center gap-1.5">
          <span>Received at:</span>
          <span className="font-semibold text-slate-700 font-mono">
            {formatTimestamp(payment.receivedAt)}
          </span>
        </div>
      </div>

      {/* Main Hero Amount & Details Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 pt-6">
        {/* Left Column: Big Amount & Provider Data */}
        <div className="lg:col-span-7 flex flex-col justify-between space-y-4">
          <div>
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400 block mb-1">
              Confirmed Transaction Amount
            </span>
            <div className="flex items-baseline gap-3">
              <h2 className="text-4xl sm:text-5xl font-extrabold text-slate-900 tracking-tight">
                {formatCurrency(payment.amountMinor, payment.currency)}
              </h2>
              <span
                className={`inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-bold uppercase ${
                  isCaptured
                    ? 'bg-emerald-100 text-emerald-800'
                    : 'bg-amber-100 text-amber-800'
                }`}
              >
                {payment.status}
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-2 flex items-center gap-1.5">
              <CreditCard className="w-3.5 h-3.5 text-slate-400" />
              Method: <span className="font-semibold uppercase text-slate-700">{payment.paymentMethod}</span>
              {payment.payerReference && (
                <span className="text-slate-600 font-mono text-2xs">({payment.payerReference})</span>
              )}
            </p>
          </div>

          {/* Reference IDs Box */}
          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-1.5 font-mono">
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Provider Payment ID:</span>
              <span className="text-slate-800 font-semibold">{payment.providerPaymentId}</span>
            </div>
            {payment.providerOrderId && (
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Provider Order ID:</span>
                <span className="text-slate-600">{payment.providerOrderId}</span>
              </div>
            )}
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Internal Payment UUID:</span>
              <span className="text-slate-600 truncate max-w-[200px]" title={payment.paymentId}>
                {payment.paymentId}
              </span>
            </div>
          </div>
        </div>

        {/* Right Column: Cryptographic Verification & Delivery Story */}
        <div className="lg:col-span-5 flex flex-col justify-between bg-slate-50 rounded-xl p-4 border border-slate-200">
          <div>
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500 block mb-3 flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              Ledger Verification Pipeline
            </span>

            <ul className="space-y-2.5 text-xs">
              <li className="flex items-start gap-2 text-slate-700 font-medium">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 mt-0.5 shrink-0" />
                <span>HMAC-SHA256 Webhook Signature Verified</span>
              </li>
              <li className="flex items-start gap-2 text-slate-700 font-medium">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 mt-0.5 shrink-0" />
                <span>Recorded in PostgreSQL Financial Ledger</span>
              </li>
              <li className="flex items-start gap-2 text-slate-700 font-medium">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 mt-0.5 shrink-0" />
                <span>Transactional Outbox Published over Redis</span>
              </li>
              <li className="flex items-start gap-2 text-slate-700 font-medium">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 mt-0.5 shrink-0" />
                <span>Dispatched to Soundbox Hardware Bridge</span>
              </li>
            </ul>
          </div>

          {/* Soundbox Announcement Banner */}
          <div className="mt-4 pt-3 border-t border-slate-200 flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-semibold text-indigo-700">
              <Speaker className="w-4 h-4 animate-pulse text-indigo-600" />
              <span>Voice Announcement Dispatched</span>
            </div>
            <button
              type="button"
              onClick={() => navigate('/devices')}
              className="inline-flex items-center gap-1 text-2xs font-semibold px-2 py-1 rounded-lg bg-indigo-50 text-indigo-700 hover:bg-indigo-100 transition-colors border border-indigo-200"
            >
              <span>View Simulator</span>
              <ArrowRight className="w-3 h-3" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
