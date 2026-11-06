"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import {
  fetchIncident,
  runInvestigation,
  approveAction,
  rejectAction,
  IncidentDetail,
  EventItem,
} from "@/lib/api";
import {
  ArrowLeft,
  ShieldAlert,
  ShieldCheck,
  Clock,
  CheckCircle2,
  XCircle,
  FileText,
  AlertTriangle,
  Lock,
  ChevronDown,
  ChevronRight,
  Cpu,
  RefreshCw,
  Send,
  Eye,
  Key,
} from "lucide-react";

export default function IncidentDetailPage({
  params,
}: {
  params: Promise<{ id: string }> | { id: string };
}) {
  const unwrappedParams = use(params as any) as { id: string };
  const incidentId = unwrappedParams.id;

  const [incident, setIncident] = useState<IncidentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [investigating, setInvestigating] = useState(false);
  const [activeClaimEventIds, setActiveClaimEventIds] = useState<string[]>([]);
  const [expandedPayloads, setExpandedPayloads] = useState<Record<string, boolean>>({});
  
  // Action approval state
  const [adminToken, setAdminToken] = useState("traceguard_admin_secret");
  const [approving, setApproving] = useState<string | null>(null);
  const [approvalError, setApprovalError] = useState<string | null>(null);
  const [approvalSuccess, setApprovalSuccess] = useState<string | null>(null);

  const loadIncident = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchIncident(incidentId);
      setIncident(data);
    } catch (err: any) {
      setError(err.message || "Failed to load incident");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadIncident();
  }, [incidentId]);

  const handleInvestigate = async () => {
    try {
      setInvestigating(true);
      setError(null);
      await runInvestigation(incidentId);
      await loadIncident();
    } catch (err: any) {
      setError(err.message || "Investigation failed");
    } finally {
      setInvestigating(false);
    }
  };

  const handleApprove = async (actionId: string) => {
    try {
      setApproving(actionId);
      setApprovalError(null);
      setApprovalSuccess(null);
      await approveAction(actionId, adminToken, "lead_auditor");
      setApprovalSuccess("Action approved and idempotently executed via PayPal Sandbox!");
      await loadIncident();
    } catch (err: any) {
      setApprovalError(err.message || "Failed to approve action");
    } finally {
      setApproving(null);
    }
  };

  const handleReject = async (actionId: string) => {
    try {
      setApproving(actionId);
      setApprovalError(null);
      await rejectAction(actionId, adminToken, "lead_auditor", "Dismissed by human auditor");
      setApprovalSuccess("Action rejected and archived.");
      await loadIncident();
    } catch (err: any) {
      setApprovalError(err.message || "Failed to reject action");
    } finally {
      setApproving(null);
    }
  };

  const togglePayload = (id: string) => {
    setExpandedPayloads((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  if (loading) {
    return (
      <div className="py-24 text-center">
        <RefreshCw className="w-8 h-8 animate-spin mx-auto text-blue-500 mb-3" />
        <p className="text-sm text-slate-400">Loading flight recorder timeline and cryptographic audit logs...</p>
      </div>
    );
  }

  if (error || !incident) {
    return (
      <div className="space-y-4">
        <Link href="/" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200">
          <ArrowLeft className="w-4 h-4" /> Back to Incidents
        </Link>
        <div className="p-6 rounded-xl bg-rose-950/20 border border-rose-800/40 text-rose-300">
          <AlertTriangle className="w-6 h-6 mb-2" />
          <p className="font-semibold">{error || "Incident not found"}</p>
        </div>
      </div>
    );
  }

  const latestRun = incident.agent_runs?.[incident.agent_runs.length - 1];
  const isSeeded = incident.type === "dispute" || incident.order_ref.includes("SEEDED");

  return (
    <div className="space-y-6">
      {/* Top Breadcrumb & Actions */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="p-2 rounded-lg bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-slate-100 font-mono">{incident.order_ref}</h1>
              {isSeeded ? (
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-950/40 text-amber-400 border border-amber-700/40">
                  SEEDED
                </span>
              ) : (
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950/40 text-emerald-400 border border-emerald-700/40">
                  LIVE SANDBOX
                </span>
              )}
              <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-800 text-slate-300 uppercase">
                {incident.type.replace("_", " ")}
              </span>
            </div>
            <p className="text-xs text-slate-500 font-mono">Incident ID: {incident.id}</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleInvestigate}
            disabled={investigating}
            className="flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white shadow-md shadow-blue-500/20 transition"
          >
            <Cpu className={`w-4 h-4 ${investigating ? "animate-spin" : ""}`} />
            {investigating ? "Investigating (5 Tool Calls)..." : "Run AI Investigation"}
          </button>
        </div>
      </div>

      {approvalSuccess && (
        <div className="p-3 bg-emerald-950/40 border border-emerald-800/60 rounded-xl text-emerald-300 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
          {approvalSuccess}
        </div>
      )}

      {approvalError && (
        <div className="p-3 bg-rose-950/40 border border-rose-800/60 rounded-xl text-rose-300 text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
          {approvalError}
        </div>
      )}

      {/* Main Grid: Left Timeline / Right Agent & Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Cryptographic Timeline (Flight Recorder) */}
        <div className="lg:col-span-7 space-y-4">
          <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-sm">
            <div className="flex items-center justify-between pb-4 border-b border-slate-800 mb-4">
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-blue-400" />
                <h2 className="text-sm font-semibold text-slate-200">Payment Flight Recorder</h2>
              </div>
              <span className="text-xs text-slate-500 font-mono">
                {incident.timeline?.length || 0} Events in SHA-256 Hash Chain
              </span>
            </div>

            <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-3 before:bottom-3 before:w-0.5 before:bg-slate-800">
              {incident.timeline?.map((evt: EventItem, idx: number) => {
                const isCited = activeClaimEventIds.includes(evt.paypal_event_id);
                const isExpanded = expandedPayloads[evt.id];

                return (
                  <div
                    key={evt.id}
                    id={`event-${evt.paypal_event_id}`}
                    className={`relative rounded-xl p-4 transition-all duration-300 ${
                      isCited
                        ? "bg-amber-950/30 border-2 border-amber-500 shadow-lg shadow-amber-500/10"
                        : "bg-slate-950/60 border border-slate-800 hover:border-slate-700"
                    }`}
                  >
                    {/* Timeline Node Dot */}
                    <div
                      className={`absolute -left-[29px] top-4 w-3 h-3 rounded-full border-2 transition-all ${
                        isCited
                          ? "bg-amber-400 border-amber-200 ring-4 ring-amber-400/30 scale-125"
                          : "bg-blue-500 border-slate-950"
                      }`}
                    />

                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-mono font-semibold text-xs text-slate-200">
                            {evt.event_type}
                          </span>
                          {isCited && (
                            <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-amber-400 text-slate-950 animate-pulse">
                              CITED IN REPORT
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 mt-1 text-[11px] text-slate-400 font-mono">
                          <span>PayPal ID: {evt.paypal_event_id}</span>
                          {evt.resource_id && <span>• Res: {evt.resource_id}</span>}
                        </div>
                      </div>

                      {evt.amount && (
                        <div className="text-right">
                          <span className="font-mono font-bold text-xs text-slate-200">
                            {evt.currency || "USD"} {evt.amount}
                          </span>
                          <span className="block text-[10px] text-slate-500">
                            {new Date(evt.occurred_at).toLocaleTimeString()}
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Hash Provenance Bar */}
                    <div className="mt-3 pt-2 border-t border-slate-800/80 flex items-center justify-between text-[10px] font-mono text-slate-500">
                      <div className="flex items-center gap-1.5 truncate max-w-[80%]">
                        <Lock className="w-3 h-3 text-emerald-400/80 shrink-0" />
                        <span className="truncate">hash: {evt.event_hash}</span>
                      </div>
                      <button
                        onClick={() => togglePayload(evt.id)}
                        className="flex items-center gap-1 text-blue-400 hover:text-blue-300 ml-2"
                      >
                        {isExpanded ? "Hide" : "Payload"}
                        {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                      </button>
                    </div>

                    {isExpanded && (
                      <pre className="mt-3 p-3 rounded-lg bg-slate-950 border border-slate-800 text-[11px] text-slate-300 font-mono overflow-x-auto max-h-60">
                        {JSON.stringify(evt.payload, null, 2)}
                      </pre>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Right: AI Investigator Report & Human Recovery Approval */}
        <div className="lg:col-span-5 space-y-6">
          {/* AI Investigation Card */}
          <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Cpu className="w-4 h-4 text-purple-400" />
                <h2 className="text-sm font-semibold text-slate-200">Autonomous Investigation</h2>
              </div>
              {latestRun && (
                <span
                  className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                    latestRun.validation_status === "passed"
                      ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                      : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                  }`}
                >
                  {latestRun.validation_status === "passed" ? "STRICT VALIDATION PASSED" : "FAILED"}
                </span>
              )}
            </div>

            {!latestRun ? (
              <div className="p-8 text-center text-slate-500 space-y-2">
                <FileText className="w-8 h-8 mx-auto opacity-40" />
                <p className="text-xs">No AI investigation conducted yet.</p>
                <p className="text-[11px] text-slate-400">
                  Click <strong className="text-slate-200">&quot;Run AI Investigation&quot;</strong> to have the agent examine the flight recorder and draft a verifiable report.
                </p>
              </div>
            ) : (
              <div className="space-y-4 text-xs">
                {/* Agent Executive Summary */}
                <div className="p-3.5 rounded-lg bg-slate-950/70 border border-slate-800">
                  <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1">
                    Executive Finding
                  </p>
                  <p className="text-slate-200 leading-relaxed">
                    {latestRun.steps?.[latestRun.steps.length - 1]?.report?.summary ||
                      "Incident anomaly analyzed across PayPal ledger and webhooks."}
                  </p>
                </div>

                {/* Grounded Claims with Click-to-Highlight */}
                <div>
                  <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center justify-between">
                    <span>Evidence-Backed Claims</span>
                    <span className="text-[10px] text-slate-500">Click to highlight in timeline</span>
                  </p>
                  <div className="space-y-2">
                    {latestRun.claims?.map((claim: any, idx: number) => {
                      const isSelected =
                        activeClaimEventIds.length > 0 &&
                        claim.event_ids.some((id: string) => activeClaimEventIds.includes(id));

                      return (
                        <div
                          key={idx}
                          onClick={() => {
                            setActiveClaimEventIds(claim.event_ids);
                            const firstId = claim.event_ids[0];
                            if (firstId) {
                              const el = document.getElementById(`event-${firstId}`);
                              if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
                            }
                          }}
                          className={`p-3 rounded-lg cursor-pointer transition border text-[11px] ${
                            isSelected
                              ? "bg-amber-950/40 border-amber-500/80 text-amber-200 shadow-sm"
                              : "bg-slate-950/50 border-slate-800 hover:border-slate-700 text-slate-300"
                          }`}
                        >
                          <p className="leading-snug">{claim.text}</p>
                          <div className="mt-2 flex flex-wrap gap-1.5 items-center">
                            <span className="text-[10px] text-slate-500">Citing:</span>
                            {claim.event_ids.map((eid: string) => (
                              <span
                                key={eid}
                                className="font-mono text-[9px] px-1.5 py-0.5 rounded bg-blue-950/70 text-blue-300 border border-blue-800/40"
                              >
                                {eid}
                              </span>
                            ))}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Confidence & Token Efficiency */}
                <div className="grid grid-cols-2 gap-3 pt-2">
                  <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800">
                    <span className="text-[10px] text-slate-500 uppercase font-semibold">Model Used</span>
                    <p className="text-slate-200 font-mono mt-0.5">{latestRun.model}</p>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800">
                    <span className="text-[10px] text-slate-500 uppercase font-semibold">Token Usage</span>
                    <p className="text-slate-200 font-mono mt-0.5">
                      {latestRun.tokens_used?.total_tokens || 0} tokens
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Human-in-the-Loop Remediation Card */}
          <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Key className="w-4 h-4 text-emerald-400" />
                <h2 className="text-sm font-semibold text-slate-200">Human Approval Gate</h2>
              </div>
              <span className="text-[10px] text-amber-400 font-semibold bg-amber-950/30 px-2 py-0.5 rounded border border-amber-800/30">
                AI Never Moves Funds
              </span>
            </div>

            {incident.actions && incident.actions.length > 0 ? (
              <div className="space-y-4">
                {incident.actions.map((act) => (
                  <div key={act.id} className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-xs text-slate-200 font-mono uppercase">
                        Action: {act.type}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          act.status === "draft"
                            ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                            : act.status === "executed"
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            : "bg-slate-700 text-slate-300"
                        }`}
                      >
                        {act.status.toUpperCase()}
                      </span>
                    </div>

                    <div className="p-2.5 rounded bg-slate-900 text-[11px] font-mono text-slate-400 space-y-1">
                      <div>Target: {act.payload?.capture_id || act.payload?.dispute_id || "N/A"}</div>
                      {act.payload?.amount && <div>Amount: {act.payload?.currency} {act.payload?.amount}</div>}
                      <div className="truncate text-slate-500">Idempotency Key: {act.idempotency_key}</div>
                    </div>

                    {act.status === "draft" ? (
                      <div className="space-y-3 pt-2">
                        <div>
                          <label className="block text-[10px] text-slate-400 uppercase font-semibold mb-1">
                            Admin Authorization Key
                          </label>
                          <input
                            type="password"
                            value={adminToken}
                            onChange={(e) => setAdminToken(e.target.value)}
                            className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-blue-500 font-mono"
                          />
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => handleApprove(act.id)}
                            disabled={approving === act.id}
                            className="flex-1 py-2 px-3 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold shadow-md shadow-emerald-600/20 transition flex items-center justify-center gap-1.5"
                          >
                            <ShieldCheck className="w-3.5 h-3.5" />
                            {approving === act.id ? "Executing via PayPal..." : "Approve & Execute"}
                          </button>
                          <button
                            onClick={() => handleReject(act.id)}
                            disabled={approving === act.id}
                            className="py-2 px-3 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-300 rounded-lg text-xs font-semibold border border-slate-700 transition"
                          >
                            Reject
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="text-[11px] text-emerald-400 bg-emerald-950/20 p-2.5 rounded border border-emerald-800/30">
                        ✓ Approved by <strong className="text-emerald-300">{act.approved_by}</strong> at{" "}
                        {act.approved_at ? new Date(act.approved_at).toLocaleString() : "just now"}.
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-6 text-center text-slate-500 text-xs">
                Run an AI investigation to draft proposed remediation actions for human review.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

