export default function StatCard({
  label,
  value,
  hint,
  tone = "zinc",
}: {
  label: string;
  value: string | number;
  hint?: string;
  tone?: "emerald" | "amber" | "orange" | "blue" | "zinc";
}) {
  const tones: Record<string, string> = {
    emerald: "text-emerald-400",
    amber: "text-amber-400",
    orange: "text-orange-400",
    blue: "text-blue-400",
    zinc: "text-zinc-100",
  };
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
      <p className="text-xs font-medium uppercase tracking-wider text-zinc-500">
        {label}
      </p>
      <p className={`mt-2 text-2xl font-semibold tracking-tight ${tones[tone]}`}>
        {value}
      </p>
      {hint && <p className="mt-1 text-xs text-zinc-500">{hint}</p>}
    </div>
  );
}
