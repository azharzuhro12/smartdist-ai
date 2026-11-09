/**
 * Typed API client for SmartDist AI Backend REST API.
 * Accurately aligned with FastAPI endpoint paths, query parameters, and Pydantic schemas.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8035/api/v1";

export type UserRole = "ADMIN" | "ANALYST" | "VIEWER";

export interface UserProfile {
  id: number;
  username: string;
  email: string;
  role: UserRole;
  full_name?: string | null;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: UserProfile;
}

let inMemoryToken: string | null = null;

export function setAuthToken(token: string | null) {
  inMemoryToken = token;
}

export function getAuthToken(): string | null {
  return inMemoryToken;
}

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp("(^|;\\s*)(" + name + ")=([^;]*)"));
  return match ? decodeURIComponent(match[3]) : null;
}

async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
  const headers = new Headers(options.headers || {});
  headers.set("X-Requested-With", "XMLHttpRequest");
  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (inMemoryToken) {
    headers.set("Authorization", `Bearer ${inMemoryToken}`);
  }

  // Double-submit CSRF protection for cookie-authenticated mutating requests
  const method = (options.method || "GET").toUpperCase();
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    const csrfToken = getCookie("csrf_token");
    if (csrfToken) {
      headers.set("X-CSRF-Token", csrfToken);
    }
  }

  const mergedOptions: RequestInit = {
    ...options,
    headers,
    credentials: "include", // Sends HttpOnly cookie
  };

  const res = await fetch(url, mergedOptions);
  if (res.status === 401 && typeof window !== "undefined") {
    if (!window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
  }
  return res;
}

export type AnomalySeverity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "NORMAL";
export type AnomalyStatus = "NEW" | "INVESTIGATING" | "CONFIRMED" | "FALSE_POSITIVE" | "RESOLVED";

export interface AnomalyItem {
  id: number;
  detection_run_id?: number;
  anomaly_date: string;
  branch_id: number;
  branch_name?: string;
  product_id: number;
  product_name?: string;
  category_name?: string;
  observed_quantity: number;
  expected_quantity: number;
  deviation: number;
  percentage_deviation?: number;
  anomaly_score: number;
  severity: AnomalySeverity;
  direction: string;
  detector_evidence?: any;
  explanation: string;
  recommended_actions?: string[] | string;
  investigation_status: AnomalyStatus;
  resolution_note?: string;
  data_provenance?: string;
  created_at?: string;
}

export interface AnomalyListResponse {
  items: AnomalyItem[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface DataSummaryResponse {
  branches: number;
  categories: number;
  products: number;
  daily_sales_records: number;
  warehouses: number;
  suppliers: number;
  inventory_records: number;
  total_physical_stock: number;
  total_reserved_stock: number;
  available_stock: number;
  sales_start_date?: string | null;
  sales_end_date?: string | null;
}

export interface OptimizationSummaryItem {
  product_id: number;
  product_name: string;
  branch_id: number;
  branch_name: string;
  available_stock?: number | null;
  reorder_point?: number | null;
  safety_stock?: number | null;
  expected_lead_time_demand?: number | null;
  stockout_probability?: number | null;
  risk_category?: string;
  recommended_order_quantity?: number;
  decision?: string;
}

export interface OptimizationSummaryResponse {
  items: OptimizationSummaryItem[];
  total: number;
  page: number;
  size: number;
  pages: number;
  total_reorder_required: number;
  critical_risk_count: number;
  generated_at: string;
}

export interface DailyForecastRecord {
  date: string;
  product_id: number;
  branch_id: number;
  predicted_demand: number;
  horizon_step: number;
  model_name: string;
  model_version: string;
  forecast_timestamp: string;
}

export interface ForecastResponse {
  product_id: number;
  branch_id: number;
  horizon_days: number;
  model_name: string;
  model_version: string;
  status: string;
  forecast_timestamp: string;
  daily_forecasts: DailyForecastRecord[];
  forecast_points?: {
    date: string;
    step_ahead: number;
    forecasted_quantity: number;
  }[];
}

export type ForecastResult = ForecastResponse;

export interface ChatResult {
  query: string;
  intent: string;
  answer: string;
  tool_used: string;
  citations: string[];
  data: any;
  provenance: string;
}

export const api = {
  // Authentication
  async login(usernameOrEmail: string, password: string): Promise<TokenResponse> {
    const res = await fetchWithAuth(`${API_BASE}/auth/login`, {
      method: "POST",
      body: JSON.stringify({ username_or_email: usernameOrEmail, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Invalid username or password");
    }
    const data: TokenResponse = await res.json();
    setAuthToken(data.access_token);
    return data;
  },

  async getMe(): Promise<UserProfile> {
    const res = await fetchWithAuth(`${API_BASE}/auth/me`);
    if (!res.ok) {
      throw new Error(`Authentication check failed: ${res.statusText}`);
    }
    return res.json();
  },

  async logout(): Promise<void> {
    await fetchWithAuth(`${API_BASE}/auth/logout`, { method: "POST" }).catch(() => {});
    setAuthToken(null);
  },

  async getHealth() {
    const res = await fetchWithAuth(`${API_BASE.replace("/api/v1", "")}/health`);
    if (!res.ok) {
      throw new Error(`Health check failed: ${res.statusText}`);
    }
    return res.json();
  },

  async getDataSummary(): Promise<DataSummaryResponse> {
    const res = await fetchWithAuth(`${API_BASE}/data/summary`);
    if (!res.ok) {
      throw new Error(`Failed to load data summary: ${res.statusText}`);
    }
    return res.json();
  },

  async getTopProducts(limit = 10, metric: "volume" | "revenue" = "volume") {
    const query =
      metric === "revenue"
        ? `What are the top ${limit} selling products by revenue?`
        : `What are the top ${limit} selling products by volume?`;
    const res = await fetchWithAuth(`${API_BASE}/assistant/sql`, {
      method: "POST",
      body: JSON.stringify({ query }),
    });
    if (!res.ok) {
      throw new Error(`Failed to load top products: ${res.statusText}`);
    }
    return res.json();
  },

  async getBranchPerformance() {
    const res = await fetchWithAuth(`${API_BASE}/assistant/sql`, {
      method: "POST",
      body: JSON.stringify({ query: "Show sales by branch" }),
    });
    if (!res.ok) {
      throw new Error(`Failed to load branch performance: ${res.statusText}`);
    }
    return res.json();
  },

  async getForecast(productId: number, branchId: number, horizon = 7): Promise<ForecastResponse> {
    const res = await fetchWithAuth(`${API_BASE}/inventory/${productId}/${branchId}/forecast?horizon_days=${horizon}`);
    if (!res.ok) {
      throw new Error(`Failed to load forecast: ${res.statusText}`);
    }
    const data: ForecastResponse = await res.json();
    data.forecast_points = (data.daily_forecasts || []).map((df) => ({
      date: df.date,
      step_ahead: df.horizon_step,
      forecasted_quantity: df.predicted_demand,
    }));
    return data;
  },

  async getInventorySummary(page = 1, size = 15, serviceLevel = 0.95): Promise<OptimizationSummaryResponse> {
    const res = await fetchWithAuth(
      `${API_BASE}/inventory/optimization-summary?page=${page}&size=${size}&service_level=${serviceLevel}`
    );
    if (!res.ok) {
      throw new Error(`Failed to load inventory summary: ${res.statusText}`);
    }
    return res.json();
  },

  async getAnomalies(status?: string, severity?: string, size = 50, page = 1): Promise<AnomalyListResponse> {
    const params = new URLSearchParams();
    if (status) params.append("status", status);
    if (severity) params.append("severity", severity);
    params.append("page", page.toString());
    params.append("size", size.toString());
    const res = await fetchWithAuth(`${API_BASE}/anomalies?${params.toString()}`);
    if (!res.ok) {
      throw new Error(`Failed to load anomalies: ${res.statusText}`);
    }
    return res.json();
  },

  async patchAnomalyStatus(anomalyId: number, newStatus: string, resolutionNote?: string): Promise<AnomalyItem> {
    const res = await fetchWithAuth(`${API_BASE}/anomalies/${anomalyId}/status`, {
      method: "PATCH",
      body: JSON.stringify({
        status: newStatus,
        resolution_note: resolutionNote || "Updated via Web Dashboard",
      }),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Failed to update anomaly status: ${res.statusText}`);
    }
    return res.json();
  },

  async chatAssistant(query: string, conversationId?: string): Promise<ChatResult> {
    const res = await fetchWithAuth(`${API_BASE}/assistant/chat`, {
      method: "POST",
      body: JSON.stringify({ query, conversation_id: conversationId }),
    });
    if (!res.ok) {
      throw new Error(`Assistant error: ${res.statusText}`);
    }
    return res.json();
  },

  async executeWorkflow(workflowName: string, parameters: Record<string, any> = {}) {
    const res = await fetchWithAuth(`${API_BASE}/assistant/workflow`, {
      method: "POST",
      body: JSON.stringify({ workflow_name: workflowName, parameters }),
    });
    if (!res.ok) {
      throw new Error(`Workflow execution error: ${res.statusText}`);
    }
    return res.json();
  },

  async getWorkflows() {
    const res = await fetchWithAuth(`${API_BASE}/assistant/workflows`);
    if (!res.ok) {
      throw new Error(`Failed to load workflows: ${res.statusText}`);
    }
    return res.json();
  },

  async searchPolicy(query: string) {
    const res = await fetchWithAuth(`${API_BASE}/assistant/policy-search`, {
      method: "POST",
      body: JSON.stringify({ query, top_k: 3 }),
    });
    if (!res.ok) {
      throw new Error(`Policy search failed: ${res.statusText}`);
    }
    return res.json();
  },
};
