"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { api, type BatchUploadResult } from "@/lib/api";
import AgentStream from "@/components/AgentStream";

export default function UploadPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [results, setResults] = useState<BatchUploadResult[] | null>(null);
  const [liveId, setLiveId] = useState<string | null>(null);
  const [finalStatus, setFinalStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function addFiles(list: FileList | null) {
    if (!list) return;
    const next = Array.from(list);
    setFiles((prev) => {
      const seen = new Set(prev.map((f) => `${f.name}:${f.size}`));
      return [...prev, ...next.filter((f) => !seen.has(`${f.name}:${f.size}`))];
    });
    setResults(null);
    setLiveId(null);
    setFinalStatus(null);
    setError(null);
  }

  async function handleUpload() {
    if (files.length === 0) return;
    setUploading(true);
    setError(null);
    setResults(null);
    setFinalStatus(null);
    setLiveId(null);
    try {
      let rows: BatchUploadResult[];
      if (files.length === 1) {
        const r = await api.upload(files[0]);
        rows = [
          {
            filename: files[0].name,
            invoice_id: r.invoice_id,
            status: r.status,
            error: null,
          },
        ];
      } else {
        const res = await api.uploadBatch(files);
        rows = res.results;
      }
      setResults(rows);
      setLiveId(rows.find((r) => r.invoice_id)?.invoice_id ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setUploading(false);
    }
  }

  function reset() {
    setFiles([]);
    setResults(null);
    setLiveId(null);
    setFinalStatus(null);
    setError(null);
  }

  const accepted = results?.filter((r) => r.invoice_id).length ?? 0;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">
          Upload invoices
        </h1>
        <p className="mt-1 text-sm text-zinc-400">
          Drop one or many PDFs and images. The agent pipeline processes each file
          live, explaining every decision it makes.
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
          addFiles(e.dataTransfer.files);
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
          {files.length === 0
            ? "Click to choose or drag & drop"
            : `${files.length} file${files.length === 1 ? "" : "s"} selected`}
        </p>
        <p className="mt-1 text-xs text-zinc-500">
          PDF, PNG, JPG · multiple files supported
        </p>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,image/*"
          multiple
          className="hidden"
          onChange={(e) => addFiles(e.target.files)}
        />
      </div>

      {files.length > 0 && (
        <ul className="space-y-1.5 rounded-xl border border-zinc-800 bg-zinc-900/40 p-3">
          {files.map((f) => (
            <li
              key={`${f.name}:${f.size}`}
              className="flex items-center justify-between gap-3 rounded-lg px-2 py-1 text-sm text-zinc-300"
            >
              <span className="truncate">{f.name}</span>
              <span className="flex items-center gap-3 text-xs text-zinc-500">
                {(f.size / 1024).toFixed(0)} KB
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setFiles((prev) => prev.filter((x) => x !== f));
                  }}
                  className="rounded px-1.5 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300"
                  aria-label={`Remove ${f.name}`}
                >
                  ✕
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">
          {error}
        </div>
      )}

      {!results && (
        <button
          onClick={handleUpload}
          disabled={files.length === 0 || uploading}
          className="w-full rounded-lg bg-emerald-500 px-4 py-2.5 text-sm font-semibold text-zinc-950 transition-colors hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {uploading
            ? "Uploading…"
            : `Process ${files.length || ""} invoice${files.length === 1 ? "" : "s"}`}
        </button>
      )}

      {results && (
        <div className="space-y-3 rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
          <p className="text-sm text-zinc-300">
            Accepted{" "}
            <span className="font-semibold text-emerald-400">{accepted}</span> of{" "}
            {results.length} file{results.length === 1 ? "" : "s"}
            {results.length - accepted > 0 && (
              <span className="text-red-400">
                {" "}
                · {results.length - accepted} rejected
              </span>
            )}
          </p>
          <ul className="space-y-1.5">
            {results.map((r) => (
              <li
                key={r.filename}
                className="flex items-center justify-between gap-3 text-sm"
              >
                <span className="truncate text-zinc-300">{r.filename}</span>
                {r.invoice_id ? (
                  <Link
                    href={`/invoices/${r.invoice_id}`}
                    className="shrink-0 text-xs text-emerald-400 hover:underline"
                  >
                    view audit trail →
                  </Link>
                ) : (
                  <span
                    className="shrink-0 text-xs text-red-400"
                    title={r.error ?? ""}
                  >
                    {r.error ?? "rejected"}
                  </span>
                )}
              </li>
            ))}
          </ul>
          <button
            onClick={reset}
            className="rounded-lg border border-zinc-700 px-3 py-1.5 text-sm text-zinc-300 hover:bg-zinc-800"
          >
            Upload more
          </button>
        </div>
      )}

      {liveId && (
        <AgentStream
          invoiceId={liveId}
          onComplete={(status) => setFinalStatus(status)}
        />
      )}

      {finalStatus && liveId && (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4">
          <p className="text-sm text-emerald-300">
            Pipeline finished with status{" "}
            <span className="font-semibold">{finalStatus}</span>.
          </p>
          <Link
            href={`/invoices/${liveId}`}
            className="mt-3 inline-block rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-zinc-950 transition-colors hover:bg-emerald-400"
          >
            View audit trail →
          </Link>
        </div>
      )}
    </div>
  );
}
