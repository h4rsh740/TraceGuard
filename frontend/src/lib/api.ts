/**
 * TraceGuard API client for connecting to the FastAPI backend.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface SystemHealth {
  status: string;
  app: string;
  version: string;
  database: string;
  sandbox_mode: boolean;
  paypal_base_url: string;
}

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
  payload: any;
}

export interface ClaimItem {
  text: string;
  event_ids: string[];
}

export interface AIReport {
  summary: string;
  claims: ClaimItem[];
  recommended_action: string;
  target_resource_id: string;
  confidence: number;
  unknowns: string[];
}

export interface ActionItem {
  id: string;
  type: string;
  status: string;
  payload: any;
  idempotency_key: string;
  approved_by: string | null;
  approved_at: string | null;
  created_at: string;
}

export interface AgentRunItem {
  id: string;
  model: string;
  steps: any[];
  tool_calls: any[];
  tokens_used: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  claims: ClaimItem[];
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
  actions: ActionItem[];
  agent_runs: AgentRunItem[];
}

export interface IntegrityReport {
  status: string;
  chain_valid: boolean;
  total_events: number;
  chain_head?: string;
  first_event_id?: string;
  latest_event_id?: string;
  broken_at_index?: number;
  broken_at_event_id?: string;
  error_type?: string;
  expected_hash?: string;
  actual_hash?: string;
  message?: string;
}

export async function fetchHealth(): Promise<SystemHealth> {
  const res = await fetch(`${API_BASE}/health`, { cache: "no-store" });
  if (!res.ok) throw new Error("Health check degraded");
  return res.json();
}

export async function fetchIncidents(
  statusFilter?: string,
  typeFilter?: string
): Promise<{ total: number; items: IncidentSummary[] }> {
  const params = new URLSearchParams();
  if (statusFilter && statusFilter !== "all") params.append("status", statusFilter);
  if (typeFilter && typeFilter !== "all") params.append("type", typeFilter);

  const res = await fetch(`${API_BASE}/incidents?${params.toString()}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch incidents");
  return res.json();
}

export async function fetchIncident(id: string): Promise<IncidentDetail> {
  const res = await fetch(`${API_BASE}/incidents/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch incident ${id}`);
  return res.json();
}

export async function runInvestigation(incidentId: string): Promise<{
  incident_id: string;
  agent_run_id: string;
  validation_status: string;
  validation_errors: string[];
  tokens_used: any;
  report: AIReport;
}> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/investigate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Investigation failed");
  }
  return res.json();
}

export async function approveAction(
  actionId: string,
  adminToken: string,
  approvedBy: string = "lead_auditor"
): Promise<any> {
  const res = await fetch(`${API_BASE}/actions/${actionId}/approve`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Token": adminToken,
    },
    body: JSON.stringify({ approved_by: approvedBy }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Approval failed");
  }
  return res.json();
}

export async function rejectAction(
  actionId: string,
  adminToken: string,
  rejectedBy: string = "lead_auditor",
  reason: string = ""
): Promise<any> {
  const res = await fetch(`${API_BASE}/actions/${actionId}/reject`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Token": adminToken,
    },
    body: JSON.stringify({ rejected_by: rejectedBy, reason }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Rejection failed");
  }
  return res.json();
}

export async function verifyIntegrity(orderRef?: string): Promise<IntegrityReport> {
  const params = new URLSearchParams();
  if (orderRef) params.append("order_ref", orderRef);

  const res = await fetch(`${API_BASE}/integrity/verify?${params.toString()}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Integrity check failed");
  return res.json();
}

