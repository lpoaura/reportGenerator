# src/reportgenerator/analysis/common/timing.py
import json
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path


class RunTimer:
    def __init__(self):
        self.steps = []

    @contextmanager
    def step(self, name):
        start = time.perf_counter()
        print(f"→ {name}...")
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            self.steps.append({"step": name, "duration_s": round(duration, 2)})
            print(f"✓ {name} terminé en {duration:.1f}s")

    def summary(self):
        total = sum(s["duration_s"] for s in self.steps)
        print("\n--- Résumé des temps d'exécution ---")
        for s in self.steps:
            pct = (s["duration_s"] / total * 100) if total else 0
            print(f"  {s['step']:<35} {s['duration_s']:>7.1f}s  ({pct:4.1f}%)")
        print(f"  {'TOTAL':<35} {total:>7.1f}s")
        return total

    def save_json(self, path: Path, meta: dict | None = None):
        payload = {
            "date": datetime.now().isoformat(),
            "steps": self.steps,
            "meta": meta or {},
        }
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )