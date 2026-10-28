import type { Metadata } from "next";
import { PolicyBrowser } from "@/components/policy-browser";

export const metadata: Metadata = { title: "Policies" };

export default function PoliciesPage() {
  return (
    <div className="mx-auto max-w-7xl space-y-8 px-4 py-8 sm:px-6 sm:py-10">
      <header className="max-w-3xl space-y-2">
        <p className="font-mono text-xs tracking-wider text-muted-foreground uppercase">Policy corpus</p>
        <h1 className="font-heading text-3xl font-semibold tracking-tight">Policies and requirements</h1>
        <p className="text-muted-foreground">
          Each policy is split into citable clauses, which the PolicyAnalyst turns into verifiable requirements with
          deterministic checks and LLM guidance.
        </p>
      </header>
      <PolicyBrowser />
    </div>
  );
}
