import { apiClient } from './client';

export interface Product {
  id: string;
  merchant_id: string;
  name: string;
  price: number;
  price_minor: number;
  category: string;
  description?: string;
  unit: string;
  stock_quantity: number;
  track_inventory: boolean;
  attributes: Record<string, any>;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
}

export interface ProductCreateInput {
  name: string;
  price: number;
  category?: string;
  description?: string;
  unit?: string;
  stock_quantity?: number;
  track_inventory?: boolean;
  attributes?: Record<string, any>;
}

export interface ProductUpdateInput {
  name?: string;
  price?: number;
  category?: string;
  description?: string;
  unit?: string;
  stock_quantity?: number;
  track_inventory?: boolean;
  attributes?: Record<string, any>;
  is_active?: boolean;
}

export interface InventoryAdjustResponse {
  product_id: string;
  product_name: string;
  previous_quantity: number;
  new_quantity: number;
  delta: number;
  reason: string;
}

export interface SaleItem {
  id: string;
  product_id?: string;
  product_name: string;
  quantity: number;
  unit_price: number;
  subtotal: number;
}

export interface Sale {
  id: string;
  merchant_id: string;
  customer_name?: string;
  customer_phone?: string;
  total_amount: number;
  received_amount: number;
  outstanding_amount: number;
  status: 'PENDING' | 'PARTIAL' | 'PAID' | 'FAILED' | 'CANCELLED';
  payment_id?: string;
  razorpay_order_id?: string;
  razorpay_payment_link_id?: string;
  razorpay_payment_link_url?: string;
  raw_voice_transcript?: string;
  created_at: string;
  updated_at?: string;
  items: SaleItem[];
}

export interface SaleCreateInput {
  customer_name?: string;
  customer_phone?: string;
  auto_create_payment_link?: boolean;
  items: {
    product_name: string;
    quantity: number;
    unit_price?: number;
    product_id?: string;
  }[];
}

export interface PeriodStats {
  orders_count: number;
  total_gmv: number;
  total_collected: number;
  total_outstanding: number;
  paid_orders_count: number;
  pending_orders_count: number;
  partial_orders_count: number;
  collection_rate: number;
  top_products: { name: string; units: number; revenue: number }[];
}

export interface SalesAnalytics {
  merchant: {
    id: string;
    name: string;
    business_type: string;
    currency: string;
  };
  generated_at: string;
  periods: {
    today: PeriodStats;
    week: PeriodStats;
    month: PeriodStats;
    all_time: PeriodStats;
  };
  catalog_summary: any[];
}

export interface BusinessTypesData {
  types: { id: string; label: string }[];
  presets: Record<string, any>;
}

// ── Product Catalog APIs ─────────────────────────────────────────────

// ── Product Catalog APIs ─────────────────────────────────────────────

export async function listProductsApi(params?: {
  category?: string;
  search?: string;
  active_only?: boolean;
}): Promise<Product[]> {
  const q = new URLSearchParams();
  if (params?.category) q.append('category', params.category);
  if (params?.search) q.append('search', params.search);
  if (params?.active_only !== undefined) q.append('active_only', String(params.active_only));

  const qs = q.toString();
  let rawList: any[];

  try {
    rawList = await apiClient.get<any[]>(`/api/sales/catalog/products${qs ? `?${qs}` : ''}`, {
      requiresAuth: false,
    });
  } catch (err: any) {
    if (err?.status === 404 || err?.message?.includes('404')) {
      rawList = await apiClient.get<any[]>(`/api/v1/store/products${qs ? `?${qs}` : ''}`, {
        requiresAuth: true,
      });
    } else {
      throw err;
    }
  }

  return (rawList || []).map((p: any) => ({
    id: String(p.id),
    merchant_id: String(p.merchant_id || '1'),
    name: p.name,
    price: Number(p.price || 0),
    price_minor: p.price_minor ?? Math.round(Number(p.price || 0) * 100),
    category: p.category || 'General',
    description: p.description || '',
    unit: p.unit || 'unit',
    stock_quantity: Number(p.stock_quantity ?? 100),
    track_inventory: Boolean(p.track_inventory ?? false),
    attributes: p.attributes || {},
    is_active: p.is_active ?? true,
    created_at: p.created_at || new Date().toISOString(),
    updated_at: p.updated_at,
  }));
}

