import React, { useState, useEffect, useCallback } from 'react';
import {
  CreditCard,
  CheckCircle2,
  AlertCircle,
  Clock,
  RotateCcw,
  Search,
  Filter,
  Copy,
  Check,
  ShieldCheck,
  Radio,
  X,
  FileText
} from 'lucide-react';
import { listPaymentsApi, PaymentRecord, PaymentsListResponse } from '../api/payments';
import { useMerchantEvents } from '../hooks/useMerchantEvents';
import { useAuth } from '../hooks/useAuth';

export const PaymentsPage: React.FC = () => {
  const { merchant } = useAuth();
  const { status: wsStatus, latestPayment } = useMerchantEvents();

  const [data, setData] = useState<PaymentsListResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [selectedPayment, setSelectedPayment] = useState<PaymentRecord | null>(null);

  const fetchPayments = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listPaymentsApi({
        limit: 100,
        status: statusFilter !== 'ALL' ? statusFilter : undefined,
      });
      setData(res);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch payments ledger');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchPayments();
  }, [fetchPayments]);

  // When a new WebSocket payment event arrives, re-fetch or prepend
  useEffect(() => {
    if (latestPayment) {
      fetchPayments();
    }
  }, [latestPayment, fetchPayments]);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(text);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const filteredItems = (data?.items || []).filter((p) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      p.provider_payment_id.toLowerCase().includes(q) ||
      (p.provider_order_id && p.provider_order_id.toLowerCase().includes(q)) ||
      (p.payer_reference && p.payer_reference.toLowerCase().includes(q)) ||
      (p.payment_method && p.payment_method.toLowerCase().includes(q))
    );
  });

  const getStatusBadge = (status: PaymentRecord['status']) => {
    switch (status) {
      case 'CAPTURED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            Captured
          </span>
        );
      case 'AUTHORIZED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
            <Clock className="w-3.5 h-3.5 text-blue-600" />
            Authorized
          </span>
        );
      case 'FAILED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-red-50 text-red-700 border border-red-200">
            <AlertCircle className="w-3.5 h-3.5 text-red-600" />
            Failed
          </span>
        );
      case 'REFUNDED':
      case 'PARTIALLY_REFUNDED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            <RotateCcw className="w-3.5 h-3.5 text-amber-600" />
            {status === 'PARTIALLY_REFUNDED' ? 'Partial Refund' : 'Refunded'}
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-700">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded-full text-2xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
              Canonical Ingestion
            </span>
            <span className="inline-flex items-center gap-1.5 text-2xs font-semibold text-slate-600">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
              HMAC Authenticated
            </span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900 mt-1.5">Payments Ledger</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Immutable payment audit log synchronized with provider webhooks and the canonical Outbox Event Bus.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-50 border border-slate-200 text-xs">
            <Radio
              className={`w-3.5 h-3.5 ${
                wsStatus === 'CONNECTED' ? 'text-emerald-500 animate-pulse' : 'text-slate-400'
              }`}
            />
            <span className="text-slate-600 font-medium">WebSocket:</span>
            <span
              className={`font-semibold ${
                wsStatus === 'CONNECTED' ? 'text-emerald-700' : 'text-slate-500'
              }`}
            >
              {wsStatus}
            </span>
          </div>

          <button
            onClick={() => fetchPayments()}
            disabled={loading}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors disabled:opacity-50"
          >
            <RotateCcw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Total Captured Volume
          </span>
          <div className="text-2xl font-extrabold text-slate-900 mt-1">
            ₹{(data?.total_captured || 0).toLocaleString('en-IN', {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
          </div>
          <span className="text-2xs text-slate-400 mt-1 block">
            {merchant?.currency || 'INR'} • Integer minor units in DB
          </span>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Captured Transactions
          </span>
          <div className="text-2xl font-extrabold text-emerald-600 mt-1">
            {data?.captured_count ?? 0}
          </div>
          <span className="text-2xs text-slate-400 mt-1 block">
            Verified successful payments
          </span>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Total Recorded Events
          </span>
          <div className="text-2xl font-extrabold text-slate-900 mt-1">
            {data?.total_count ?? 0}
          </div>
          <span className="text-2xs text-slate-400 mt-1 block">
            Includes authorizations, captures & refunds
          </span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search by Payment ID, Order ID, Payer..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-sm rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <Filter className="w-4 h-4 text-slate-400" />
          <span className="text-xs font-medium text-slate-600">Status:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-1.5 text-xs font-semibold rounded-lg border border-slate-200 bg-slate-50 text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="ALL">All Statuses</option>
            <option value="CAPTURED">Captured</option>
            <option value="AUTHORIZED">Authorized</option>
            <option value="FAILED">Failed</option>
            <option value="REFUNDED">Refunded</option>
          </select>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Payment Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-600">
            <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase tracking-wider">
              <tr>
                <th className="px-6 py-3.5">Payment ID</th>
                <th className="px-6 py-3.5">Amount</th>
                <th className="px-6 py-3.5">Status</th>
                <th className="px-6 py-3.5">Method</th>
                <th className="px-6 py-3.5">Order / Payer</th>
                <th className="px-6 py-3.5">Captured At</th>
                <th className="px-6 py-3.5 text-right">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading && filteredItems.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-slate-400">
                    <RotateCcw className="w-6 h-6 animate-spin mx-auto mb-2 text-blue-500" />
                    Loading payments ledger...
                  </td>
                </tr>
              ) : filteredItems.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-slate-400">
                    <CreditCard className="w-8 h-8 mx-auto mb-2 text-slate-300" />
                    No payments found matching criteria.
                  </td>
                </tr>
              ) : (
                filteredItems.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="px-6 py-4 font-mono text-xs">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-slate-900">{p.provider_payment_id}</span>
                        <button
                          onClick={() => copyToClipboard(p.provider_payment_id)}
                          className="text-slate-400 hover:text-slate-600 p-1 rounded"
                          title="Copy Payment ID"
                        >
                          {copiedId === p.provider_payment_id ? (
                            <Check className="w-3.5 h-3.5 text-emerald-600" />
                          ) : (
                            <Copy className="w-3.5 h-3.5" />
                          )}
                        </button>
                      </div>
                      <span className="text-3xs text-slate-400 block mt-0.5 font-sans">
                        Provider: {p.provider}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className="font-bold text-slate-900 text-sm">
                        ₹{p.amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </span>
                      <span className="text-3xs text-slate-400 block font-mono">
                        {p.amount_minor} {p.currency}
                      </span>
                    </td>
                    <td className="px-6 py-4">{getStatusBadge(p.status)}</td>
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700">
                        {p.payment_method ? p.payment_method.toUpperCase() : 'UPI'}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-xs">
                      {p.provider_order_id ? (
                        <div className="font-mono text-slate-700 truncate max-w-[140px]" title={p.provider_order_id}>
                          {p.provider_order_id}
                        </div>
                      ) : (
                        <span className="text-slate-400 italic">Direct Pay</span>
                      )}
                      {p.payer_reference && (
                        <span className="text-3xs text-slate-400 block truncate max-w-[140px]">
                          {p.payer_reference}
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-xs text-slate-500 whitespace-nowrap">
                      {p.captured_at
                        ? new Date(p.captured_at).toLocaleString()
                        : new Date(p.created_at).toLocaleString()}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => setSelectedPayment(p)}
                        className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-semibold rounded-lg text-blue-600 hover:bg-blue-50 transition-colors"
                      >
                        <FileText className="w-3.5 h-3.5" />
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Payment Detail Modal */}
      {selectedPayment && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100">
              <div>
                <h3 className="text-lg font-bold text-slate-900">Payment Audit Record</h3>
                <p className="text-xs text-slate-500 font-mono mt-0.5">UUID: {selectedPayment.id}</p>
              </div>
              <button
                onClick={() => setSelectedPayment(null)}
                className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="py-4 space-y-3 text-sm">
              <div className="flex justify-between py-1.5 border-b border-slate-50">
                <span className="text-slate-500">Provider Payment ID</span>
                <span className="font-mono font-semibold text-slate-900">
                  {selectedPayment.provider_payment_id}
                </span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-50">
                <span className="text-slate-500">Provider Order ID</span>
                <span className="font-mono text-slate-800">
                  {selectedPayment.provider_order_id || 'N/A'}
                </span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-50">
                <span className="text-slate-500">Amount</span>
                <span className="font-bold text-emerald-600">
                  ₹{selectedPayment.amount.toFixed(2)} ({selectedPayment.amount_minor} minor units)
                </span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-50">
                <span className="text-slate-500">Status</span>
                <span>{getStatusBadge(selectedPayment.status)}</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-50">
                <span className="text-slate-500">Payment Method</span>
                <span className="font-semibold text-slate-800">
                  {selectedPayment.payment_method || 'UPI'}
                </span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-50">
                <span className="text-slate-500">Payer Reference</span>
                <span className="text-slate-800">{selectedPayment.payer_reference || 'N/A'}</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-50">
                <span className="text-slate-500">Captured At</span>
                <span className="text-slate-800">
                  {selectedPayment.captured_at
                    ? new Date(selectedPayment.captured_at).toISOString()
                    : 'Not captured'}
                </span>
              </div>
              <div className="flex justify-between py-1.5">
                <span className="text-slate-500">Created At</span>
                <span className="text-slate-800">
                  {new Date(selectedPayment.created_at).toISOString()}
                </span>
              </div>
            </div>

            <div className="pt-4 border-t border-slate-100 flex justify-end">
              <button
                onClick={() => setSelectedPayment(null)}
                className="px-4 py-2 text-sm font-semibold rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
