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
  return apiClient.get<Product[]>(`/api/v1/store/products${qs ? `?${qs}` : ''}`, {
    requiresAuth: true,
  });
}

export async function createProductApi(data: ProductCreateInput): Promise<Product> {
  return apiClient.post<Product>('/api/v1/store/products', data, { requiresAuth: true });
}

export async function updateProductApi(id: string, data: ProductUpdateInput): Promise<Product> {
  return apiClient.put<Product>(`/api/v1/store/products/${id}`, data, { requiresAuth: true });
}

export async function deleteProductApi(id: string): Promise<{ detail: string; id: string }> {
  return apiClient.delete<{ detail: string; id: string }>(`/api/v1/store/products/${id}`, {
    requiresAuth: true,
  });
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

  return apiClient.get<Sale[]>(`/api/v1/store/sales?${q.toString()}`, { requiresAuth: true });
}

export async function createSaleApi(data: SaleCreateInput): Promise<Sale> {
  return apiClient.post<Sale>('/api/v1/store/sales', data, { requiresAuth: true });
}

export async function getSaleApi(id: string): Promise<Sale> {
  return apiClient.get<Sale>(`/api/v1/store/sales/${id}`, { requiresAuth: true });
}

// ── Business Presets & Profiles ──────────────────────────────────────

export async function getBusinessTypesApi(): Promise<BusinessTypesData> {
  return apiClient.get<BusinessTypesData>('/api/v1/store/business-types', { requiresAuth: true });
}

export async function setBusinessTypeApi(
  businessType: string,
  seedSampleItems: boolean = false
): Promise<any> {
  return apiClient.post(
    '/api/v1/store/business-type',
    { business_type: businessType, seed_sample_items: seedSampleItems },
    { requiresAuth: true }
  );
}

// ── Analytics & Excel Export ─────────────────────────────────────────

export async function getSalesAnalyticsApi(): Promise<SalesAnalytics> {
  return apiClient.get<SalesAnalytics>('/api/v1/store/analytics/summary', { requiresAuth: true });
}

export function getExcelExportUrl(): string {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
  return `${baseUrl}/api/v1/store/analytics/export/excel`;
}
