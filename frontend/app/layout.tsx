import type { Metadata } from "next";
import { Suspense } from "react";
import { Geist, Geist_Mono } from "next/font/google";
import Navbar from "@/components/Navbar";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "InvoiceFlow — Explainable Multi-Agent AP",
  description:
    "Open-source, explainable multi-agent accounts payable platform. Every agent decision is auditable: reasoning, confidence, and the exact rule that fired.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-zinc-950 text-zinc-100">
        <Suspense fallback={<div className="h-14 border-b border-zinc-800/60" />}>
          <Navbar />
        </Suspense>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6">
          {children}
        </main>
        <footer className="border-t border-zinc-800/60 py-4 text-center text-xs text-zinc-600">
          InvoiceFlow — open-source explainable multi-agent accounts payable ·
          MIT licensed
        </footer>
      </body>
    </html>
  );
}
