"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Dashboard" },
  { href: "/upload", label: "Upload" },
  { href: "/approvals", label: "Approvals" },
];

export default function Navbar() {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-40 border-b border-zinc-800/80 bg-zinc-950/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-500/15 text-emerald-400 ring-1 ring-inset ring-emerald-500/30">
            <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
              <path d="M3 4a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4Zm4.5 4a1 1 0 0 0 0 2h5a1 1 0 1 0 0-2h-5Zm0 3.5a1 1 0 1 0 0 2h5a1 1 0 1 0 0-2h-5Z" />
            </svg>
          </span>
          <span className="text-sm font-semibold tracking-tight text-zinc-100">
            Invoice<span className="text-emerald-400">Flow</span>
          </span>
        </Link>
        <nav className="flex items-center gap-1">
          {links.map((l) => {
            const active =
              l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                  active
                    ? "bg-zinc-800 text-zinc-100"
                    : "text-zinc-400 hover:bg-zinc-800/60 hover:text-zinc-200"
                }`}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>
        <span className="hidden items-center gap-1.5 rounded-full bg-zinc-900 px-3 py-1 text-xs text-zinc-400 ring-1 ring-inset ring-zinc-800 sm:flex">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
          explainable multi-agent AP
        </span>
      </div>
    </header>
  );
}
