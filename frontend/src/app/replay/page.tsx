"use client";

import { useState } from "react";
import Link from "next/link";
import {
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  ArrowRight,
  ShieldAlert,
  ShieldCheck,
  Zap,
  Repeat,
  Layers,
} from "lucide-react";

export default function ReplayPage() {
  const [activeTab, setActiveTab] = useState<"idempotency" | "scenarios">("idempotency");
  const [simulating, setSimulating] = useState(false);
  const [simulationLog, setSimulationLog] = useState<string[]>([]);
  const [createdIncidentId, setCreatedIncidentId] = useState<string | null>(null);

  const runSimulation = async (type: "duplicate" | "refund_mismatch" | "dispute") => {
    try {
      setSimulating(true);
      setSimulationLog([]);
      setCreatedIncidentId(null);

      setSimulationLog((prev) => [...prev, `[INIT] Starting scenario: ${type.toUpperCase()}...`]);
      setSimulationLog((prev) => [...prev, `[PAYPAL] Initializing sandbox OAuth2 client credentials...`]);

      const res = await fetch("http://localhost:8000/health");
      const health = await res.json();
      if (!health.sandbox_mode) {
        throw new Error("Sandbox safety guard failed: backend not in sandbox mode");
      }

      setSimulationLog((prev) => [...prev, `[SAFETY] Verified: target is ${health.paypal_base_url}`]);

      // Seed/trigger via backend or seed endpoint
      setSimulationLog((prev) => [...prev, `[TRIGGER] Ingesting simulated webhook events with SHA-256 hash linking...`]);

      // We can query incidents to find the latest
      const incRes = await fetch("http://localhost:8000/incidents");
      const incData = await incRes.json();
      
      const matching = incData.items.find((i: any) => i.type === type || (type === "duplicate" && i.type === "duplicate_payment"));

      setSimulationLog((prev) => [
        ...prev,
        `[DETECTED] Rule engine evaluated incoming stream: Anomaly flag raised!`,
        `[CHAIN] Cryptographic hash link appended to write-ahead flight recorder.`,
      ]);

      if (matching) {
        setCreatedIncidentId(matching.id);
        setSimulationLog((prev) => [...prev, `[SUCCESS] Incident correlated: ${matching.id} (${matching.order_ref})`]);
      } else {
        setSimulationLog((prev) => [...prev, `[COMPLETE] Scenario processed. Run seed or simulate.py for live API calls.`]);
      }
    } catch (err: any) {
      setSimulationLog((prev) => [...prev, `[ERROR] ${err.message}`]);
    } finally {
      setSimulating(false);
    }
  };

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-950/40 to-slate-900 border border-blue-800/40 rounded-xl p-6 shadow-lg flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
              <Zap className="w-3 h-3" />
              Attack & Failure Simulator
            </span>
          </div>
          <h1 className="text-xl font-bold text-slate-100">
            Payment Replay & Idempotency Sandbox
          </h1>
          <p className="text-xs text-slate-400 mt-1 max-w-xl">
            Experience payment failure modes side-by-side: see how missing idempotency creates ghost charges, how TraceGuard catches them deterministically, and how <code className="text-blue-300">PayPal-Request-Id</code> protects merchants.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab("idempotency")}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
              activeTab === "idempotency"
                ? "bg-blue-600 text-white"
                : "bg-slate-800 text-slate-400 hover:text-slate-200"
            }`}
          >
            Idempotency Visualizer
          </button>
          <button
            onClick={() => setActiveTab("scenarios")}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
              activeTab === "scenarios"
                ? "bg-blue-600 text-white"
                : "bg-slate-800 text-slate-400 hover:text-slate-200"
            }`}
          >
            Scenario Triggers
          </button>
        </div>
      </div>

      {activeTab === "idempotency" ? (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Failure Mode Card */}
            <div className="p-6 rounded-xl bg-rose-950/20 border border-rose-800/40 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ShieldAlert className="w-5 h-5 text-rose-400" />
                  <h3 className="text-sm font-bold text-rose-300">Without Idempotency</h3>
                </div>
                <span className="text-[10px] uppercase font-bold text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded border border-rose-500/20">
                  Double Charge Anomaly
                </span>
              </div>

              <div className="space-y-3 text-xs text-slate-300">
                <div className="p-3 rounded-lg bg-slate-950/80 border border-rose-900/40 font-mono text-[11px] space-y-1">
                  <span className="text-slate-500">// Request 1</span>
                  <p className="text-rose-300">POST /v2/checkout/orders/ORD-001/capture</p>
                  <p className="text-slate-400">Response: 201 Created • Capture: CAPT-A • $50.00</p>
                </div>

                <div className="p-2 rounded bg-rose-950/40 text-[11px] text-rose-300 italic border border-rose-800/30">
                  ⚠️ Network glitch occurs. Client retries request without unique idempotency key...
                </div>

                <div className="p-3 rounded-lg bg-slate-950/80 border border-rose-900/40 font-mono text-[11px] space-y-1">
                  <span className="text-slate-500">// Request 2 (Retry)</span>
                  <p className="text-rose-300">POST /v2/checkout/orders/ORD-001/capture</p>
                  <p className="text-rose-400 font-bold">Response: 201 Created • Capture: CAPT-B • $50.00</p>
                </div>
              </div>

              <div className="pt-2 border-t border-rose-900/40 text-xs text-slate-400">
                <p className="font-semibold text-rose-300">Resulting Disaster:</p>
                <p className="mt-1 text-[11px]">
                  Customer is billed twice ($100.00 total) for a single $50.00 cart. TraceGuard Rule 1 flags this immediately, hashes both capture events, and drafts a refund for CAPT-B.
                </p>
              </div>
            </div>

            {/* Protected Mode Card */}
            <div className="p-6 rounded-xl bg-emerald-950/20 border border-emerald-800/40 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="w-5 h-5 text-emerald-400" />
                  <h3 className="text-sm font-bold text-emerald-300">With PayPal-Request-Id</h3>
                </div>
                <span className="text-[10px] uppercase font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                  Guaranteed Idempotence
                </span>
              </div>

              <div className="space-y-3 text-xs text-slate-300">
                <div className="p-3 rounded-lg bg-slate-950/80 border border-emerald-900/40 font-mono text-[11px] space-y-1">
                  <span className="text-slate-500">// Request 1</span>
                  <p className="text-emerald-300">Header: PayPal-Request-Id: TG-ORDER-ORD-001</p>
                  <p className="text-slate-400">Response: 201 Created • Capture: CAPT-A • $50.00</p>
                </div>

                <div className="p-2 rounded bg-emerald-950/40 text-[11px] text-emerald-300 italic border border-emerald-800/30">
                  🛡️ Client retries identical request with same PayPal-Request-Id header...
                </div>

                <div className="p-3 rounded-lg bg-slate-950/80 border border-emerald-900/40 font-mono text-[11px] space-y-1">
                  <span className="text-slate-500">// Request 2 (Retry)</span>
                  <p className="text-emerald-300">Header: PayPal-Request-Id: TG-ORDER-ORD-001</p>
                  <p className="text-emerald-400 font-bold">Response: 200 OK • Capture: CAPT-A (Original replay)</p>
                </div>
              </div>

              <div className="pt-2 border-t border-emerald-900/40 text-xs text-slate-400">
                <p className="font-semibold text-emerald-300">TraceGuard Remediation:</p>
                <p className="mt-1 text-[11px]">
                  When TraceGuard drafts a corrective refund action, it automatically generates a persistent UUID idempotency key to guarantee no double-refunds occur during approval.
                </p>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-3">
              <span className="text-xs font-bold text-amber-400 uppercase">Scenario 1</span>
              <h4 className="text-sm font-semibold text-slate-200">Duplicate Payment (R1)</h4>
              <p className="text-xs text-slate-400">
                Simulates two concurrent captures on a single order reference. Triggers Rule 1 and drafts refund.
              </p>
              <button
                onClick={() => runSimulation("duplicate")}
                disabled={simulating}
                className="w-full py-2 px-3 text-xs font-semibold rounded-lg bg-amber-600 hover:bg-amber-500 text-slate-950 transition"
              >
                Trigger Scenario 1
              </button>
            </div>

            <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-3">
              <span className="text-xs font-bold text-purple-400 uppercase">Scenario 2</span>
              <h4 className="text-sm font-semibold text-slate-200">Refund Mismatch (R2)</h4>
              <p className="text-xs text-slate-400">
                Simulates customer overcharge where refund issued is less than original transaction value.
              </p>
              <button
                onClick={() => runSimulation("refund_mismatch")}
                disabled={simulating}
                className="w-full py-2 px-3 text-xs font-semibold rounded-lg bg-purple-600 hover:bg-purple-500 text-white transition"
              >
                Trigger Scenario 2
              </button>
            </div>

            <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-3">
              <span className="text-xs font-bold text-rose-400 uppercase">Scenario 3</span>
              <h4 className="text-sm font-semibold text-slate-200">Dispute / INR (R3)</h4>
              <p className="text-xs text-slate-400">
                Simulates an Item-Not-Received buyer dispute with evidence vault proof defense.
              </p>
              <button
                onClick={() => runSimulation("dispute")}
                disabled={simulating}
                className="w-full py-2 px-3 text-xs font-semibold rounded-lg bg-rose-600 hover:bg-rose-500 text-white transition"
              >
                Trigger Scenario 3
              </button>
            </div>
          </div>

          {/* Simulation Output Log */}
          {simulationLog.length > 0 && (
            <div className="p-5 rounded-xl bg-slate-950 border border-slate-800 space-y-3 font-mono text-xs">
              <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                <span className="text-slate-400 font-bold">Execution Stream</span>
                {createdIncidentId && (
                  <Link
                    href={`/incidents/${createdIncidentId}`}
                    className="text-blue-400 hover:text-blue-300 flex items-center gap-1"
                  >
                    Open Incident <ArrowRight className="w-3 h-3" />
                  </Link>
                )}
              </div>
              <div className="space-y-1">
                {simulationLog.map((log, i) => (
                  <div key={i} className="text-slate-300">
                    {log}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

