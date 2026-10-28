import { Loader2Icon } from "lucide-react";
import type { Metadata } from "next";
import { Suspense } from "react";
import { ReportView } from "@/components/report/report-view";

export const metadata: Metadata = { title: "Report" };

// Reports are resolved client-side (static library JSON or browser uploads), so the
// dynamic segment is read inside a Suspense boundary and the shell stays static.
export default function ReportPage(props: PageProps<"/reports/[id]">) {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center gap-2 py-32 text-muted-foreground" role="status">
          <Loader2Icon className="size-4 animate-spin" aria-hidden /> Loading report...
        </div>
      }
    >
      <ReportFromParams params={props.params} />
    </Suspense>
  );
}

async function ReportFromParams({ params }: { params: PageProps<"/reports/[id]">["params"] }) {
  const { id } = await params;
  return <ReportView id={decodeURIComponent(id)} />;
}
