"use client";

import { useEffect, useState } from "react";
import { verifyIntegrity, IntegrityReport } from "@/lib/api";
import {
  ShieldCheck,
  ShieldAlert,
  Lock,
  RefreshCw,
  Hash,
  Database,
  ArrowRight,
  AlertTriangle,
  FileCheck,
} from "lucide-react";

export default function IntegrityPage() {
  const [report, setReport] = useState<IntegrityReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [orderFilter, setOrderFilter] = useState("");
  const [error, setError] = useState<string | null>(null);

  const checkIntegrity = async (filter?: string) => {
    try {
      setLoading(true);
      setError(null);
      const data = await verifyIntegrity(filter || undefined);
      setReport(data);
    } catch (err: any) {
      setError(err.message || "Failed to verify integrity");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkIntegrity();
  }, []);

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-950/40 to-slate-900 border border-blue-800/40 rounded-xl p-6 shadow-lg flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <Lock className="w-3 h-3" />
              Cryptographic Provenance
            </span>
          </div>
          <h1 className="text-xl font-bold text-slate-100">
            SHA-256 Tamper-Evident Flight Recorder Chain
          </h1>
          <p className="text-xs text-slate-400 mt-1 max-w-xl">
            Every webhook received from PayPal is cryptographically linked to the preceding event hash. If any database row is altered, inserted, or deleted, verification fails with the exact index of compromise.
          </p>
        </div>

        <button
          onClick={() => checkIntegrity(orderFilter)}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2.5 text-xs font-semibold rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white shadow-md shadow-blue-500/20 transition"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          Re-verify Audit Chain
        </button>
      </div>

      {/* Verification Status Card */}
      {loading ? (
        <div className="p-16 text-center text-slate-400 bg-slate-900/60 border border-slate-800 rounded-xl">
          <RefreshCw className="w-8 h-8 animate-spin mx-auto text-blue-400 mb-3" />
          <p className="text-xs">Traversing and hashing all payment events sequentially...</p>
        </div>
      ) : error ? (
        <div className="p-6 rounded-xl bg-rose-950/20 border border-rose-800/40 text-rose-300">
          <AlertTriangle className="w-6 h-6 mb-2" />
          <p className="font-semibold">{error}</p>
        </div>
      ) : report ? (
        <div className="space-y-6">
          <div
            className={`p-6 rounded-xl border shadow-lg ${
              report.chain_valid
                ? "bg-emerald-950/20 border-emerald-500/40"
                : "bg-rose-950/30 border-rose-500/50"
            }`}
          >
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                {report.chain_valid ? (
                  <div className="w-12 h-12 rounded-xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400">
                    <ShieldCheck className="w-6 h-6" />
                  </div>
                ) : (
                  <div className="w-12 h-12 rounded-xl bg-rose-500/20 border border-rose-500/40 flex items-center justify-center text-rose-400">
                    <ShieldAlert className="w-6 h-6" />
                  </div>
                )}
                <div>
                  <h2 className="text-lg font-bold text-slate-100">
                    {report.chain_valid ? "Audit Chain Intact & Verifiable" : "Chain Integrity Compromised!"}
                  </h2>
                  <p className="text-xs text-slate-400">
                    {report.chain_valid
                      ? `All ${report.total_events} sequential events verified against SHA-256 hash links.`
                      : report.message || "Hash mismatch detected in event storage."}
                  </p>
                </div>
              </div>

              <span
                className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${
                  report.chain_valid
                    ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                    : "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                }`}
              >
                {report.chain_valid ? "VALID" : "COMPROMISED"}
              </span>
            </div>

            {/* Hash Details */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6 pt-6 border-t border-slate-800/60 font-mono text-xs">
              <div className="p-3.5 rounded-lg bg-slate-950/70 border border-slate-800">
                <span className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold block mb-1">
                  Chain Head Hash (Latest SHA-256)
                </span>
                <p className="text-blue-400 break-all">{report.chain_head || "None (Chain Empty)"}</p>
              </div>

              <div className="p-3.5 rounded-lg bg-slate-950/70 border border-slate-800">
                <span className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold block mb-1">
                  Sequential Block Count
                </span>
                <p className="text-slate-200 font-bold text-base mt-1">
                  {report.total_events} <span className="text-xs font-normal text-slate-500">records</span>
                </p>
              </div>
            </div>

            {!report.chain_valid && (
              <div className="mt-4 p-4 rounded-lg bg-rose-950/40 border border-rose-800/80 text-rose-200 text-xs font-mono space-y-1">
                <p className="font-bold">Failure Point Detected:</p>
                <p>Broken at Event Index: {report.broken_at_index}</p>
                <p>Event ID: {report.broken_at_event_id}</p>
                <p>Expected Hash: {report.expected_hash}</p>
                <p>Actual Stored Hash: {report.actual_hash}</p>
              </div>
            )}
          </div>

          {/* Cryptographic Architecture Visualizer */}
          <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-6 shadow-sm space-y-4">
            <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
              <Hash className="w-4 h-4 text-blue-400" />
              How the Flight Recorder Guarantees Tamper-Resistance
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
              <div className="p-4 rounded-lg bg-slate-950/60 border border-slate-800 space-y-2">
                <span className="text-xs font-bold text-blue-400">1. Webhook Ingestion</span>
                <p className="text-slate-400 leading-relaxed">
                  Every PayPal webhook arrives with a cryptographic signature from PayPal, which is validated before being ingested into the Postgres write-ahead ledger.
                </p>
              </div>

              <div className="p-4 rounded-lg bg-slate-950/60 border border-slate-800 space-y-2">
                <span className="text-xs font-bold text-blue-400">2. Hash Chain Binding</span>
                <p className="text-slate-400 leading-relaxed">
                  Each event hash binds <code className="text-slate-200">prev_hash</code>, <code className="text-slate-200">paypal_event_id</code>, <code className="text-slate-200">event_type</code>, <code className="text-slate-200">occurred_at</code>, and deterministic canonical JSON payload.
                </p>
              </div>

              <div className="p-4 rounded-lg bg-slate-950/60 border border-slate-800 space-y-2">
                <span className="text-xs font-bold text-blue-400">3. Autonomous Agent Citing</span>
                <p className="text-slate-400 leading-relaxed">
                  The AI investigator can only reference real verified event IDs from this chain. A pure-code validator rejects any hallucinated event IDs or mismatched financial amounts.
                </p>
              </div>
            </div>

            <div className="p-4 rounded-lg bg-slate-950 border border-slate-800 text-[11px] font-mono text-slate-400">
              <span className="text-slate-500">// Canonical Hash Formula</span>
              <p className="text-slate-300 mt-1">
                event_hash = SHA256(prev_hash + &quot;:&quot; + event_id + &quot;:&quot; + event_type + &quot;:&quot; + occurred_at + &quot;:&quot; + json_canonical(payload))
              </p>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

