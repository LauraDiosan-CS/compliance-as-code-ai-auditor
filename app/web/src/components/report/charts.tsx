"use client";

import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CATEGORY_LABEL, STATUS_META, label, scoreColor } from "@/lib/meta";
import { applicableCount } from "@/lib/scoring";
import type { CategoryScore, Status } from "@/lib/types";
import { STATUSES } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Row {
  name: string;
  score: number;
  applicable: number;
  c: CategoryScore;
}

function ChartTooltip({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  if (!active || !payload?.length) return null;
  const { c, applicable, name } = payload[0].payload;
  return (
    <div className="rounded-md border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md">
      <div className="mb-1 font-medium">{name}</div>
      <div className="tabular mb-1.5 text-muted-foreground">
        {applicable ? `${c.score.toFixed(1)} / 100` : "No applicable requirements"} · {c.total} total
      </div>
      {(["compliant", "partial", "non_compliant", "needs_review"] as const).map((s) => (
        <div key={s} className="flex items-center gap-2">
          <span className={cn("size-2 rounded-full", STATUS_META[s].dot)} />
          <span className="flex-1">{STATUS_META[s].label}</span>
          <span className="tabular">{c[s]}</span>
        </div>
      ))}
    </div>
  );
}

export function CategoryChart({ scorecard }: { scorecard: CategoryScore[] }) {
  const rows: Row[] = [...scorecard]
    .map((c) => ({ name: label(CATEGORY_LABEL, c.category), score: c.score, applicable: applicableCount(c), c }))
    .sort((a, b) => a.score - b.score);
  const height = Math.max(180, rows.length * 36 + 24);

  return (
    <div style={{ height }} className="w-full text-xs">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 44, bottom: 4, left: 4 }} barCategoryGap={8}>
          <XAxis type="number" domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis type="category" dataKey="name" width={148} tick={{ fill: "var(--foreground)", fontSize: 12 }} axisLine={false} tickLine={false} />
          <Tooltip cursor={{ fill: "var(--muted)", opacity: 0.6 }} content={<ChartTooltip />} />
          <Bar dataKey="score" minPointSize={3} radius={[0, 4, 4, 0]} background={{ fill: "var(--muted)", radius: 4 }} isAnimationActive={false}>
            {rows.map((r) => (
              <Cell key={r.name} fill={r.applicable ? scoreColor(r.score) : "#a1a1aa"} />
            ))}
            <LabelList
              dataKey="score"
              position="right"
              content={(props) => {
                const { x = 0, y = 0, width = 0, height: h = 0, value } = props as {
                  x?: number | string; y?: number | string; width?: number | string; height?: number | string; value?: number | string;
                };
                return (
                  <text x={Number(x) + Number(width) + 6} y={Number(y) + Number(h) / 2} dy={4} fontSize={12} fill="var(--foreground)" className="tabular">
                    {Math.round(Number(value ?? 0))}
                  </text>
                );
              }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function StatusDistribution({
  counts,
  onSelect,
}: {
  counts: Record<Status, number>;
  onSelect?: (s: Status) => void;
}) {
  const total = STATUSES.reduce((n, s) => n + counts[s], 0) || 1;
  return (
    <div className="space-y-4">
      <div className="flex h-3 w-full overflow-hidden rounded-full bg-muted" role="img" aria-label="Status distribution">
        {STATUSES.filter((s) => counts[s] > 0).map((s) => (
          <div key={s} style={{ width: `${(counts[s] / total) * 100}%`, background: STATUS_META[s].color }} title={`${STATUS_META[s].label}: ${counts[s]}`} />
        ))}
      </div>
      <ul className="grid grid-cols-2 gap-x-6 gap-y-1 sm:grid-cols-1">
        {STATUSES.map((s) => (
          <li key={s}>
            <button
              type="button"
              onClick={() => onSelect?.(s)}
              disabled={!onSelect || counts[s] === 0}
              className="group flex w-full items-center gap-2 rounded-md px-1.5 py-1 text-left text-sm enabled:hover:bg-muted disabled:opacity-60"
            >
              <span className={cn("size-2.5 rounded-sm", STATUS_META[s].dot)} aria-hidden />
              <span className="flex-1">{STATUS_META[s].label}</span>
              <span className="tabular font-mono text-muted-foreground">{counts[s]}</span>
              <span className="tabular hidden w-10 text-right font-mono text-xs text-muted-foreground sm:inline">
                {Math.round((counts[s] / total) * 100)}%
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
