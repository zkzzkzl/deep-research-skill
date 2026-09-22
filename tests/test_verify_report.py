from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_report.py"


class VerifyReportTests(unittest.TestCase):
    def run_verify(self, text: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-X", "utf8", str(SCRIPT)],
            input=text,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )

    def test_english_concise_output(self):
        result = self.run_verify(
            "China's 2025 NEV exports reached 1.2 million units.\n"
            "Source: Example Institute (https://example.com/report, published: 2026-01-10)\n"
            "Verification: Verified\n"
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_chinese_concise_output(self):
        result = self.run_verify(
            "2026 年测试结论。\n"
            "来源：示例机构（https://example.com/report，发布：2026-01-10）\n"
            "核验：已核实\n"
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_english_report_output(self):
        report = """### Research Findings
- China's 2025 NEV exports reached 1.2 million units (Fact | Verified)
- Growth accelerated in the second half (Source view | Limited evidence)

### Evidence and Sources
| # | Fact | Value/Key point | Source and Full URL | Publication Date | Evidence Type |
|---|---|---|---|---|---|
| 1 | 2025 NEV exports | 1.2 million units | Example Institute (https://example.com/report) | 2026-01-10 | Fact |

Broken links: None

### Source Disagreements
No material disagreements found.

### Verification Status
The export figure comes from a primary source.

### Uncovered Scope
None
"""
        result = self.run_verify(report)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()