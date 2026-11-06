"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  fetchIncidents,
  fetchHealth,
  verifyIntegrity,
  IncidentSummary,
  SystemHealth,
  IntegrityReport,
} from "@/lib/api";
import {
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  RefreshCw,
  Search,
  ExternalLink,
  Lock,
  FileCheck,
  Layers,
  ArrowRight,
} from "lucide-react";

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<IncidentSummary[]>([]);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [integrity, setIntegrity] = useState<IntegrityReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [incData, healthData, integData] = await Promise.all([
        fetchIncidents(statusFilter, typeFilter).catch(() => ({ total: 0, items: [] })),
        fetchHealth().catch(() => null),
        verifyIntegrity().catch(() => null),
      ]);
      setIncidents(incData.items);
      setHealth(healthData);
      setIntegrity(integData);
    } catch (err: any) {
      setError(err.message || "Failed to load dashboard data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [statusFilter, typeFilter]);

  const filteredIncidents = incidents.filter((inc) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      inc.id.toLowerCase().includes(q) ||
      inc.order_ref.toLowerCase().includes(q) ||
      inc.type.toLowerCase().includes(q)
    );
  });

  const openCount = incidents.filter((i) => i.status === "open").length;
  const investigatingCount = incidents.filter((i) => i.status === "investigating").length;
  const resolvedCount = incidents.filter((i) => i.status === "resolved").length;

  return (
    <div className="space-y-8">
      {/* Banner / Sandbox Notice */}
      <div className="bg-gradient-to-r from-blue-950/40 via-purple-950/30 to-slate-900 border border-blue-800/40 rounded-xl p-5 shadow-lg flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              PayPal Sandbox Enforced
            </span>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
              <Lock className="w-3 h-3" />
              SHA-256 Hash Chain
            </span>
          </div>
          <h1 className="text-xl font-bold text-slate-100 tracking-tight">
            TraceGuard Payment Anomaly Flight Recorder
          </h1>
          <p className="text-xs text-slate-400 max-w-2xl">
            Autonomous anomaly detector and proof engine for PayPal payments. Every agent claim is strictly validated against immutable cryptographic event IDs. Human approval is required before moving funds.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={loadData}
            disabled={loading}
            className="flex items-center gap-2 px-3.5 py-2 text-xs font-medium rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
          <Link
            href="/replay"
            className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium rounded-lg bg-blue-600 hover:bg-blue-500 text-white shadow-md shadow-blue-500/20 transition"
          >
            Simulate Attack
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>

      {/* KPI Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Total Incidents</span>
            <AlertTriangle className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-slate-100">{incidents.length}</div>
          <div className="text-xs text-slate-500 mt-1">Reconstructed from webhooks</div>
        </div>

        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Open Anomaly</span>
            <ShieldAlert className="w-4 h-4 text-rose-400" />
          </div>
          <div className="text-2xl font-bold text-rose-400">{openCount}</div>
          <div className="text-xs text-slate-500 mt-1">{investigatingCount} in active investigation</div>
        </div>

        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Resolved</span>
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-400">{resolvedCount}</div>
          <div className="text-xs text-slate-500 mt-1">Refunded or defended</div>
        </div>

        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Chain Integrity</span>
            <FileCheck className="w-4 h-4 text-blue-400" />
          </div>
          <div className="text-2xl font-bold text-blue-400">
            {integrity?.chain_valid ? "VALID" : integrity ? "DEGRADED" : "OFFLINE"}
          </div>
          <div className="text-xs text-slate-500 mt-1">
            {integrity?.total_events ?? 0} events verified
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 shadow-sm">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            placeholder="Search by order ref, incident ID, or type..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-slate-950/70 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500 transition"
          />
        </div>
        <div className="flex items-center gap-2 overflow-x-auto">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-slate-950/70 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-blue-500"
          >
            <option value="all">All Statuses</option>
            <option value="open">Open</option>
            <option value="investigating">Investigating</option>
            <option value="resolved">Resolved</option>
            <option value="dismissed">Dismissed</option>
          </select>
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="bg-slate-950/70 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-blue-500"
          >
            <option value="all">All Incident Types</option>
            <option value="duplicate_payment">Duplicate Payment (R1)</option>
            <option value="refund_mismatch">Refund Mismatch (R2)</option>
            <option value="dispute">Dispute / INR (R3)</option>
          </select>
        </div>
      </div>

      {/* Incident List Table */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
        <div className="px-5 py-4 border-b border-slate-800 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
            <Layers className="w-4 h-4 text-blue-400" />
            Detected Incidents
          </h2>
          <span className="text-xs text-slate-500">
            Showing {filteredIncidents.length} of {incidents.length}
          </span>
        </div>

        {loading ? (
          <div className="p-12 text-center text-slate-400">
            <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-blue-400" />
            <p className="text-xs">Querying deterministic incident index...</p>
          </div>
        ) : error ? (
          <div className="p-8 text-center text-rose-400">
            <AlertTriangle className="w-6 h-6 mx-auto mb-2" />
            <p className="text-xs">{error}</p>
          </div>
        ) : filteredIncidents.length === 0 ? (
          <div className="p-12 text-center text-slate-500">
            <Layers className="w-8 h-8 mx-auto mb-2 opacity-40" />
            <p className="text-sm font-medium text-slate-400">No payment anomalies detected</p>
            <p className="text-xs mt-1">Run a scenario simulator to trigger live webhook anomalies.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-slate-950/50 border-b border-slate-800 text-slate-400 font-medium">
                  <th className="py-3 px-4">Order Ref</th>
                  <th className="py-3 px-4">Type</th>
                  <th className="py-3 px-4">Provenance</th>
                  <th className="py-3 px-4">Amount</th>
                  <th className="py-3 px-4">Events</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Detected</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {filteredIncidents.map((inc) => {
                  const isSeeded = inc.type === "dispute" || inc.order_ref.includes("SEEDED");
                  return (
                    <tr key={inc.id} className="hover:bg-slate-800/40 transition">
                      <td className="py-3 px-4">
                        <Link
                          href={`/incidents/${inc.id}`}
                          className="font-mono font-medium text-blue-400 hover:text-blue-300 flex items-center gap-1.5"
                        >
                          {inc.order_ref}
                          <ExternalLink className="w-3 h-3 opacity-60" />
                        </Link>
                        <span className="block font-mono text-[10px] text-slate-500 truncate max-w-[120px]">
                          {inc.id}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        {inc.type === "duplicate_payment" && (
                          <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-500/10 text-amber-300 border border-amber-500/20">
                            Duplicate Payment
                          </span>
                        )}
                        {inc.type === "refund_mismatch" && (
                          <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-purple-500/10 text-purple-300 border border-purple-500/20">
                            Refund Mismatch
                          </span>
                        )}
                        {inc.type === "dispute" && (
                          <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-rose-500/10 text-rose-300 border border-rose-500/20">
                            INR Dispute
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        {isSeeded ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-amber-950/40 text-amber-400 border border-amber-700/40" title="Disputes are seeded because PayPal sandbox restricts dispute creation via REST API. Backed by real evidence vault.">
                            SEEDED
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950/40 text-emerald-400 border border-emerald-700/40" title="Direct capture from live PayPal Sandbox API">
                            LIVE SANDBOX
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4 font-mono font-medium text-slate-200">
                        {inc.amount ? `${inc.currency || "USD"} ${inc.amount}` : "—"}
                      </td>
                      <td className="py-3 px-4 text-slate-400">
                        <span className="inline-flex items-center gap-1">
                          <Layers className="w-3 h-3 text-slate-500" />
                          {inc.event_count}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        {inc.status === "open" && (
                          <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                            Open
                          </span>
                        )}
                        {inc.status === "investigating" && (
                          <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
                            Investigating
                          </span>
                        )}
                        {inc.status === "resolved" && (
                          <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                            Resolved
                          </span>
                        )}
                        {inc.status === "dismissed" && (
                          <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-slate-700 text-slate-300">
                            Dismissed
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-slate-500">
                        {new Date(inc.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <Link
                          href={`/incidents/${inc.id}`}
                          className="inline-flex items-center gap-1 px-3 py-1 text-xs font-medium rounded-md bg-slate-800 hover:bg-slate-700 text-blue-400 hover:text-blue-300 border border-slate-700 transition"
                        >
                          Investigate
                          <ArrowRight className="w-3 h-3" />
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Honesty & Provenance Callout */}
      <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/80 text-xs text-slate-400 flex items-start gap-3">
        <ShieldCheck className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <p className="font-semibold text-slate-300">Auditable Provenance & Integrity Statement</p>
          <p>
            Duplicate payment captures and refund mismatches originate from real PayPal Sandbox REST API executions (<code className="text-slate-300">api-m.sandbox.paypal.com</code>). Because PayPal restricts simulated buyer dispute creation via REST, dispute scenarios are marked <strong className="text-amber-300">SEEDED</strong> and correlate against pre-ingested cryptographic delivery evidence in the immutable evidence vault.
          </p>
        </div>
      </div>
    </div>
  );
}
