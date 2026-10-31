import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TraceGuard | PayPal Flight Recorder",
  description:
    "Reconstructs payment anomalies from real PayPal sandbox events with tamper-evident cryptographic proofs.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased min-h-screen bg-slate-50 font-sans">
        {children}
      </body>
    </html>
  );
}
