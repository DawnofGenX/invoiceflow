import type { Metadata } from "next";
import { Suspense } from "react";
import { Archivo, Sometype_Mono } from "next/font/google";
import Navbar from "@/components/Navbar";
import "./globals.css";

const archivo = Archivo({
  variable: "--font-archivo",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

const sometype = Sometype_Mono({
  variable: "--font-sometype",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "InvoiceFlow — Confirmation register for accounts payable",
  description:
    "Open-source, explainable multi-agent accounts payable. Every decision is printed on the record: reasoning, confidence, and the exact rule that fired.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${archivo.variable} ${sometype.variable}`}>
      <body className="flex min-h-dvh flex-col bg-print text-ink antialiased">
        <Suspense
          fallback={<div className="h-[52px] border-b border-ink bg-ink" />}
        >
          <Navbar />
        </Suspense>
        <main className="flex-1">{children}</main>
        <footer className="border-t border-rule px-5 py-3 text-[11px] text-ink-mute sm:px-8">
          <div className="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-2">
            <span>
              InvoiceFlow — open-source explainable accounts payable · MIT
              licensed
            </span>
            <span className="num">every decision printed, nothing inferred</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
