export interface MerchantContext {
  id: string;
  name: string;
  business_type?: string;
  status: string;
  currency: string;
  user_role: 'OWNER' | 'ADMIN' | 'STAFF' | string;
  created_at: string;
}

export interface ResourceAccessResponse {
  authorized: boolean;
  resource_id: string;
  resource_type: string;
  merchant_id: string;
}
