"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const links = [
  { href: "/", label: "Register" },
  { href: "/upload", label: "Intake" },
  { href: "/approvals", label: "Held" },
  { href: "/audit", label: "Evidence" },
];

function Mark() {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.25}
      aria-hidden="true"
      className="h-5 w-5 shrink-0"
    >
      <rect x="3" y="2" width="14" height="16" rx="1.5" />
      <path d="M6.5 6.5h7M6.5 9.75h7M6.5 13h4" strokeLinecap="square" />
      <circle cx="14.5" cy="15" r="1.1" />
    </svg>
  );
}

export default function Navbar() {
  const pathname = usePathname();
  const [held, setHeld] = useState<number | null>(null);

  useEffect(() => {
    let live = true;
    function read() {
      api
        .dashboard()
        .then((d) => {
          if (live) setHeld(d.pending_approvals);
        })
        .catch(() => {
          if (live) setHeld(null);
        });
    }
    read();
    // A decision made elsewhere in the app should move this count immediately.
    window.addEventListener("invoiceflow:changed", read);
    // And the queue stays honest if someone else is working it.
    const timer = window.setInterval(read, 15000);
    return () => {
      live = false;
      window.removeEventListener("invoiceflow:changed", read);
      window.clearInterval(timer);
    };
  }, [pathname]);

  return (
    <header className="sticky top-0 z-40 border-b border-ink-soft bg-ink">
      <div className="mx-auto flex h-[52px] max-w-[1440px] items-center gap-3 px-4 sm:gap-6 sm:px-8">
        <Link href="/" className="flex items-center gap-2.5 text-print">
          <Mark />
          <span className="hidden flex-col leading-none sm:flex">
            <span className="text-[14px] font-semibold tracking-[-0.01em]">
              InvoiceFlow
            </span>
            <span
              className="mt-1 hidden text-[9px] font-medium text-rail-text sm:block"
              style={{ letterSpacing: "0.14em" }}
            >
              CONFIRMATION REGISTER
            </span>
          </span>
        </Link>

        <nav className="flex min-w-0 items-center gap-0.5 sm:gap-1" aria-label="Sections">
          {links.map((l) => {
            const active =
              l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                aria-current={active ? "page" : undefined}
                className={`rounded-[3px] px-2 py-1.5 text-[10px] font-medium uppercase transition-colors duration-150 sm:px-2.5 sm:text-[10.5px] ${
                  active
                    ? "bg-print text-ink"
                    : "text-rail-text hover:bg-ink-soft hover:text-print"
                }`}
                style={{ letterSpacing: "0.12em" }}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>

        <Link
          href="/approvals"
          className="ml-auto flex shrink-0 items-center gap-2 rounded-[3px] px-1.5 py-1.5 text-print transition-colors duration-150 hover:bg-ink-soft sm:px-2"
          title="Invoices held for a human decision"
          aria-label={
            held == null
              ? "Held for review"
              : `${held} invoice${held === 1 ? "" : "s"} held for review`
          }
        >
          <span className="micro !text-rail-text hidden sm:inline">
            held for review
          </span>
          <span className="flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className={`h-2 w-2 ${
                held && held > 0 ? "lamp-live bg-signal" : "border border-rail-text"
              }`}
            />
            <span className="num text-[12px] tabular-nums">
              {held == null ? "—" : String(held).padStart(2, "0")}
            </span>
          </span>
        </Link>
      </div>
    </header>
  );
}
