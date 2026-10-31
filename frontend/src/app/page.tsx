import React from "react";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8 bg-slate-900 text-slate-100">
      <div className="z-10 max-w-4xl w-full text-center space-y-6">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          PayPal Sandbox Only &bull; Phase 1 Scaffold Active
        </div>

        <h1 className="text-5xl font-extrabold tracking-tight bg-gradient-to-r from-blue-400 via-sky-300 to-indigo-300 bg-clip-text text-transparent">
          TraceGuard
        </h1>

        <p className="text-xl text-slate-300 max-w-2xl mx-auto leading-relaxed">
          The Flight Recorder for PayPal Payments. Reconstructing what went wrong from real PayPal events, proving it with a tamper-evident hash chain, and preparing fixes for human approval.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-6 text-left">
          <div className="p-5 rounded-xl bg-slate-800/80 border border-slate-700">
            <h3 className="font-bold text-sky-400 mb-1">Deterministic Detection</h3>
            <p className="text-xs text-slate-400">Code-driven incident builder enforces strict duplicate, mismatch, and dispute rules.</p>
          </div>
          <div className="p-5 rounded-xl bg-slate-800/80 border border-slate-700">
            <h3 className="font-bold text-sky-400 mb-1">Evidence Vault</h3>
            <p className="text-xs text-slate-400">SHA-256 cryptographic hash-chained events with real-time integrity verification.</p>
          </div>
          <div className="p-5 rounded-xl bg-slate-800/80 border border-slate-700">
            <h3 className="font-bold text-sky-400 mb-1">Human-in-the-Loop</h3>
            <p className="text-xs text-slate-400">AI drafts remediation; human approval required before any money moves.</p>
          </div>
        </div>
      </div>
    </main>
  );
}

