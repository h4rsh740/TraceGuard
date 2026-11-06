const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export interface IncidentSummary {
  id: string;
  order_ref: string;
  type: string;
  status: string;
  created_at: string;
  updated_at: string;
  event_count: number;
  amount: string | null;
  currency: string | null;
}

export interface SystemHealth {
  status: string;
  app: string;
  version: string;
  database: string;
  sandbox_mode: boolean;
  paypal_base_url: string;
}

export interface IntegrityReport {
  chain_valid: boolean;
  total_events: number;
  chain_head: string | null;
  message?: string;
  broken_at_index?: number;
  broken_at_event_id?: string;
  expected_hash?: string;
  actual_hash?: string;
}

export interface EventItem {
  id: string;
  paypal_event_id: string;
  event_type: string;
  resource_id: string | null;
  amount: string | null;
  currency: string | null;
  occurred_at: string;
  received_at: string;
  event_hash: string;
  prev_hash: string | null;
  payload: Record<string, unknown>;
}

export interface IncidentAction {
  id: string;
  type: string;
  status: string;
  payload: Record<string, any>;
  idempotency_key: string;
  approved_by: string | null;
  approved_at: string | null;
  created_at: string;
}

export interface AgentRun {
  id: string;
  model: string;
  steps: any[];
  tool_calls: any[];
  tokens_used: Record<string, any> | null;
  claims: any[];
  validation_status: string;
  validation_errors: string[];
  created_at: string;
}

export interface IncidentDetail {
  id: string;
  order_ref: string;
  type: string;
  status: string;
  created_at: string;
  updated_at: string;
  timeline: EventItem[];
  actions: IncidentAction[];
  agent_runs: AgentRun[];
}

interface RequestOptions extends RequestInit {
  params?: Record<string, string | undefined>;
}

async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { params, headers, ...init } = options;
  const url = new URL(path, API_BASE_URL);

  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value && value !== "all") {
        url.searchParams.set(key, value);
      }
    });
  }

  const response = await fetch(url.toString(), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
  });

  if (!response.ok) {
    let message = `Request failed: ${response.status}`;

    try {
      const errorBody = await response.json();
      if (typeof errorBody?.detail === "string") {
        message = errorBody.detail;
      } else if (typeof errorBody?.message === "string") {
        message = errorBody.message;
      }
    } catch {
      // Keep generic message when no JSON error body exists.
    }

    throw new Error(message);
  }

  return (await response.json()) as T;
}

export function fetchIncidents(status?: string, type?: string) {
  return apiRequest<{ total: number; items: IncidentSummary[] }>("/incidents", {
    params: {
      status,
      type,
    },
  });
}

export function fetchHealth() {
  return apiRequest<SystemHealth>("/health");
}

export function verifyIntegrity(order_ref?: string) {
  return apiRequest<IntegrityReport>("/integrity/verify", {
    params: { order_ref },
  });
}

export function fetchIncident(incidentId: string) {
  return apiRequest<IncidentDetail>(`/incidents/${incidentId}`);
}

export function runInvestigation(incidentId: string) {
  return apiRequest(`/incidents/${incidentId}/investigate`, {
    method: "POST",
  });
}

export function approveAction(actionId: string, adminToken: string, approvedBy: string) {
  return apiRequest(`/actions/${actionId}/approve`, {
    method: "POST",
    headers: {
      "X-Admin-Token": adminToken,
    },
    body: JSON.stringify({ approved_by: approvedBy }),
  });
}

export function rejectAction(actionId: string, adminToken: string, rejectedBy: string, reason: string) {
  return apiRequest(`/actions/${actionId}/reject`, {
    method: "POST",
    headers: {
      "X-Admin-Token": adminToken,
    },
    body: JSON.stringify({
      rejected_by: rejectedBy,
      reason,
    }),
  });
}
