"use client";

import { RotateCcwIcon, UserCheckIcon } from "lucide-react";
import { useState } from "react";
import { StatusBadge } from "@/components/badges";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { STATUS_META, fmtDate } from "@/lib/meta";
import type { Row } from "@/lib/report-model";
import type { Status, StoredReview } from "@/lib/types";
import { STATUSES } from "@/lib/types";
import { cn } from "@/lib/utils";

const REVIEWER_KEY = "ccauditor:reviewer";
const MIN_JUSTIFICATION = 15;

function lastReviewer(): string {
  try {
    return localStorage.getItem(REVIEWER_KEY) ?? "";
  } catch {
    return "";
  }
}

export function ReviewPanel({
  row,
  onSave,
  onRemove,
}: {
  row: Row;
  onSave: (r: StoredReview) => void;
  onRemove: (id: string) => void;
}) {
  const original = row.original?.status ?? "needs_review";
  const existing = row.review;

  if (existing) {
    return (
      <div className="rounded-lg border border-primary/30 bg-accent/40 p-4">
        <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
          <UserCheckIcon className="size-4 text-primary" aria-hidden />
          <span className="font-medium">{existing.action === "accept" ? "Verdict accepted" : "Verdict overridden"}</span>
          {existing.action === "override" && (
            <>
              <StatusBadge status={existing.original_status} className="opacity-60 line-through" />
              <span aria-hidden>→</span>
            </>
          )}
          <StatusBadge status={existing.status} />
        </div>
        <blockquote className="border-l-2 border-primary/40 pl-3 text-sm text-pretty">{existing.justification}</blockquote>
        <p className="mt-2 text-xs text-muted-foreground">
          {existing.reviewer} · {fmtDate(existing.reviewed_at)}
        </p>
        <Button variant="outline" size="sm" className="mt-3" onClick={() => onRemove(row.req.id)}>
          <RotateCcwIcon /> Withdraw review
        </Button>
      </div>
    );
  }

  return <ReviewForm key={row.req.id} reqId={row.req.id} original={original} onSave={onSave} />;
}

function ReviewForm({ reqId, original, onSave }: { reqId: string; original: Status; onSave: (r: StoredReview) => void }) {
  const mustOverride = original === "needs_review";
  const [action, setAction] = useState<"accept" | "override">(mustOverride ? "override" : "accept");
  const [status, setStatus] = useState<Status | "">("");
  const [reviewer, setReviewer] = useState(lastReviewer);
  const [justification, setJustification] = useState("");
  const [touched, setTouched] = useState(false);

  const finalStatus: Status | "" = action === "accept" ? original : status;
  const errors = {
    status: action === "override" && (!status || status === original) ? "Choose a status different from the current verdict." : "",
    reviewer: reviewer.trim() ? "" : "Reviewer name is required.",
    justification:
      justification.trim().length >= MIN_JUSTIFICATION ? "" : `Justification is required (at least ${MIN_JUSTIFICATION} characters).`,
  };
  const valid = !errors.status && !errors.reviewer && !errors.justification;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (!valid || !finalStatus) return;
    try {
      localStorage.setItem(REVIEWER_KEY, reviewer.trim());
    } catch {}
    onSave({
      requirement_id: reqId,
      status: finalStatus,
      reviewer: reviewer.trim(),
      justification: justification.trim(),
      reviewed_at: new Date().toISOString(),
      action,
      original_status: original,
    });
  }

  const err = (k: keyof typeof errors) =>
    touched && errors[k] ? (
      <p id={`err-${k}`} className="text-xs text-red-600 dark:text-red-400">
        {errors[k]}
      </p>
    ) : null;

  return (
    <form onSubmit={submit} noValidate className="space-y-4 rounded-lg border bg-muted/30 p-4">
      <fieldset className="space-y-2">
        <legend className="mb-2 text-sm font-medium">Decision</legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {(["accept", "override"] as const).map((a) => {
            const disabled = a === "accept" && mustOverride;
            return (
              <label
                key={a}
                className={cn(
                  "flex cursor-pointer items-start gap-2 rounded-md border bg-background p-2.5 text-sm has-checked:border-primary has-checked:ring-1 has-checked:ring-primary/40",
                  disabled && "cursor-not-allowed opacity-50",
                )}
              >
                <input
                  type="radio"
                  name={`action-${reqId}`}
                  value={a}
                  checked={action === a}
                  disabled={disabled}
                  onChange={() => setAction(a)}
                  className="mt-0.5 accent-[var(--primary)]"
                />
                <span>
                  <span className="font-medium">{a === "accept" ? "Accept verdict" : "Override status"}</span>
                  <span className="block text-xs text-muted-foreground">
                    {a === "accept"
                      ? disabled
                        ? "Not possible for needs-review items"
                        : `Confirm "${STATUS_META[original].label}"`
                      : "Set the final status manually"}
                  </span>
                </span>
              </label>
            );
          })}
        </div>
      </fieldset>

      {action === "override" && (
        <fieldset className="space-y-2">
          <legend className="mb-2 text-sm font-medium">Final status</legend>
          <div className="flex flex-wrap gap-2">
            {STATUSES.filter((s) => s !== original).map((s) => (
              <label key={s} className="cursor-pointer">
                <input
                  type="radio"
                  name={`status-${reqId}`}
                  value={s}
                  checked={status === s}
                  onChange={() => setStatus(s)}
                  className="peer sr-only"
                  aria-describedby={errors.status ? "err-status" : undefined}
                />
                <span className="inline-flex rounded-md ring-offset-2 ring-offset-background peer-checked:ring-2 peer-checked:ring-primary peer-focus-visible:ring-2 peer-focus-visible:ring-ring">
                  <StatusBadge status={s} className="px-2.5 py-1" />
                </span>
              </label>
            ))}
          </div>
          {err("status")}
        </fieldset>
      )}

      <div className="space-y-1.5">
        <label htmlFor={`reviewer-${reqId}`} className="text-sm font-medium">
          Reviewer
        </label>
        <Input
          id={`reviewer-${reqId}`}
          value={reviewer}
          onChange={(e) => setReviewer(e.target.value)}
          placeholder="Full name"
          autoComplete="name"
          aria-invalid={touched && !!errors.reviewer}
        />
        {err("reviewer")}
      </div>

      <div className="space-y-1.5">
        <label htmlFor={`just-${reqId}`} className="text-sm font-medium">
          Justification
        </label>
        <Textarea
          id={`just-${reqId}`}
          value={justification}
          onChange={(e) => setJustification(e.target.value)}
          rows={3}
          placeholder="Why is this the correct status? Reference evidence, documents or interviews."
          aria-invalid={touched && !!errors.justification}
        />
        <div className="flex justify-between gap-2">
          {err("justification") ?? <span />}
          <span className="tabular text-xs text-muted-foreground">{justification.trim().length} chars</span>
        </div>
      </div>

      <Button type="submit" className="w-full sm:w-auto">
        <UserCheckIcon /> Record review
      </Button>
    </form>
  );
}
