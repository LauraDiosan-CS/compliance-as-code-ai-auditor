import type { Metadata } from "next";
import { AuditForm } from "@/components/audit-form";

export const metadata: Metadata = { title: "Run audit" };

export default function AuditPage() {
  return (
    <div className="mx-auto max-w-5xl space-y-8 px-4 py-8 sm:px-6 sm:py-10">
      <header className="max-w-3xl space-y-2">
        <p className="font-mono text-xs tracking-wider text-muted-foreground uppercase">New audit</p>
        <h1 className="font-heading text-3xl font-semibold tracking-tight">Run an audit</h1>
        <p className="text-muted-foreground">
          Point the auditor at a repository, pick the policies to check against and choose how verdicts are produced.
        </p>
      </header>
      <AuditForm apiUrl={process.env.NEXT_PUBLIC_API_URL ?? ""} />
    </div>
  );
}
