import React from 'react';
import { CheckCircle2 } from 'lucide-react';
import { MerchantPaymentEvent } from '../../types/websocket';
import { formatCurrency, formatTimestamp } from '../../services/websocketParser';

interface PaymentFeedTableProps {
  payments: MerchantPaymentEvent[];
  onSelectPayment?: (payment: MerchantPaymentEvent) => void;
  selectedPaymentId?: string | null;
}

export const PaymentFeedTable: React.FC<PaymentFeedTableProps> = ({
  payments,
  onSelectPayment,
  selectedPaymentId,
}) => {
  if (payments.length === 0) {
    return null;
  }

  return (
    <div className="bg-white border border-slate-200 rounded-2xl shadow-xs overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <span>Session Payment History</span>
            <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
              {payments.length} {payments.length === 1 ? 'event' : 'events'}
            </span>
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Real-time payment transactions received during this session via WebSocket.
          </p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
          <thead className="bg-slate-50 text-slate-500 font-semibold uppercase tracking-wider">
            <tr>
              <th scope="col" className="px-6 py-3">Status</th>
              <th scope="col" className="px-6 py-3">Amount</th>
              <th scope="col" className="px-6 py-3">Payment ID</th>
              <th scope="col" className="px-6 py-3">Method / Payer</th>
              <th scope="col" className="px-6 py-3">Event Type</th>
              <th scope="col" className="px-6 py-3 text-right">Received At</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {payments.map((p) => {
              const isSelected = p.id === selectedPaymentId;
              const isCaptured = p.status.toUpperCase() === 'CAPTURED';

              return (
                <tr
                  key={p.id + p.receivedAt}
                  onClick={() => onSelectPayment?.(p)}
                  className={`hover:bg-slate-50 transition-colors cursor-pointer ${
                    isSelected ? 'bg-blue-50/50' : ''
                  }`}
                >
                  <td className="px-6 py-3.5 whitespace-nowrap">
                    <span
                      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-2xs font-bold uppercase ${
                        isCaptured
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : 'bg-amber-50 text-amber-700 border border-amber-200'
                      }`}
                    >
                      <CheckCircle2 className="w-3 h-3" />
                      {p.status}
                    </span>
                  </td>

                  <td className="px-6 py-3.5 whitespace-nowrap">
                    <span className="text-sm font-bold text-slate-900">
                      {formatCurrency(p.amountMinor, p.currency)}
                    </span>
                  </td>

                  <td className="px-6 py-3.5 whitespace-nowrap font-mono text-slate-700">
                    {p.providerPaymentId}
                  </td>

                  <td className="px-6 py-3.5 whitespace-nowrap">
                    <div className="flex flex-col">
                      <span className="font-semibold uppercase text-slate-700">{p.paymentMethod}</span>
                      <span className="text-2xs text-slate-400 font-mono">{p.payerReference}</span>
                    </div>
                  </td>

                  <td className="px-6 py-3.5 whitespace-nowrap font-mono text-slate-500 text-2xs">
                    {p.eventType}
                  </td>

                  <td className="px-6 py-3.5 whitespace-nowrap text-right font-mono text-slate-500 text-2xs">
                    {formatTimestamp(p.receivedAt)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
