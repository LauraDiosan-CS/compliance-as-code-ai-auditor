"use client";

import { useCallback, useMemo, useSyncExternalStore } from "react";
import type { AuditReport, ReviewDecision, StoredReview } from "./types";

// Tiny localStorage-backed store using useSyncExternalStore (SSR-safe, cross-tab).

const EVENT = "ccauditor:storage";
const UPLOADS_KEY = "ccauditor:uploads:v1";
const reviewsKey = (reportId: string) => `ccauditor:reviews:v1:${reportId}`;

function read(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string | null) {
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch (e) {
    throw new Error(
      e instanceof DOMException && e.name === "QuotaExceededError"
        ? "Browser storage is full. Remove some uploaded reports and try again."
        : "Browser storage is unavailable.",
    );
  }
  window.dispatchEvent(new CustomEvent(EVENT, { detail: key }));
}

function subscribe(cb: () => void) {
  window.addEventListener("storage", cb);
  window.addEventListener(EVENT, cb);
  return () => {
    window.removeEventListener("storage", cb);
    window.removeEventListener(EVENT, cb);
  };
}

function parse<T>(raw: string | null, fallback: T): T {
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

/** Returns [raw string | null, hydrated]. `hydrated` is false during SSR / first render. */
function useLocalRaw(key: string): [string | null, boolean] {
  const raw = useSyncExternalStore(
    subscribe,
    () => read(key),
    () => null,
  );
  const hydrated = useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );
  return [raw, hydrated];
}

// ---------------------------------------------------------------- uploaded reports

export function getUploadedReports(): Record<string, AuditReport> {
  return parse<Record<string, AuditReport>>(read(UPLOADS_KEY), {});
}

export function saveUploadedReport(report: AuditReport) {
  const all = getUploadedReports();
  all[report.id] = report;
  write(UPLOADS_KEY, JSON.stringify(all));
}

export function deleteUploadedReport(id: string) {
  const all = getUploadedReports();
  delete all[id];
  write(UPLOADS_KEY, JSON.stringify(all));
}

export function useUploadedReports(): { uploads: Record<string, AuditReport>; hydrated: boolean } {
  const [raw, hydrated] = useLocalRaw(UPLOADS_KEY);
  const uploads = useMemo(() => parse<Record<string, AuditReport>>(raw, {}), [raw]);
  return { uploads, hydrated };
}

// ---------------------------------------------------------------- reviews

export function useReviews(reportId: string) {
  const key = reviewsKey(reportId);
  const [raw, hydrated] = useLocalRaw(key);
  const reviews = useMemo(() => parse<Record<string, StoredReview>>(raw, {}), [raw]);

  const saveReview = useCallback(
    (review: StoredReview) => {
      const all = parse<Record<string, StoredReview>>(read(key), {});
      all[review.requirement_id] = review;
      write(key, JSON.stringify(all));
    },
    [key],
  );

  const removeReview = useCallback(
    (requirementId: string) => {
      const all = parse<Record<string, StoredReview>>(read(key), {});
      delete all[requirementId];
      write(key, Object.keys(all).length ? JSON.stringify(all) : null);
    },
    [key],
  );

  const clearReviews = useCallback(() => write(key, null), [key]);

  return { reviews, hydrated, saveReview, removeReview, clearReviews };
}

/** Export format consumed by `ccauditor review apply`. */
export function toReviewExport(reviews: Record<string, StoredReview>): ReviewDecision[] {
  return Object.values(reviews)
    .sort((a, b) => a.requirement_id.localeCompare(b.requirement_id))
    .map(({ requirement_id, status, reviewer, justification, reviewed_at }) => ({
      requirement_id,
      status,
      reviewer,
      justification,
      reviewed_at,
    }));
}

export function downloadJson(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2) + "\n"], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
