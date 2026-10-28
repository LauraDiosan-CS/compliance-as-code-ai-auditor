import { scoreColor } from "@/lib/meta";

/** 240-degree arc gauge for the overall score (0..100). */
export function ScoreGauge({ score, size = 168, label = "Overall score" }: { score: number; size?: number; label?: string }) {
  const s = Math.max(0, Math.min(100, score));
  const r = 42;
  const c = 2 * Math.PI * r;
  const arc = c * (240 / 360);
  const filled = arc * (s / 100);
  return (
    <figure className="relative shrink-0" style={{ width: size, height: size * 0.86 }} aria-label={`${label}: ${s.toFixed(1)} out of 100`} role="img">
      <svg viewBox="0 0 100 86" className="size-full -rotate-0">
        <g transform="rotate(150 50 50)">
          <circle cx="50" cy="50" r={r} fill="none" stroke="var(--muted)" strokeWidth="8" strokeDasharray={`${arc} ${c}`} strokeLinecap="round" />
          <circle
            cx="50"
            cy="50"
            r={r}
            fill="none"
            stroke={scoreColor(s)}
            strokeWidth="8"
            strokeDasharray={`${filled} ${c}`}
            strokeLinecap="round"
            style={{ transition: "stroke-dasharray 600ms ease" }}
          />
        </g>
        {[0, 50, 80].map((t) => {
          const a = ((150 + (t / 100) * 240) * Math.PI) / 180;
          return (
            <line
              key={t}
              x1={50 + Math.cos(a) * 34}
              y1={50 + Math.sin(a) * 34}
              x2={50 + Math.cos(a) * 31}
              y2={50 + Math.sin(a) * 31}
              stroke="var(--muted-foreground)"
              strokeOpacity=".5"
              strokeWidth="0.8"
            />
          );
        })}
      </svg>
      <figcaption className="absolute inset-x-0 top-[36%] flex flex-col items-center">
        <span className="tabular font-heading text-4xl leading-none font-semibold tracking-tight">
          {s.toFixed(s % 1 === 0 ? 0 : 1)}
        </span>
        <span className="mt-1 text-[11px] tracking-wider text-muted-foreground uppercase">{label}</span>
      </figcaption>
    </figure>
  );
}