export async function createProductApi(data: ProductCreateInput): Promise<Product> {
  let p: any;
  try {
    p = await apiClient.post<any>('/api/sales/catalog/products', data, { requiresAuth: false });
  } catch (err: any) {
    if (err?.status === 404 || err?.message?.includes('404')) {
      p = await apiClient.post<any>('/api/v1/store/products', data, { requiresAuth: true });
    } else {
      throw err;
    }
  }
  return {
    id: String(p.id),
    merchant_id: String(p.merchant_id || '1'),
    name: p.name,
    price: Number(p.price || 0),
    price_minor: p.price_minor ?? Math.round(Number(p.price || 0) * 100),
    category: p.category || 'General',
    description: p.description || '',
    unit: p.unit || 'unit',
    stock_quantity: Number(p.stock_quantity ?? 100),
    track_inventory: Boolean(p.track_inventory ?? false),
    attributes: p.attributes || {},
    is_active: p.is_active ?? true,
    created_at: p.created_at || new Date().toISOString(),
  };
}

export async function updateProductApi(id: string, data: ProductUpdateInput): Promise<Product> {
  let p: any;
  try {
    p = await apiClient.put<any>(`/api/sales/catalog/products/${id}`, data, { requiresAuth: false });
  } catch (err: any) {
    if (err?.status === 404 || err?.message?.includes('404')) {
      p = await apiClient.put<any>(`/api/v1/store/products/${id}`, data, { requiresAuth: true });
    } else {
      throw err;
    }
  }
  return {
    id: String(p.id),
    merchant_id: String(p.merchant_id || '1'),
    name: p.name,
    price: Number(p.price || 0),
    price_minor: p.price_minor ?? Math.round(Number(p.price || 0) * 100),
    category: p.category || 'General',
    description: p.description || '',
    unit: p.unit || 'unit',
    stock_quantity: Number(p.stock_quantity ?? 100),
    track_inventory: Boolean(p.track_inventory ?? false),
    attributes: p.attributes || {},
    is_active: p.is_active ?? true,
    created_at: p.created_at || new Date().toISOString(),
  };
}

export async function deleteProductApi(id: string): Promise<{ detail: string; id: string }> {
  try {
    return await apiClient.delete<{ detail: string; id: string }>(`/api/sales/catalog/products/${id}`, {
      requiresAuth: false,
    });
  } catch (err: any) {
    if (err?.status === 404 || err?.message?.includes('404')) {
      return await apiClient.delete<{ detail: string; id: string }>(`/api/v1/store/products/${id}`, {
        requiresAuth: true,
      });
    }
    throw err;
  }
}

// ── Inventory APIs ───────────────────────────────────────────────────

export async function adjustInventoryApi(
  productId: string,
  delta: number,
  reason: string = 'manual'
): Promise<InventoryAdjustResponse> {
  return apiClient.post<InventoryAdjustResponse>(
    '/api/v1/store/inventory/adjust',
    { product_id: productId, delta, reason },
    { requiresAuth: true }
  );
}

// ── Sales & Orders APIs ──────────────────────────────────────────────

export async function listSalesApi(limit: number = 50, status?: string): Promise<Sale[]> {
  const q = new URLSearchParams();
  q.append('limit', String(limit));
  if (status && status !== 'ALL') q.append('status', status);

  let rawList: any[];
  try {
    rawList = await apiClient.get<any[]>(`/api/sales?${q.toString()}`, { requiresAuth: false });
  } catch (err: any) {
    if (err?.status === 404 || err?.message?.includes('404')) {
      rawList = await apiClient.get<any[]>(`/api/v1/store/sales?${q.toString()}`, { requiresAuth: true });
    } else {
      throw err;
    }
  }

  return (rawList || []).map((s: any) => ({
    id: String(s.id),
    merchant_id: String(s.merchant_id || '1'),
    customer_name: s.customer_name || 'Walk-in Customer',
    customer_phone: s.customer_phone,
    total_amount: Number(s.total_amount || 0),
    received_amount: Number(s.received_amount || 0),
    outstanding_amount: Number(s.outstanding_amount || 0),
    status: s.status || 'PENDING',
    payment_id: s.payment_id,
    razorpay_order_id: s.razorpay_order_id,
    razorpay_payment_link_id: s.razorpay_payment_link_id,
    razorpay_payment_link_url: s.razorpay_payment_link_url,
    raw_voice_transcript: s.raw_voice_transcript,
    created_at: s.created_at || new Date().toISOString(),
    updated_at: s.updated_at,
    items: (s.items || []).map((it: any) => ({
      id: String(it.id || Math.random().toString(36).substring(7)),
      product_id: it.product_id ? String(it.product_id) : undefined,
      product_name: it.product_name || 'Item',
      quantity: Number(it.quantity || 1),
      unit_price: Number(it.unit_price || 0),
      subtotal: Number(it.subtotal || (it.quantity || 1) * (it.unit_price || 0)),
    })),
  }));
}

