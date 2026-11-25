const STATIONS = [
  { key: "intake", x: 16, label: "INTAKE", tone: "ink" },
  { key: "extract", x: 176, label: "EXTRACT", tone: "ink" },
  { key: "validate", x: 336, label: "VALIDATE", tone: "ink" },
  { key: "route", x: 496, label: "ROUTE", tone: "ink" },
  { key: "settle", x: 660, label: "SETTLE", tone: "settled" },
] as const;

/**
 * The route: one line, bends only at 90°, and an interchange exactly where a
 * human takes over. Counts are invoices reaching each stage.
 */
export default function PipelineRoute({
  received,
  settled,
  held,
  voided,
}: {
  received: number;
  settled: number;
  held: number;
  voided: number;
}) {
  const counts: Record<string, number> = {
    intake: received,
    extract: received,
    validate: Math.max(0, received - voided),
    route: received,
    settle: settled,
  };

  return (
    <div className="w-full">
      <svg
        viewBox="0 0 760 66"
        role="img"
        aria-label={`Route: ${received} received, ${held} held for human review, ${settled} settled, ${voided} void`}
        className="hidden h-[66px] w-full max-w-[760px] md:block"
      >
        {/* main line */}
        <path d="M16 44 H660" stroke="#b3b7a8" strokeWidth="1" fill="none" />
        {/* 90° spur to the human interchange */}
        <path
          d="M496 44 V58 H596"
          stroke="#b3b7a8"
          strokeWidth="1"
          fill="none"
        />

        {STATIONS.map((s) => (
          <g key={s.key}>
            <rect
              x={s.x - 3.5}
              y={40.5}
              width="7"
              height="7"
              fill={s.tone === "settled" ? "#2a6350" : "#fbfbf5"}
              stroke={s.tone === "settled" ? "#2a6350" : "#0f1e1b"}
              strokeWidth="1.25"
            />
            <text
              x={s.x + 9}
              y={17}
              fontSize="9"
              letterSpacing="0.12em"
              fill="#46554f"
              className="num"
            >
              {s.label}
            </text>
            <text
              x={s.x + 9}
              y={34}
              fontSize="13"
              fill={s.tone === "settled" ? "#2a6350" : "#0f1e1b"}
              className="num"
            >
              {counts[s.key]}
            </text>
          </g>
        ))}

        {/* human interchange sits on the spur, off the main line */}
        <g>
          <rect
            x="592.5"
            y="54.5"
            width="7"
            height="7"
            fill={held > 0 ? "#8a5b10" : "#fbfbf5"}
            stroke="#8a5b10"
            strokeWidth="1.25"
          />
          <text
            x="605"
            y="61"
            fontSize="9"
            letterSpacing="0.12em"
            fill="#8a5b10"
            className="num"
          >
            HUMAN {held}
          </text>
        </g>
      </svg>

      {/* Small screens: the same route as a plain ruled row. */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 md:hidden">
        {STATIONS.map((s) => (
          <span key={s.key} className="flex items-baseline gap-1.5">
            <span className="micro">{s.label}</span>
            <span className="num text-[12px]">{counts[s.key]}</span>
          </span>
        ))}
        <span className="flex items-baseline gap-1.5">
          <span className="micro !text-hold">HUMAN</span>
          <span className="num text-[12px] text-hold">{held}</span>
        </span>
      </div>
    </div>
  );
}
