"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import AgentStream from "@/components/AgentStream";

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [invoiceId, setInvoiceId] = useState<string | null>(null);
  const [finalStatus, setFinalStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    setError(null);
    setFinalStatus(null);
    setInvoiceId(null);
    try {
      const res = await api.upload(file);
      setInvoiceId(res.invoice_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setUploading(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">
          Upload an invoice
        </h1>
        <p className="mt-1 text-sm text-zinc-400">
          Drop a PDF or image. A pipeline of agents — intake, extraction,
          validation, approval — will process it live, explaining every decision.
        </p>
      </div>

      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          const f = e.dataTransfer.files?.[0];
          if (f) setFile(f);
        }}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed p-12 text-center transition-colors ${
          dragOver
            ? "border-emerald-500 bg-emerald-500/5"
            : "border-zinc-700 bg-zinc-900/30 hover:border-zinc-500"
        }`}
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.5}
          className="mb-3 h-10 w-10 text-zinc-500"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 16.5V9.75m0 0 3 3m-3-3-3 3M6.75 19.5a4.5 4.5 0 0 1-1.41-8.775 5.25 5.25 0 0 1 10.233-2.33 3 3 0 0 1 3.758 3.848A3.752 3.752 0 0 1 18 19.5H6.75Z"
          />
        </svg>
        <p className="text-sm font-medium text-zinc-200">
          {file ? file.name : "Click to choose or drag & drop"}
        </p>
        <p className="mt-1 text-xs text-zinc-500">
          PDF, PNG, JPG · scanned or native
        </p>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,image/*"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) setFile(f);
          }}
        />
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">
          {error}
        </div>
      )}

      {!invoiceId && (
        <button
          onClick={handleUpload}
          disabled={!file || uploading}
          className="w-full rounded-lg bg-emerald-500 px-4 py-2.5 text-sm font-semibold text-zinc-950 transition-colors hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {uploading ? "Uploading…" : "Process invoice"}
        </button>
      )}

      {invoiceId && (
        <AgentStream
          invoiceId={invoiceId}
          onComplete={(status) => setFinalStatus(status)}
        />
      )}

      {finalStatus && (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4">
          <p className="text-sm text-emerald-300">
            Pipeline finished with status{" "}
            <span className="font-semibold">{finalStatus}</span>.
          </p>
          <Link
            href={`/invoices/${invoiceId}`}
            className="mt-3 inline-block rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-zinc-950 transition-colors hover:bg-emerald-400"
          >
            View audit trail →
          </Link>
        </div>
      )}
    </div>
  );
}
