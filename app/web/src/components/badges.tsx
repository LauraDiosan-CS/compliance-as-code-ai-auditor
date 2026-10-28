import { BotIcon, CogIcon, LayersIcon, ShieldCheckIcon, ShieldQuestionIcon, UserCheckIcon } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { METHOD_META, RISK_META, SEVERITY_META, STATUS_META } from "@/lib/meta";
import type { RiskLevel, Severity, Status, VerdictMethod } from "@/lib/types";
import { cn } from "@/lib/utils";

export function StatusBadge({ status, className }: { status: Status | undefined; className?: string }) {
  if (!status) {
    return (
      <span className={cn("inline-flex items-center rounded-md px-2 py-0.5 text-xs text-muted-foreground ring-1 ring-border ring-inset", className)}>
        No verdict
      </span>
    );
  }
  const m = STATUS_META[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium whitespace-nowrap ring-1 ring-inset",
        m.badge,
        className,
      )}
    >
      <span aria-hidden className={cn("size-1.5 rounded-full", m.dot)} />
      {m.label}
    </span>
  );
}

export function RiskBadge({ level, className }: { level: RiskLevel; className?: string }) {
  const m = RISK_META[level] ?? RISK_META.unknown;
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2.5 py-1 font-mono text-xs font-semibold tracking-wide uppercase",
        m.badge,
        className,
      )}
    >
      {m.label}
    </span>
  );
}

export function SeverityLabel({ severity }: { severity: Severity }) {
  const m = SEVERITY_META[severity] ?? SEVERITY_META.medium;
  const bars = m.weight;
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-xs", m.cls)}>
      <span aria-hidden className="flex items-end gap-px">
        {[1, 2, 3, 4].map((i) => (
          <span
            key={i}
            className={cn("w-[3px] rounded-[1px]", i <= bars ? "bg-current" : "bg-current opacity-15")}
            style={{ height: 3 + i * 2 }}
          />
        ))}
      </span>
      {m.label}
    </span>
  );
}

const METHOD_ICON: Record<VerdictMethod, typeof CogIcon> = {
  deterministic: CogIcon,
  llm: BotIcon,
  hybrid: LayersIcon,
  human: UserCheckIcon,
};

export function MethodTag({ method }: { method: VerdictMethod }) {
  const m = METHOD_META[method] ?? METHOD_META.deterministic;
  const Icon = METHOD_ICON[method] ?? CogIcon;
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <span
            className={cn(
              "inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground ring-1 ring-border ring-inset",
              method === "human" && "bg-accent text-accent-foreground ring-primary/30",
            )}
          />
        }
      >
        <Icon className="size-3" aria-hidden />
        {m.label}
      </TooltipTrigger>
      <TooltipContent>{m.hint}</TooltipContent>
    </Tooltip>
  );
}

export function VerifiedTag({ verified, resolved, total }: { verified: boolean; resolved: number; total: number }) {
  const ok = verified && resolved === total;
  const Icon = ok ? ShieldCheckIcon : ShieldQuestionIcon;
  const text = total === 0 ? (verified ? "Verified (no citations)" : "Unverified") : ok ? `Citations verified ${resolved}/${total}` : `Unverified ${resolved}/${total} resolved`;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 text-xs",
        ok ? "text-emerald-700 dark:text-emerald-400" : "text-amber-700 dark:text-amber-400",
      )}
    >
      <Icon className="size-3.5" aria-hidden />
      {text}
    </span>
  );
}
