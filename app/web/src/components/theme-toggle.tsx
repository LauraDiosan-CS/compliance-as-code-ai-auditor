"use client";

import { MonitorIcon, MoonIcon, SunIcon } from "lucide-react";
import { useSyncExternalStore } from "react";
import { Button } from "@/components/ui/button";

type Theme = "light" | "dark" | "system";
const KEY = "ccauditor:theme";
const EVENT = "ccauditor:theme";

function subscribe(cb: () => void) {
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  mq.addEventListener("change", cb);
  window.addEventListener(EVENT, cb);
  window.addEventListener("storage", cb);
  return () => {
    mq.removeEventListener("change", cb);
    window.removeEventListener(EVENT, cb);
    window.removeEventListener("storage", cb);
  };
}

function current(): Theme {
  try {
    const t = localStorage.getItem(KEY);
    return t === "light" || t === "dark" ? t : "system";
  } catch {
    return "system";
  }
}

function apply(t: Theme) {
  const dark = t === "dark" || (t === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
}

export function ThemeToggle() {
  const theme = useSyncExternalStore<Theme>(subscribe, current, () => "system");
  const next: Theme = theme === "system" ? "light" : theme === "light" ? "dark" : "system";
  const Icon = theme === "light" ? SunIcon : theme === "dark" ? MoonIcon : MonitorIcon;

  return (
    <Button
      variant="ghost"
      size="icon-sm"
      aria-label={`Theme: ${theme}. Switch to ${next}`}
      title={`Theme: ${theme} (click for ${next})`}
      onClick={() => {
        try {
          localStorage.setItem(KEY, next);
        } catch {}
        apply(next);
        window.dispatchEvent(new Event(EVENT));
      }}
    >
      <Icon />
    </Button>
  );
}