export async function createSaleApi(data: SaleCreateInput): Promise<Sale> {
  let s: any;
  try {
    s = await apiClient.post<any>('/api/sales', data, { requiresAuth: false });
  } catch (err: any) {
    if (err?.status === 404 || err?.message?.includes('404')) {
      s = await apiClient.post<any>('/api/v1/store/sales', data, { requiresAuth: true });
    } else {
      throw err;
    }
  }
  return {
    id: String(s.id),
    merchant_id: String(s.merchant_id || '1'),
    customer_name: s.customer_name || 'Walk-in Customer',
    customer_phone: s.customer_phone,
    total_amount: Number(s.total_amount || 0),
    received_amount: Number(s.received_amount || 0),
    outstanding_amount: Number(s.outstanding_amount || 0),
    status: s.status || 'PENDING',
    razorpay_payment_link_url: s.razorpay_payment_link_url,
    created_at: s.created_at || new Date().toISOString(),
    items: (s.items || []).map((it: any) => ({
      id: String(it.id || Math.random().toString(36).substring(7)),
      product_name: it.product_name,
      quantity: Number(it.quantity || 1),
      unit_price: Number(it.unit_price || 0),
      subtotal: Number(it.subtotal || 0),
    })),
  };
}

export async function getSaleApi(id: string): Promise<Sale> {
  try {
    return await apiClient.get<Sale>(`/api/sales/${id}`, { requiresAuth: false });
  } catch (err: any) {
    if (err?.status === 404 || err?.message?.includes('404')) {
      return await apiClient.get<Sale>(`/api/v1/store/sales/${id}`, { requiresAuth: true });
    }
    throw err;
  }
}

// ── Business Presets & Profiles ──────────────────────────────────────

export async function getBusinessTypesApi(): Promise<BusinessTypesData> {
  try {
    return await apiClient.get<BusinessTypesData>('/api/sales/catalog/business-types', { requiresAuth: false });
  } catch (err: any) {
    if (err?.status === 404 || err?.message?.includes('404')) {
      return await apiClient.get<BusinessTypesData>('/api/v1/store/business-types', { requiresAuth: true });
    }
    throw err;
  }
}

export async function setBusinessTypeApi(
  businessType: string,
  seedSampleItems: boolean = false
): Promise<any> {
  const payload = { business_type: businessType, seed_sample_items: seedSampleItems };
  try {
    return await apiClient.post('/api/sales/catalog/merchant/business-type', payload, { requiresAuth: false });
  } catch (err: any) {
    if (err?.status === 404 || err?.message?.includes('404')) {
      return await apiClient.post('/api/v1/store/business-type', payload, { requiresAuth: true });
    }
    throw err;
  }
}

// ── Analytics & Excel Export ─────────────────────────────────────────

export async function getSalesAnalyticsApi(): Promise<SalesAnalytics> {
  try {
    return await apiClient.get<SalesAnalytics>('/api/sales/analytics/summary', { requiresAuth: false });
  } catch (err: any) {
    if (err?.status === 404 || err?.message?.includes('404')) {
      return await apiClient.get<SalesAnalytics>('/api/v1/store/analytics/summary', { requiresAuth: true });
    }
    throw err;
  }
}

export function getExcelExportUrl(): string {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
  return `${baseUrl}/api/sales/analytics/export/excel`;
}

