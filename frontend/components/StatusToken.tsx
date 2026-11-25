import { disposition, type Tone } from "@/lib/format";

const toneClass: Record<Tone, string> = {
  settled: "border-settled/40 bg-settled-soft text-settled",
  hold: "border-hold/40 bg-hold-soft text-hold",
  void: "border-void/40 bg-void-soft text-void",
  live: "border-signal/45 bg-slip text-signal",
  neutral: "border-rule-firm bg-print-2 text-ink-mute",
};

const dotClass: Record<Tone, string> = {
  settled: "bg-settled",
  hold: "bg-hold",
  void: "bg-void",
  live: "bg-signal",
  neutral: "bg-ink-mute",
};

/** A disposition is a stamped token, never a coloured pill. */
export function StatusToken({
  status,
  invert = false,
}: {
  status: string;
  invert?: boolean;
}) {
  const { token, tone } = disposition(status);
  if (invert) {
    return (
      <span className="num inline-flex items-center gap-1.5 rounded-[2px] border border-print/40 px-1.5 py-[2px] text-[10px] uppercase text-print">
        <span aria-hidden="true" className="h-[5px] w-[5px] bg-print" />
        {token}
      </span>
    );
  }
  return (
    <span
      className={`num inline-flex items-center gap-1.5 rounded-[2px] border px-1.5 py-[2px] text-[10px] uppercase ${toneClass[tone]}`}
    >
      <span aria-hidden="true" className={`h-[5px] w-[5px] ${dotClass[tone]}`} />
      {token}
    </span>
  );
}

/** Signal lamp: filled while a record changed and has not been acknowledged. */
export function Lamp({
  live,
  invert = false,
}: {
  live: boolean;
  invert?: boolean;
}) {
  return (
    <span
      aria-hidden="true"
      className={`inline-block h-[6px] w-[6px] ${
        live
          ? "lamp-live bg-signal"
          : invert
            ? "border border-print/40"
            : "border border-rule-firm"
      }`}
    />
  );
}
