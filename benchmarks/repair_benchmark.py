"""Micro-benchmark for the rule-based repair pipeline."""

from __future__ import annotations

import time

from pdf2epub_ai.repair.rules import RuleBasedRepairer


def main() -> None:
    repairer = RuleBasedRepairer()
    sample = ("Bug ün de vam etti. y er verildi. i çin k itap " * 5000).strip()
    start = time.perf_counter()
    repaired = repairer.repair(sample)
    elapsed = time.perf_counter() - start
    print(
        f"chars={len(sample)} elapsed={elapsed:.3f}s throughput={len(sample) / elapsed:,.0f} chars/s"
    )
    print(repaired[:120])


if __name__ == "__main__":
    main()
