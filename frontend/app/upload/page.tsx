"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { api, type BatchUploadResult } from "@/lib/api";
import AgentStream from "@/components/AgentStream";
import { StatusToken } from "@/components/StatusToken";

function RemoveIcon() {
  return (
    <svg
      viewBox="0 0 12 12"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.25}
      aria-hidden="true"
      className="h-3 w-3"
    >
      <path d="M2.5 2.5l7 7M9.5 2.5l-7 7" strokeLinecap="square" />
    </svg>
  );
}

function TrayIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.25}
      aria-hidden="true"
      className="h-6 w-6 text-ink-mute"
    >
      <path d="M12 4v9m0 0 3.25-3.25M12 13 8.75 9.75" strokeLinecap="square" />
      <path d="M4 15v3.5h16V15" strokeLinecap="square" />
    </svg>
  );
}

export default function IntakePage() {
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
    <div className="mx-auto max-w-[880px] px-5 py-8 sm:px-8">
      <h1 className="text-[26px] font-semibold leading-tight tracking-[-0.02em]">
        Intake
      </h1>
      <p className="mt-1 max-w-[64ch] text-[13px] text-ink-mute">
        Send invoices in and watch the record build itself. Each file is read,
        matched against purchase orders and prior payments, and routed — with one
        printed line per decision.
      </p>

      <div className="mt-6 grid gap-5 lg:grid-cols-[minmax(0,1fr)_260px]">
        <div>
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
            className={`flex cursor-pointer flex-col items-center justify-center border bg-slip px-6 py-10 text-center transition-colors duration-150 ${
              dragOver
                ? "border-ink bg-print-2"
                : "border-field hover:border-ink hover:bg-print-2/60"
            }`}
          >
            <TrayIcon />
            <p className="micro mt-3 !text-ink">
              Drop files, or browse the register
            </p>
            <p className="mt-1.5 text-[11.5px] text-ink-mute">
              PDF, PNG or JPG — one file or many at once
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
            <div className="mt-4 border border-rule-firm bg-slip">
              <div className="flex items-baseline justify-between border-b border-rule px-3 py-1.5">
                <span className="micro">Staged</span>
                <span className="num text-[10.5px] text-ink-mute">
                  {files.length} file{files.length === 1 ? "" : "s"}
                </span>
              </div>
              <ul>
                {files.map((f) => (
                  <li
                    key={`${f.name}:${f.size}`}
                    className="flex items-center gap-3 border-b border-rule px-3 py-1.5 last:border-0"
                  >
                    <span className="num w-6 shrink-0 text-[10px] text-ink-mute">
                      {f.name.split(".").pop()?.toUpperCase().slice(0, 4) ?? "DOC"}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-[12px] text-ink">
                      {f.name}
                    </span>
                    <span className="num shrink-0 text-[10.5px] text-ink-mute">
                      {(f.size / 1024).toFixed(0)} KB
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setFiles((prev) => prev.filter((x) => x !== f));
                      }}
                      className="shrink-0 border border-field p-1 text-ink-mute transition-colors duration-150 hover:border-ink hover:text-ink"
                      aria-label={`Remove ${f.name}`}
                    >
                      <RemoveIcon />
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {error && (
            <div className="mt-4 border border-void/40 bg-void-soft px-4 py-3">
              <p className="num text-[11.5px] text-void">{error}</p>
            </div>
          )}

          {!results && (
            <button
              onClick={handleUpload}
              disabled={files.length === 0 || uploading}
              className="mt-4 w-full rounded-[3px] bg-ink px-4 py-2.5 text-[10.5px] font-medium uppercase tracking-[0.12em] text-print transition-colors duration-150 hover:bg-ink-soft disabled:cursor-not-allowed disabled:opacity-35"
            >
              {uploading
                ? "Reading the documents…"
                : `Process ${files.length || ""} invoice${files.length === 1 ? "" : "s"}`}
            </button>
          )}

          {results && (
            <div className="mt-4 border border-rule-firm bg-slip">
              <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-ink px-4 py-2.5">
                <span className="micro !text-ink">
                  Accepted <span className="num">{accepted}</span> of{" "}
                  <span className="num">{results.length}</span>
                </span>
                <button
                  onClick={reset}
                  className="text-[10.5px] font-medium uppercase tracking-[0.08em] text-ink underline decoration-rule-firm underline-offset-4 hover:decoration-ink"
                >
                  Intake more
                </button>
              </div>
              <ul>
                {results.map((r) => (
                  <li
                    key={r.filename}
                    className="flex flex-wrap items-center gap-3 border-b border-rule px-4 py-2 last:border-0"
                  >
                    <span className="min-w-0 flex-1 truncate text-[12px] text-ink">
                      {r.filename}
                    </span>
                    {r.invoice_id ? (
                      <>
                        <StatusToken
                          status={
                            r.invoice_id === liveId && finalStatus
                              ? finalStatus
                              : r.status
                          }
                        />
                        <Link
                          href={`/invoices/${r.invoice_id}`}
                          className="num text-[10.5px] text-ink underline decoration-rule-firm underline-offset-4 hover:decoration-ink"
                        >
                          open record
                        </Link>
                      </>
                    ) : (
                      <span
                        className="num text-[10.5px] text-void"
                        title={r.error ?? ""}
                      >
                        {r.error ?? "void — unreadable"}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {liveId && (
            <div className="mt-5">
              <AgentStream
                invoiceId={liveId}
                onComplete={(status) => setFinalStatus(status)}
              />
            </div>
          )}

          {finalStatus && liveId && (
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border border-rule-firm bg-slip px-4 py-3">
              <span className="flex items-center gap-2">
                <span className="micro !text-ink">Routed</span>
                <StatusToken status={finalStatus} />
              </span>
              <Link
                href={`/invoices/${liveId}`}
                className="text-[10.5px] font-medium uppercase tracking-[0.08em] text-ink underline decoration-rule-firm underline-offset-4 hover:decoration-ink"
              >
                Read the full record
              </Link>
            </div>
          )}
        </div>

        <aside className="border border-rule bg-print-2/50 px-4 py-3">
          <p className="micro">What happens next</p>
          <ol className="mt-2 space-y-2 text-[11.5px] leading-[1.5] text-ink-mute">
            <li>
              <span className="num text-ink">01</span> Intake reads the document
              type. Non-invoices are voided here.
            </li>
            <li>
              <span className="num text-ink">02</span> Extraction pulls vendor,
              amount, PO and line items.
            </li>
            <li>
              <span className="num text-ink">03</span> Five validation rules run
              in order: PO match, line items, duplicates, amount, anomalies.
            </li>
            <li>
              <span className="num text-ink">04</span> Routing stamps a
              disposition. Under $500 settles automatically; a new vendor never
              does.
            </li>
          </ol>
        </aside>
      </div>
    </div>
  );
}
