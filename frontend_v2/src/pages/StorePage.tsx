import React, { useState, useEffect, useCallback } from 'react';
import {
  Package,
  Plus,
  Search,
  Edit2,
  Trash2,
  Boxes,
  Sparkles,
  RefreshCw,
  CheckCircle2,
} from 'lucide-react';
import {
  Product,
  listProductsApi,
  createProductApi,
  updateProductApi,
  deleteProductApi,
  adjustInventoryApi,
  getBusinessTypesApi,
  setBusinessTypeApi,
  BusinessTypesData,
} from '../api/store';
import { useAuth } from '../hooks/useAuth';

export const StorePage: React.FC = () => {
  const { merchant } = useAuth();

  const [activeTab, setActiveTab] = useState<'products' | 'inventory' | 'presets'>('products');
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');

  // Add / Edit Modal state
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [formName, setFormName] = useState<string>('');
  const [formPrice, setFormPrice] = useState<string>('');
  const [formCategory, setFormCategory] = useState<string>('General');
  const [formUnit, setFormUnit] = useState<string>('piece');
  const [formStock, setFormStock] = useState<string>('0');
  const [formTrackInventory, setFormTrackInventory] = useState<boolean>(false);
  const [formDescription, setFormDescription] = useState<string>('');
  const [formAttrs, setFormAttrs] = useState<{ key: string; value: string }[]>([]);
  const [saving, setSaving] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string>('');

  // Business Types
  const [businessData, setBusinessData] = useState<BusinessTypesData | null>(null);
  const [selectedType, setSelectedType] = useState<string>(merchant?.business_type || 'Kirana & Retail');
  const [settingType, setSettingType] = useState<boolean>(false);
  const [successMsg, setSuccessMsg] = useState<string>('');

  const loadProducts = useCallback(async () => {
    try {
      setLoading(true);
      const data = await listProductsApi({
        search: searchQuery || undefined,
        category: selectedCategory !== 'ALL' ? selectedCategory : undefined,
      });
      setProducts(data);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to load products');
    } finally {
      setLoading(false);
    }
  }, [searchQuery, selectedCategory]);

  useEffect(() => {
    loadProducts();
  }, [loadProducts]);

  useEffect(() => {
    getBusinessTypesApi()
      .then(setBusinessData)
      .catch((err) => console.warn('Presets notice:', err));
  }, []);

  const categories = Array.from(new Set(products.map((p) => p.category || 'General'))).sort();

  const handleOpenAdd = () => {
    setEditingProduct(null);
    setFormName('');
    setFormPrice('');
    setFormCategory(categories[0] || 'General');
    setFormUnit('piece');
    setFormStock('0');
    setFormTrackInventory(false);
    setFormDescription('');
    setFormAttrs([]);
    setErrorMsg('');
    setIsModalOpen(true);
  };

  const handleOpenEdit = (p: Product) => {
    setEditingProduct(p);
    setFormName(p.name);
    setFormPrice(String(p.price));
    setFormCategory(p.category);
    setFormUnit(p.unit || 'piece');
    setFormStock(String(p.stock_quantity));
    setFormTrackInventory(p.track_inventory);
    setFormDescription(p.description || '');

    const attrsList = p.attributes
      ? Object.entries(p.attributes).map(([key, value]) => ({ key, value: String(value) }))
      : [];
    setFormAttrs(attrsList);
    setErrorMsg('');
    setIsModalOpen(true);
  };

  const handleSaveProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName.trim()) {
      setErrorMsg('Product name is required');
      return;
    }
    const priceNum = parseFloat(formPrice);
    if (isNaN(priceNum) || priceNum < 0) {
      setErrorMsg('Please enter a valid price');
      return;
    }

    setSaving(true);
    setErrorMsg('');

    const attributesObj: Record<string, any> = {};
    formAttrs.forEach((attr) => {
      if (attr.key.trim()) {
        attributesObj[attr.key.trim()] = attr.value.trim();
      }
    });

    try {
      if (editingProduct) {
        await updateProductApi(editingProduct.id, {
          name: formName.trim(),
          price: priceNum,
          category: formCategory.trim() || 'General',
          unit: formUnit.trim(),
          stock_quantity: parseInt(formStock, 10) || 0,
          track_inventory: formTrackInventory,
          description: formDescription.trim() || undefined,
          attributes: attributesObj,
        });
      } else {
        await createProductApi({
          name: formName.trim(),
          price: priceNum,
          category: formCategory.trim() || 'General',
          unit: formUnit.trim(),
          stock_quantity: parseInt(formStock, 10) || 0,
          track_inventory: formTrackInventory,
          description: formDescription.trim() || undefined,
          attributes: attributesObj,
        });
      }
      setIsModalOpen(false);
      await loadProducts();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to save product');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!window.confirm(`Are you sure you want to deactivate product "${name}"?`)) return;
    try {
      await deleteProductApi(id);
      await loadProducts();
    } catch (err: any) {
      alert(`Deactivation failed: ${err.message}`);
    }
  };

  const handleQuickAdjustStock = async (productId: string, delta: number) => {
    try {
      await adjustInventoryApi(productId, delta, 'quick_button_click');
      setProducts((prev) =>
        prev.map((p) =>
          p.id === productId
            ? { ...p, stock_quantity: Math.max(0, p.stock_quantity + delta), track_inventory: true }
            : p
        )
      );
    } catch (err: any) {
      alert(`Stock adjustment failed: ${err.message}`);
    }
  };

  const handleApplyBusinessType = async (seed: boolean) => {
    setSettingType(true);
    try {
      const res = await setBusinessTypeApi(selectedType, seed);
      setSuccessMsg(
        `Applied preset: ${selectedType}${seed ? ` and seeded ${res.seeded_count || 0} items!` : '!'}`
      );
      setTimeout(() => setSuccessMsg(''), 4000);
      await loadProducts();
    } catch (err: any) {
      alert(`Failed to set preset: ${err.message}`);
    } finally {
      setSettingType(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200 shadow-2xs">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">Store & Catalog</h1>
            <span className="text-2xs font-semibold px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
              {merchant?.business_type || 'Retail'}
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Manage your product catalog, real-time inventory levels, and business domain presets.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={handleOpenAdd}
            className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-xl bg-blue-600 text-white hover:bg-blue-700 transition shadow-xs"
          >
            <Plus className="w-4 h-4" />
            Add Product
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200 gap-6 text-sm font-medium">
        <button
          type="button"
          onClick={() => setActiveTab('products')}
          className={`pb-3 inline-flex items-center gap-2 border-b-2 transition ${
            activeTab === 'products'
              ? 'border-blue-600 text-blue-700 font-semibold'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Package className="w-4 h-4" />
          Products Catalog ({products.length})
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('inventory')}
          className={`pb-3 inline-flex items-center gap-2 border-b-2 transition ${
            activeTab === 'inventory'
              ? 'border-blue-600 text-blue-700 font-semibold'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Boxes className="w-4 h-4" />
          Stock & Inventory
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('presets')}
          className={`pb-3 inline-flex items-center gap-2 border-b-2 transition ${
            activeTab === 'presets'
              ? 'border-blue-600 text-blue-700 font-semibold'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Sparkles className="w-4 h-4" />
          Domain Presets
        </button>
      </div>

      {/* SUCCESS BANNER */}
      {successMsg && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-xs font-semibold flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          {successMsg}
        </div>
      )}

      {/* TAB 1: PRODUCTS CATALOG */}
      {activeTab === 'products' && (
        <div className="space-y-4">
          {/* Filter Bar */}
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search products by name or category..."
                className="w-full pl-9 pr-3 py-2 bg-white border border-slate-200 rounded-xl text-xs text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
              <button
                type="button"
                onClick={() => setSelectedCategory('ALL')}
                className={`px-3 py-1.5 rounded-lg text-2xs font-semibold transition ${
                  selectedCategory === 'ALL'
                    ? 'bg-slate-900 text-white'
                    : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
                }`}
              >
                All
              </button>
              {categories.map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setSelectedCategory(cat)}
                  className={`px-3 py-1.5 rounded-lg text-2xs font-semibold transition whitespace-nowrap ${
                    selectedCategory === cat
                      ? 'bg-blue-600 text-white'
                      : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>
          </div>

          {/* Products Table */}
          <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-2xs">
            {loading ? (
              <div className="py-16 text-center text-slate-400 text-xs flex items-center justify-center gap-2">
                <RefreshCw className="w-4 h-4 animate-spin text-blue-500" />
                Loading catalog products...
              </div>
            ) : products.length === 0 ? (
              <div className="py-16 text-center text-slate-500 text-xs">
                <Package className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                No products found in catalog. Click &ldquo;Add Product&rdquo; or select a Domain Preset to start.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold">
                    <tr>
                      <th className="py-3 px-4">Item Name</th>
                      <th className="py-3 px-4">Category</th>
                      <th className="py-3 px-4">Price</th>
                      <th className="py-3 px-4">Unit</th>
                      <th className="py-3 px-4">Stock</th>
                      <th className="py-3 px-4">Attributes</th>
                      <th className="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700">
                    {products.map((prod) => (
                      <tr key={prod.id} className="hover:bg-slate-50/70 transition">
                        <td className="py-3 px-4 font-semibold text-slate-900 capitalize">
                          {prod.name}
                          {prod.description && (
                            <span className="block text-2xs font-normal text-slate-400">
                              {prod.description}
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4">
                          <span className="inline-block px-2 py-0.5 rounded bg-slate-100 text-slate-700 text-2xs font-medium">
                            {prod.category}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-bold text-slate-900">₹{prod.price.toFixed(2)}</td>
                        <td className="py-3 px-4 text-slate-500">{prod.unit || 'piece'}</td>
                        <td className="py-3 px-4">
                          {prod.track_inventory ? (
                            <span
                              className={`inline-flex items-center px-2 py-0.5 rounded text-2xs font-semibold ${
                                prod.stock_quantity > 10
                                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                  : prod.stock_quantity > 0
                                  ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                  : 'bg-rose-50 text-rose-700 border border-rose-200'
                              }`}
                            >
                              {prod.stock_quantity} available
                            </span>
                          ) : (
                            <span className="text-slate-400 text-2xs">Untracked</span>
                          )}
                        </td>
                        <td className="py-3 px-4">
                          {prod.attributes && Object.keys(prod.attributes).length > 0 ? (
                            <div className="flex flex-wrap gap-1 max-w-xs">
                              {Object.entries(prod.attributes).map(([k, v]) => (
                                <span
                                  key={k}
                                  className="text-2xs bg-slate-100 px-1.5 py-0.5 rounded text-slate-600"
                                >
                                  {k}: {String(v)}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span className="text-slate-400 text-2xs">—</span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-right">
                          <div className="inline-flex items-center gap-1.5">
                            <button
                              type="button"
                              onClick={() => handleOpenEdit(prod)}
                              className="p-1 rounded-lg text-slate-500 hover:text-blue-600 hover:bg-blue-50 transition"
                              title="Edit item"
                            >
                              <Edit2 className="w-3.5 h-3.5" />
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDelete(prod.id, prod.name)}
                              className="p-1 rounded-lg text-slate-500 hover:text-rose-600 hover:bg-rose-50 transition"
                              title="Deactivate item"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: INVENTORY & STOCK */}
      {activeTab === 'inventory' && (
        <div className="space-y-4">
          <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-2xs">
            <div className="p-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
              <div>
                <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                  Live Stock Control
                </h3>
                <p className="text-2xs text-slate-500">
                  Quick adjustments immediately sync with order deduction and voice queries.
                </p>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold">
                  <tr>
                    <th className="py-3 px-4">Item Name</th>
                    <th className="py-3 px-4">Category</th>
                    <th className="py-3 px-4">Unit Price</th>
                    <th className="py-3 px-4">Current Stock</th>
                    <th className="py-3 px-4 text-right">Quick Adjust</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {products.map((prod) => (
                    <tr key={prod.id} className="hover:bg-slate-50/70 transition">
                      <td className="py-3 px-4 font-semibold text-slate-900 capitalize">
                        {prod.name}
                      </td>
                      <td className="py-3 px-4 text-slate-500">{prod.category}</td>
                      <td className="py-3 px-4 font-medium">₹{prod.price.toFixed(2)}</td>
                      <td className="py-3 px-4">
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-2xs font-bold ${
                            prod.stock_quantity > 10
                              ? 'bg-emerald-100 text-emerald-800'
                              : prod.stock_quantity > 0
                              ? 'bg-amber-100 text-amber-800'
                              : 'bg-rose-100 text-rose-800'
                          }`}
                        >
                          {prod.stock_quantity} {prod.unit || 'units'}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <div className="inline-flex items-center gap-1">
                          <button
                            type="button"
                            onClick={() => handleQuickAdjustStock(prod.id, -5)}
                            className="px-2 py-1 rounded bg-slate-100 hover:bg-slate-200 text-2xs font-bold text-slate-700"
                          >
                            -5
                          </button>
                          <button
                            type="button"
                            onClick={() => handleQuickAdjustStock(prod.id, -1)}
                            className="px-2 py-1 rounded bg-slate-100 hover:bg-slate-200 text-2xs font-bold text-slate-700"
                          >
                            -1
                          </button>
                          <button
                            type="button"
                            onClick={() => handleQuickAdjustStock(prod.id, 1)}
                            className="px-2 py-1 rounded bg-emerald-50 hover:bg-emerald-100 text-2xs font-bold text-emerald-700 border border-emerald-200"
                          >
                            +1
                          </button>
                          <button
                            type="button"
                            onClick={() => handleQuickAdjustStock(prod.id, 5)}
                            className="px-2 py-1 rounded bg-emerald-50 hover:bg-emerald-100 text-2xs font-bold text-emerald-700 border border-emerald-200"
                          >
                            +5
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: DOMAIN PRESETS */}
      {activeTab === 'presets' && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="md:col-span-1 bg-white p-5 rounded-2xl border border-slate-200 shadow-2xs space-y-4">
            <h3 className="text-sm font-bold text-slate-900">Select Business Type</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Preset categories and units tailor speech recognition, entity extraction, and catalog hints for your store.
            </p>

            <div className="space-y-2">
              {businessData?.types?.map((bt) => (
                <button
                  key={bt.id}
                  type="button"
                  onClick={() => setSelectedType(bt.id)}
                  className={`w-full text-left px-3.5 py-2.5 rounded-xl text-xs font-semibold transition border ${
                    selectedType === bt.id
                      ? 'bg-blue-50 border-blue-500 text-blue-700'
                      : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  {bt.label}
                </button>
              ))}
            </div>

            <div className="pt-2 flex flex-col gap-2">
              <button
                type="button"
                disabled={settingType}
                onClick={() => handleApplyBusinessType(false)}
                className="w-full py-2 bg-slate-900 text-white rounded-xl text-xs font-semibold hover:bg-slate-800 transition disabled:opacity-50"
              >
                Apply Preset Hints
              </button>
              <button
                type="button"
                disabled={settingType}
                onClick={() => handleApplyBusinessType(true)}
                className="w-full py-2 bg-blue-600 text-white rounded-xl text-xs font-semibold hover:bg-blue-700 transition disabled:opacity-50 flex items-center justify-center gap-1.5"
              >
                <Sparkles className="w-3.5 h-3.5" />
                Apply & Seed Starter Items
              </button>
            </div>
          </div>

          <div className="md:col-span-2 bg-white p-5 rounded-2xl border border-slate-200 shadow-2xs space-y-4">
            <h3 className="text-sm font-bold text-slate-900">
              Preset Details: {businessData?.presets?.[selectedType]?.label || selectedType}
            </h3>

            {businessData?.presets?.[selectedType] && (
              <div className="space-y-4 text-xs">
                <div>
                  <span className="font-bold text-slate-700 block mb-1.5">Suggested Categories:</span>
                  <div className="flex flex-wrap gap-1.5">
                    {businessData.presets[selectedType].default_categories?.map((cat: string) => (
                      <span
                        key={cat}
                        className="px-2 py-1 rounded bg-blue-50 text-blue-700 border border-blue-200 font-medium"
                      >
                        {cat}
                      </span>
                    ))}
                  </div>
                </div>

                <div>
                  <span className="font-bold text-slate-700 block mb-1.5">Standard Units of Measure:</span>
                  <div className="flex flex-wrap gap-1.5">
                    {businessData.presets[selectedType].default_units?.map((u: string) => (
                      <span key={u} className="px-2 py-1 rounded bg-slate-100 text-slate-700 font-medium">
                        {u}
                      </span>
                    ))}
                  </div>
                </div>

                <div>
                  <span className="font-bold text-slate-700 block mb-1.5">Attribute Suggestions:</span>
                  <div className="flex flex-wrap gap-1.5">
                    {businessData.presets[selectedType].attribute_hints?.map((a: string) => (
                      <span key={a} className="px-2 py-1 rounded bg-amber-50 text-amber-800 font-medium">
                        {a}
                      </span>
                    ))}
                  </div>
                </div>

                <div>
                  <span className="font-bold text-slate-700 block mb-1.5">Starter Items Sample:</span>
                  <div className="space-y-1">
                    {businessData.presets[selectedType].sample_items?.map((item: any) => (
                      <div
                        key={item.name}
                        className="p-2 rounded-lg bg-slate-50 border border-slate-200 flex justify-between items-center"
                      >
                        <span className="capitalize font-medium">{item.name}</span>
                        <span className="text-slate-500 font-semibold">
                          ₹{item.price} per {item.unit}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ADD / EDIT PRODUCT MODAL */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
          <div className="bg-white w-full max-w-lg rounded-2xl shadow-xl border border-slate-200 overflow-hidden flex flex-col max-h-[90vh]">
            <div className="p-4 border-b border-slate-200 flex items-center justify-between">
              <h2 className="text-sm font-bold text-slate-900">
                {editingProduct ? 'Edit Catalog Product' : 'Add New Catalog Product'}
              </h2>
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 text-xs font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSaveProduct} className="p-5 overflow-y-auto space-y-4 text-xs">
              {errorMsg && (
                <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 font-semibold">
                  {errorMsg}
                </div>
              )}

              <div>
                <label className="block font-bold text-slate-700 mb-1">Item Name *</label>
                <input
                  type="text"
                  required
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="e.g. Masala Chai, Paracetamol 650, Cotton Shirt"
                  className="w-full px-3 py-2 border border-slate-200 rounded-xl text-slate-900 focus:outline-hidden focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Price in INR (₹) *</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    required
                    value={formPrice}
                    onChange={(e) => setFormPrice(e.target.value)}
                    placeholder="25.00"
                    className="w-full px-3 py-2 border border-slate-200 rounded-xl text-slate-900 focus:outline-hidden focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block font-bold text-slate-700 mb-1">Unit of Measure</label>
                  <input
                    type="text"
                    value={formUnit}
                    onChange={(e) => setFormUnit(e.target.value)}
                    placeholder="piece, kg, cup, packet"
                    className="w-full px-3 py-2 border border-slate-200 rounded-xl text-slate-900 focus:outline-hidden focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Category</label>
                  <input
                    type="text"
                    value={formCategory}
                    onChange={(e) => setFormCategory(e.target.value)}
                    placeholder="e.g. Beverages, Snacks, General"
                    className="w-full px-3 py-2 border border-slate-200 rounded-xl text-slate-900 focus:outline-hidden focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block font-bold text-slate-700 mb-1">Stock Quantity</label>
                  <input
                    type="number"
                    min="0"
                    value={formStock}
                    onChange={(e) => setFormStock(e.target.value)}
                    placeholder="0"
                    className="w-full px-3 py-2 border border-slate-200 rounded-xl text-slate-900 focus:outline-hidden focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="trackStockCheck"
                  checked={formTrackInventory}
                  onChange={(e) => setFormTrackInventory(e.target.checked)}
                  className="rounded text-blue-600 focus:ring-blue-500 w-4 h-4"
                />
                <label htmlFor="trackStockCheck" className="text-slate-700 font-medium">
                  Track inventory deductions on orders
                </label>
              </div>

              <div>
                <label className="block font-bold text-slate-700 mb-1">Description (Optional)</label>
                <textarea
                  rows={2}
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  placeholder="Optional product details..."
                  className="w-full px-3 py-2 border border-slate-200 rounded-xl text-slate-900 focus:outline-hidden focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {/* Dynamic Key-Value Attributes */}
              <div>
                <div className="flex justify-between items-center mb-1">
                  <label className="font-bold text-slate-700">Attributes (Brand, Size, etc.)</label>
                  <button
                    type="button"
                    onClick={() => setFormAttrs([...formAttrs, { key: '', value: '' }])}
                    className="text-2xs font-bold text-blue-600 hover:text-blue-700"
                  >
                    + Add Field
                  </button>
                </div>
                <div className="space-y-1.5">
                  {formAttrs.map((attr, idx) => (
                    <div key={idx} className="flex gap-2 items-center">
                      <input
                        type="text"
                        placeholder="Key (e.g. Brand)"
                        value={attr.key}
                        onChange={(e) => {
                          const updated = [...formAttrs];
                          updated[idx].key = e.target.value;
                          setFormAttrs(updated);
                        }}
                        className="flex-1 px-2.5 py-1.5 border border-slate-200 rounded-lg text-2xs"
                      />
                      <input
                        type="text"
                        placeholder="Value (e.g. Tata)"
                        value={attr.value}
                        onChange={(e) => {
                          const updated = [...formAttrs];
                          updated[idx].value = e.target.value;
                          setFormAttrs(updated);
                        }}
                        className="flex-1 px-2.5 py-1.5 border border-slate-200 rounded-lg text-2xs"
                      />
                      <button
                        type="button"
                        onClick={() => setFormAttrs(formAttrs.filter((_, i) => i !== idx))}
                        className="text-slate-400 hover:text-rose-600 text-xs px-1"
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              <div className="pt-3 border-t border-slate-100 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 border border-slate-200 text-slate-700 font-semibold rounded-xl hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-4 py-2 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 disabled:opacity-50"
                >
                  {saving ? 'Saving...' : editingProduct ? 'Update Product' : 'Add to Catalog'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
