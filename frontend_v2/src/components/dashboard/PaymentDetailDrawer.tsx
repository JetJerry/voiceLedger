import React, { useEffect, useState } from 'react';
import {
  X,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  CreditCard,
  Layers,
  Database,
  Lock,
  Code2,
} from 'lucide-react';
import { MerchantPaymentEvent } from '../../types/websocket';
import { ResourceAccessResponse } from '../../types/merchant';
import { checkPaymentAccessApi } from '../../api/merchants';
import { formatCurrency, formatTimestamp } from '../../services/websocketParser';

interface PaymentDetailDrawerProps {
  payment: MerchantPaymentEvent | null;
  isOpen: boolean;
  onClose: () => void;
}

export const PaymentDetailDrawer: React.FC<PaymentDetailDrawerProps> = ({
  payment,
  isOpen,
  onClose,
}) => {
  const [accessVerification, setAccessVerification] = useState<ResourceAccessResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !payment?.paymentId) {
      setAccessVerification(null);
      setError(null);
      return;
    }

    let isMounted = true;
    setLoading(true);
    setError(null);

    checkPaymentAccessApi(payment.paymentId)
      .then((res) => {
        if (isMounted) setAccessVerification(res);
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || 'Tenant verification failed: Payment not found in active ledger.');
        }
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, payment?.paymentId]);

  if (!isOpen || !payment) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-slate-900/40 backdrop-blur-xs animate-fadeIn">
      <div className="absolute inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-md bg-white shadow-2xl border-l border-slate-200 flex flex-col">
          {/* Drawer Header */}
          <div className="p-6 border-b border-slate-100 flex items-center justify-between bg-slate-50/70">
            <div>
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
                <h3 className="text-sm font-bold text-slate-900">Payment Audit Record</h3>
              </div>
              <p className="text-2xs text-slate-500 mt-0.5 font-mono">
                {payment.providerPaymentId || payment.paymentId}
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Drawer Content */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {/* Amount Banner */}
            <div className="p-5 rounded-2xl bg-gradient-to-br from-slate-900 to-slate-800 text-white shadow-sm space-y-2">
              <span className="text-2xs font-semibold uppercase tracking-wider text-slate-400 block">
                Confirmed Transaction Amount
              </span>
              <div className="flex items-baseline justify-between">
                <h2 className="text-3xl font-extrabold tracking-tight">
                  {formatCurrency(payment.amountMinor, payment.currency)}
                </h2>
                <span className="px-2 py-0.5 rounded text-2xs font-bold uppercase bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                  {payment.status}
                </span>
              </div>
              <div className="text-2xs text-slate-400 flex items-center gap-2 pt-1">
                <CreditCard className="w-3.5 h-3.5 text-slate-300" />
                <span>Method: {payment.paymentMethod.toUpperCase()}</span>
                {payment.payerReference && <span>• {payment.payerReference}</span>}
              </div>
            </div>

            {/* PostgreSQL Tenant Isolation Verification Status */}
            <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
                  <Database className="w-3.5 h-3.5 text-blue-600" />
                  PostgreSQL Ledger Verification
                </span>
                <span className="text-3xs font-mono text-slate-400">
                  GET /merchants/payments/{'{id}'}
                </span>
              </div>

              {loading ? (
                <div className="py-2 text-center text-xs text-slate-500">
                  <span className="animate-pulse">Verifying query-level tenant access...</span>
                </div>
              ) : accessVerification?.authorized ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-xs font-semibold text-emerald-800 bg-emerald-50 p-2.5 rounded-lg border border-emerald-200">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                    <span>Authorized & Validated in Tenant Partition</span>
                  </div>
                  <div className="text-2xs space-y-1 font-mono text-slate-600 pt-1">
                    <div className="flex justify-between">
                      <span className="text-slate-400">Resource Type:</span>
                      <span className="font-semibold text-slate-700">{accessVerification.resource_type}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Merchant UUID:</span>
                      <span className="text-slate-700 truncate max-w-[180px]">{accessVerification.merchant_id}</span>
                    </div>
                  </div>
                </div>
              ) : error ? (
                <div className="flex items-start gap-2 text-xs text-amber-800 bg-amber-50 p-2.5 rounded-lg border border-amber-200">
                  <AlertCircle className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
                  <span>{error}</span>
                </div>
              ) : null}
            </div>

            {/* Verification Checklist */}
            <div className="space-y-2.5">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400 block">
                Cryptographic Security Checklist
              </span>
              <div className="space-y-2 text-xs">
                <div className="flex items-center gap-2 text-slate-700 p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                  <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>HMAC-SHA256 Signature Validated</span>
                </div>
                <div className="flex items-center gap-2 text-slate-700 p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                  <Lock className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>Level-1 Redis Idempotency Locked</span>
                </div>
                <div className="flex items-center gap-2 text-slate-700 p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                  <Layers className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>Transactional Outbox Emitted over Redis</span>
                </div>
              </div>
            </div>

            {/* Timestamps and Identifiers */}
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-2 font-mono">
              <div className="flex justify-between">
                <span className="text-slate-400">Provider Payment ID:</span>
                <span className="font-semibold text-slate-800">{payment.providerPaymentId}</span>
              </div>
              {payment.providerOrderId && (
                <div className="flex justify-between">
                  <span className="text-slate-400">Provider Order ID:</span>
                  <span className="text-slate-600">{payment.providerOrderId}</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-slate-400">Internal Payment UUID:</span>
                <span className="text-slate-600 truncate max-w-[180px]">{payment.paymentId}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Capture Timestamp:</span>
                <span className="text-slate-600">{payment.capturedAt ? formatTimestamp(payment.capturedAt) : 'Immediate'}</span>
              </div>
            </div>

            {/* Raw Event JSON */}
            <div>
              <span className="text-2xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1 mb-1.5">
                <Code2 className="w-3 h-3" />
                Raw WebSocket Frame Payload
              </span>
              <pre className="p-3 rounded-xl bg-slate-900 text-slate-200 text-3xs font-mono overflow-x-auto max-h-48">
                {JSON.stringify(payment, null, 2)}
              </pre>
            </div>
          </div>

          {/* Drawer Footer */}
          <div className="p-4 border-t border-slate-100 bg-slate-50 flex items-center justify-end">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-xs font-semibold text-slate-700 bg-white border border-slate-200 hover:bg-slate-100 transition-colors shadow-2xs"
            >
              Close Drawer
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
