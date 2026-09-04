import React, { useState, useEffect, useCallback } from 'react';
import {
  Plus,
  Search,
  Download,
  TrendingUp,
  RefreshCw,
  Receipt,
  ExternalLink,
  CheckCircle2,
} from 'lucide-react';
import {
  Sale,
  SalesAnalytics,
  Product,
  listSalesApi,
  createSaleApi,
  getSalesAnalyticsApi,
  getExcelExportUrl,
  listProductsApi,
} from '../api/store';

export const SalesPage: React.FC = () => {
  const [sales, setSales] = useState<Sale[]>([]);
  const [analytics, setAnalytics] = useState<SalesAnalytics | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [period, setPeriod] = useState<'today' | 'week' | 'month' | 'all_time'>('month');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Create Sale Modal
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [custName, setCustName] = useState<string>('');
  const [custPhone, setCustPhone] = useState<string>('');
  const [autoPayLink, setAutoPayLink] = useState<boolean>(true);
  const [items, setItems] = useState<
    { product_name: string; quantity: number; unit_price: number; product_id?: string }[]
  >([{ product_name: '', quantity: 1, unit_price: 50 }]);
  const [creating, setCreating] = useState<boolean>(false);
  const [modalError, setModalError] = useState<string>('');
  const [createdSale, setCreatedSale] = useState<Sale | null>(null);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [salesData, analyticsData, prodsData] = await Promise.all([
        listSalesApi(100, statusFilter !== 'ALL' ? statusFilter : undefined),
        getSalesAnalyticsApi(),
        listProductsApi({ active_only: true }),
      ]);
      setSales(salesData);
      setAnalytics(analyticsData);
      setProducts(prodsData);
    } catch (err: any) {
      console.warn('Load error:', err);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const currentStats = analytics?.periods?.[period] || {
    orders_count: 0,
    total_gmv: 0,
    total_collected: 0,
    total_outstanding: 0,
    paid_orders_count: 0,
    pending_orders_count: 0,
    partial_orders_count: 0,
    collection_rate: 100,
    top_products: [],
  };

  const filteredSales = sales.filter((s) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    const custMatch = (s.customer_name || '').toLowerCase().includes(q);
    const idMatch = s.id.toLowerCase().includes(q);
    const itemMatch = s.items.some((it) => it.product_name.toLowerCase().includes(q));
    return custMatch || idMatch || itemMatch;
  });

  const handleAddItemRow = () => {
    setItems([...items, { product_name: '', quantity: 1, unit_price: 50 }]);
  };

  const handleRemoveItemRow = (idx: number) => {
    if (items.length > 1) {
      setItems(items.filter((_, i) => i !== idx));
    }
  };

  const handleProductSelect = (idx: number, prodId: string) => {
    const p = products.find((prod) => prod.id === prodId);
    if (p) {
      const updated = [...items];
      updated[idx] = {
        product_name: p.name,
        quantity: updated[idx].quantity || 1,
        unit_price: p.price,
        product_id: p.id,
      };
      setItems(updated);
    }
  };

  const calculateTotal = () => {
    return items.reduce((acc, it) => acc + (it.quantity || 1) * (it.unit_price || 0), 0);
  };

  const handleCreateSaleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const validItems = items.filter((it) => it.product_name.trim().length > 0);
    if (validItems.length === 0) {
      setModalError('Please add at least one line item with a name.');
      return;
    }

    setCreating(true);
    setModalError('');

    try {
      const newSale = await createSaleApi({
        customer_name: custName.trim() || undefined,
        customer_phone: custPhone.trim() || undefined,
        auto_create_payment_link: autoPayLink,
        items: validItems.map((it) => ({
          product_name: it.product_name.trim(),
          quantity: it.quantity || 1,
          unit_price: it.unit_price,
          product_id: it.product_id,
        })),
      });

      setCreatedSale(newSale);
      await loadData();
    } catch (err: any) {
      setModalError(err.message || 'Failed to create sale');
    } finally {
      setCreating(false);
    }
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setCreatedSale(null);
    setCustName('');
    setCustPhone('');
    setItems([{ product_name: '', quantity: 1, unit_price: 50 }]);
    setModalError('');
  };

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200 shadow-2xs">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">Sales & Orders Ledger</h1>
            <span className="text-2xs font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
              Financial Sync Active
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Real-time merchant transaction ledger with period analytics and multi-sheet spreadsheet exports.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <a
            href={getExcelExportUrl()}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 transition"
          >
            <Download className="w-4 h-4 text-slate-600" />
            Excel Report (.xlsx)
          </a>

          <button
            type="button"
            onClick={() => {
              setCreatedSale(null);
              setIsModalOpen(true);
            }}
            className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-xl bg-blue-600 text-white hover:bg-blue-700 transition shadow-xs"
          >
            <Plus className="w-4 h-4" />
            New Order / Sale
          </button>
        </div>
      </div>

      {/* Analytics Summary Cards */}
      <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-2xs space-y-4">
        <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-3">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-blue-600" />
            <h2 className="text-sm font-bold text-slate-900">Period Performance</h2>
          </div>

          <div className="inline-flex bg-slate-100 p-1 rounded-xl gap-1 text-2xs font-semibold">
            {(['today', 'week', 'month', 'all_time'] as const).map((pKey) => (
              <button
                key={pKey}
                type="button"
                onClick={() => setPeriod(pKey)}
                className={`px-3 py-1 rounded-lg transition capitalize ${
                  period === pKey ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {pKey === 'all_time' ? 'All-Time' : pKey}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-1">
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80">
            <span className="text-2xs font-semibold text-slate-500 uppercase tracking-wider block mb-1">
              Gross Sales (GMV)
            </span>
            <span className="text-lg font-bold text-slate-900">₹{currentStats.total_gmv.toFixed(2)}</span>
            <span className="block text-2xs text-slate-400 mt-0.5">{currentStats.orders_count} orders total</span>
          </div>

          <div className="p-4 rounded-xl bg-emerald-50/50 border border-emerald-200/80">
            <span className="text-2xs font-semibold text-emerald-700 uppercase tracking-wider block mb-1">
              Settled Collections
            </span>
            <span className="text-lg font-bold text-emerald-800">₹{currentStats.total_collected.toFixed(2)}</span>
            <span className="block text-2xs text-emerald-600 mt-0.5">{currentStats.paid_orders_count} orders paid</span>
          </div>

          <div className="p-4 rounded-xl bg-amber-50/50 border border-amber-200/80">
            <span className="text-2xs font-semibold text-amber-700 uppercase tracking-wider block mb-1">
              Outstanding Receivables
            </span>
            <span className="text-lg font-bold text-amber-800">₹{currentStats.total_outstanding.toFixed(2)}</span>
            <span className="block text-2xs text-amber-600 mt-0.5">{currentStats.pending_orders_count} pending / partial</span>
          </div>

          <div className="p-4 rounded-xl bg-blue-50/50 border border-blue-200/80">
            <span className="text-2xs font-semibold text-blue-700 uppercase tracking-wider block mb-1">
              Collection Rate
            </span>
            <span className="text-lg font-bold text-blue-800">{currentStats.collection_rate}%</span>
            <span className="block text-2xs text-blue-600 mt-0.5">Automated settlement</span>
          </div>
        </div>
      </div>

      {/* Filter and Search */}
      <div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by customer, order ID, or product..."
            className="w-full pl-9 pr-3 py-2 bg-white border border-slate-200 rounded-xl text-xs text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div className="flex items-center gap-1.5 w-full sm:w-auto">
          {['ALL', 'PAID', 'PENDING', 'PARTIAL'].map((status) => (
            <button
              key={status}
              type="button"
              onClick={() => setStatusFilter(status)}
              className={`px-3 py-1.5 rounded-lg text-2xs font-semibold transition ${
                statusFilter === status
                  ? 'bg-slate-900 text-white'
                  : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
              }`}
            >
              {status}
            </button>
          ))}
        </div>
      </div>

      {/* Transactions Table */}
      <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-2xs">
        {loading ? (
          <div className="py-16 text-center text-slate-400 text-xs flex items-center justify-center gap-2">
            <RefreshCw className="w-4 h-4 animate-spin text-blue-500" />
            Loading sales transactions...
          </div>
        ) : filteredSales.length === 0 ? (
          <div className="py-16 text-center text-slate-500 text-xs">
            <Receipt className="w-8 h-8 text-slate-300 mx-auto mb-2" />
            No sales recorded yet. Click &ldquo;New Order / Sale&rdquo; or use Voice Talkback to record transactions.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold">
                <tr>
                  <th className="py-3 px-4">Order ID</th>
                  <th className="py-3 px-4">Date</th>
                  <th className="py-3 px-4">Customer</th>
                  <th className="py-3 px-4">Line Items</th>
                  <th className="py-3 px-4">Total</th>
                  <th className="py-3 px-4">Settled</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Payment Link</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {filteredSales.map((sale) => (
                  <tr key={sale.id} className="hover:bg-slate-50/70 transition">
                    <td className="py-3 px-4 font-mono font-bold text-blue-700">{sale.id}</td>
                    <td className="py-3 px-4 text-slate-500 whitespace-nowrap">
                      {new Date(sale.created_at).toLocaleDateString(undefined, {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </td>
                    <td className="py-3 px-4 font-medium text-slate-900">
                      {sale.customer_name || 'Walk-in'}
                      {sale.customer_phone && (
                        <span className="block text-2xs text-slate-400">{sale.customer_phone}</span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <div className="max-w-xs truncate text-slate-600">
                        {sale.items.map((it) => `${it.quantity}x ${it.product_name}`).join(', ') || 'Item'}
                      </div>
                    </td>
                    <td className="py-3 px-4 font-bold text-slate-900">₹{sale.total_amount.toFixed(2)}</td>
                    <td className="py-3 px-4 text-slate-600 font-medium">₹{sale.received_amount.toFixed(2)}</td>
                    <td className="py-3 px-4">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-2xs font-semibold ${
                          sale.status === 'PAID'
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : sale.status === 'PARTIAL'
                            ? 'bg-amber-50 text-amber-700 border border-amber-200'
                            : 'bg-slate-100 text-slate-700 border border-slate-200'
                        }`}
                      >
                        {sale.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      {sale.razorpay_payment_link_url ? (
                        <a
                          href={sale.razorpay_payment_link_url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-2xs font-semibold text-blue-600 hover:text-blue-800 bg-blue-50 px-2.5 py-1 rounded-lg border border-blue-200"
                        >
                          Pay Link
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      ) : (
                        <span className="text-slate-400 text-2xs">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* CREATE NEW SALE MODAL */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
          <div className="bg-white w-full max-w-lg rounded-2xl shadow-xl border border-slate-200 overflow-hidden flex flex-col max-h-[90vh]">
            <div className="p-4 border-b border-slate-200 flex items-center justify-between">
              <h2 className="text-sm font-bold text-slate-900">Record New Sale / Order</h2>
              <button
                type="button"
                onClick={handleCloseModal}
                className="text-slate-400 hover:text-slate-600 text-xs font-bold"
              >
                ✕
              </button>
            </div>

            {createdSale ? (
              <div className="p-6 text-center space-y-4 text-xs">
                <div className="w-12 h-12 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto">
                  <CheckCircle2 className="w-6 h-6" />
                </div>
                <h3 className="text-base font-bold text-slate-900">Order Created Successfully!</h3>
                <p className="text-slate-600">
                  Order <span className="font-mono font-bold text-blue-600">{createdSale.id}</span> for{' '}
                  <span className="font-bold">₹{createdSale.total_amount.toFixed(2)}</span> has been recorded in the ledger.
                </p>

                {createdSale.razorpay_payment_link_url && (
                  <div className="p-3.5 bg-blue-50 border border-blue-200 rounded-xl space-y-2 text-left">
                    <span className="text-2xs font-bold text-blue-800 block uppercase">
                      Razorpay Payment Link Ready:
                    </span>
                    <a
                      href={createdSale.razorpay_payment_link_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-blue-700 font-mono text-xs break-all underline block"
                    >
                      {createdSale.razorpay_payment_link_url}
                    </a>
                  </div>
                )}

                <button
                  type="button"
                  onClick={handleCloseModal}
                  className="w-full py-2 bg-slate-900 text-white rounded-xl font-semibold hover:bg-slate-800 transition"
                >
                  Done
                </button>
              </div>
            ) : (
              <form onSubmit={handleCreateSaleSubmit} className="p-5 overflow-y-auto space-y-4 text-xs">
                {modalError && (
                  <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 font-semibold">
                    {modalError}
                  </div>
                )}

                {/* Customer Details */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block font-bold text-slate-700 mb-1">Customer Name (Optional)</label>
                    <input
                      type="text"
                      value={custName}
                      onChange={(e) => setCustName(e.target.value)}
                      placeholder="e.g. Rahul Verma"
                      className="w-full px-3 py-2 border border-slate-200 rounded-xl text-slate-900 focus:outline-hidden focus:ring-2 focus:ring-blue-500"
                    />
                  </div>

                  <div>
                    <label className="block font-bold text-slate-700 mb-1">Phone Number (Optional)</label>
                    <input
                      type="text"
                      value={custPhone}
                      onChange={(e) => setCustPhone(e.target.value)}
                      placeholder="+91..."
                      className="w-full px-3 py-2 border border-slate-200 rounded-xl text-slate-900 focus:outline-hidden focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                </div>

                {/* Line Items */}
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <label className="font-bold text-slate-700">Line Items *</label>
                    <button
                      type="button"
                      onClick={handleAddItemRow}
                      className="text-2xs font-bold text-blue-600 hover:text-blue-700"
                    >
                      + Add Item
                    </button>
                  </div>

                  {items.map((it, idx) => (
                    <div key={idx} className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
                      <div className="flex gap-2">
                        {products.length > 0 ? (
                          <select
                            onChange={(e) => handleProductSelect(idx, e.target.value)}
                            className="w-1/2 px-2.5 py-1.5 border border-slate-200 rounded-lg text-2xs bg-white"
                          >
                            <option value="">-- Select from Catalog --</option>
                            {products.map((p) => (
                              <option key={p.id} value={p.id}>
                                {p.name} (₹{p.price})
                              </option>
                            ))}
                          </select>
                        ) : null}

                        <input
                          type="text"
                          required
                          placeholder="Or type item name..."
                          value={it.product_name}
                          onChange={(e) => {
                            const updated = [...items];
                            updated[idx].product_name = e.target.value;
                            setItems(updated);
                          }}
                          className="flex-1 px-2.5 py-1.5 border border-slate-200 rounded-lg text-2xs bg-white"
                        />
                      </div>

                      <div className="flex items-center gap-2">
                        <div className="flex items-center gap-1">
                          <span className="text-slate-500 text-2xs">Qty:</span>
                          <input
                            type="number"
                            min="1"
                            value={it.quantity}
                            onChange={(e) => {
                              const updated = [...items];
                              updated[idx].quantity = parseInt(e.target.value, 10) || 1;
                              setItems(updated);
                            }}
                            className="w-16 px-2 py-1 border border-slate-200 rounded-lg text-2xs bg-white text-center"
                          />
                        </div>

                        <div className="flex items-center gap-1">
                          <span className="text-slate-500 text-2xs">Price (₹):</span>
                          <input
                            type="number"
                            min="0"
                            step="0.01"
                            value={it.unit_price}
                            onChange={(e) => {
                              const updated = [...items];
                              updated[idx].unit_price = parseFloat(e.target.value) || 0;
                              setItems(updated);
                            }}
                            className="w-20 px-2 py-1 border border-slate-200 rounded-lg text-2xs bg-white"
                          />
                        </div>

                        <div className="flex-1 text-right font-bold text-slate-800 text-2xs">
                          Subtotal: ₹{(it.quantity * it.unit_price).toFixed(2)}
                        </div>

                        {items.length > 1 && (
                          <button
                            type="button"
                            onClick={() => handleRemoveItemRow(idx)}
                            className="text-slate-400 hover:text-rose-600 text-xs px-1"
                          >
                            ✕
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="flex items-center justify-between p-3 rounded-xl bg-blue-50 border border-blue-200">
                  <span className="font-bold text-blue-900">Total Amount:</span>
                  <span className="text-base font-extrabold text-blue-900">
                    ₹{calculateTotal().toFixed(2)}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="autoPayLinkCheck"
                    checked={autoPayLink}
                    onChange={(e) => setAutoPayLink(e.target.checked)}
                    className="rounded text-blue-600 focus:ring-blue-500 w-4 h-4"
                  />
                  <label htmlFor="autoPayLinkCheck" className="text-slate-700 font-medium">
                    Automatically create Razorpay Payment Link
                  </label>
                </div>

                <div className="pt-3 border-t border-slate-100 flex items-center justify-end gap-2">
                  <button
                    type="button"
                    onClick={handleCloseModal}
                    className="px-4 py-2 border border-slate-200 text-slate-700 font-semibold rounded-xl hover:bg-slate-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={creating}
                    className="px-4 py-2 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 disabled:opacity-50"
                  >
                    {creating ? 'Recording...' : 'Record Sale'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
