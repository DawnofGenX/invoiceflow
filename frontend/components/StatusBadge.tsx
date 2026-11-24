import { statusLabel, statusTone } from "@/lib/format";

const tones: Record<string, string> = {
  emerald: "bg-emerald-500/10 text-emerald-400 ring-emerald-500/30",
  amber: "bg-amber-500/10 text-amber-400 ring-amber-500/30",
  orange: "bg-orange-500/10 text-orange-400 ring-orange-500/30",
  red: "bg-red-500/10 text-red-400 ring-red-500/30",
  blue: "bg-blue-500/10 text-blue-400 ring-blue-500/30",
  zinc: "bg-zinc-500/10 text-zinc-400 ring-zinc-500/30",
};

const dots: Record<string, string> = {
  emerald: "bg-emerald-400",
  amber: "bg-amber-400",
  orange: "bg-orange-400",
  red: "bg-red-400",
  blue: "bg-blue-400",
  zinc: "bg-zinc-400",
};

export default function StatusBadge({ status }: { status: string }) {
  const tone = statusTone(status);
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ring-1 ring-inset ${tones[tone]}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${dots[tone]} ${status === "extracting" || status === "validating" ? "animate-pulse" : ""}`} />
      {statusLabel(status)}
    </span>
  );
}
