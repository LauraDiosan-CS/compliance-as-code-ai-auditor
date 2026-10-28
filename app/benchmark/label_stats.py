"""Print the ground-truth label distribution as Markdown tables (used in app/benchmark/README.md).

Run from the repo root:  .venv/bin/python app/benchmark/label_stats.py
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

GT = Path(__file__).resolve().parent / "ground_truth"
STATUSES = ["compliant", "partial", "non_compliant", "needs_review", "not_applicable"]
POLICY = {"AIA": "eu-ai-act", "GDPR": "gdpr", "ACME": "acme-rai"}


def main() -> None:
    files = sorted(GT.glob("*.json"))
    rows, by_policy, total = [], {p: Counter() for p in POLICY.values()}, Counter()
    for f in files:
        gt = json.loads(f.read_text())
        c = Counter(gt["labels"].values())
        total.update(c)
        for rid, st in gt["labels"].items():
            by_policy[POLICY[rid.split("-")[0]]][st] += 1
        rows.append((gt["app"], gt["risk_level"], c, len(gt["labels"])))

    head = "| App | Risk | " + " | ".join(STATUSES) + " | total |"
    sep = "|---|---|" + "---:|" * (len(STATUSES) + 1)
    print(head)
    print(sep)
    for app, risk, c, n in rows:
        print(f"| {app} | {risk} | " + " | ".join(str(c.get(s, 0)) for s in STATUSES) + f" | {n} |")
    print("| **all** | | " + " | ".join(f"**{total.get(s, 0)}**" for s in STATUSES) + f" | **{sum(total.values())}** |")
    print()
    print("| Policy | " + " | ".join(STATUSES) + " | applicable |")
    print("|---|" + "---:|" * (len(STATUSES) + 1))
    for pol, c in by_policy.items():
        appl = sum(v for k, v in c.items() if k != "not_applicable")
        print(f"| {pol} | " + " | ".join(str(c.get(s, 0)) for s in STATUSES) + f" | {appl} |")


if __name__ == "__main__":
    main()
