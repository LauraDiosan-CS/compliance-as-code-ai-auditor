"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "./theme-toggle";

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/reports", label: "Reports" },
  { href: "/audit", label: "Run audit" },
  { href: "/policies", label: "Policies" },
];

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b bg-background/85 backdrop-blur supports-backdrop-filter:bg-background/70">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-4 px-4 sm:px-6">
        <Link href="/" className="flex shrink-0 items-center gap-2.5" aria-label="CCAuditor home">
          <Seal />
          <span className="hidden flex-col leading-none min-[420px]:flex">
            <span className="font-heading text-[17px] font-semibold tracking-tight">CCAuditor</span>
            <span className="hidden font-mono text-[10px] tracking-wider text-muted-foreground uppercase sm:block">
              compliance-as-code
            </span>
          </span>
        </Link>
        <Suspense fallback={<NavLinks pathname={null} />}>
          <ActiveNav />
        </Suspense>
        <div className="sm:ml-auto">
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}

function ActiveNav() {
  return <NavLinks pathname={usePathname()} />;
}

function NavLinks({ pathname }: { pathname: string | null }) {
  return (
    <nav aria-label="Main" className="ml-auto flex min-w-0 items-center gap-0.5 overflow-x-auto sm:ml-6">
      {NAV.map((n) => {
        const active = pathname !== null && (n.href === "/" ? pathname === "/" : pathname.startsWith(n.href));
        return (
          <Link
            key={n.href}
            href={n.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "rounded-md px-2 py-1.5 text-sm whitespace-nowrap text-muted-foreground transition-colors hover:bg-muted hover:text-foreground sm:px-2.5",
              active && "bg-muted font-medium text-foreground",
            )}
          >
            {n.label}
          </Link>
        );
      })}
    </nav>
  );
}

function Seal() {
  return (
    <svg viewBox="0 0 32 32" className="size-8 text-primary" aria-hidden="true">
      <rect x="3" y="3" width="26" height="26" rx="6" fill="currentColor" />
      <path
        d="M10 16.5l4 4 8-9"
        fill="none"
        stroke="var(--primary-foreground)"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M9 9h6M9 24h4" stroke="var(--primary-foreground)" strokeOpacity=".45" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}
