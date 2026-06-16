#!/usr/bin/env python3
"""Phase 9.0: Normalize DEFERRED_LEDGER.md statuses to standard format."""

import re

LEDGER = "docs/design/EAASP/DEFERRED_LEDGER.md"

# Read the file
with open(LEDGER) as f:
    content = f.read()

# Section A: Historical items with non-standard notation
# Pattern: old notation in status cell → standardized ✅ CLOSED
section_a = {
    "D1": "✅ CLOSED 2026-04-12 Phase 0.5 S4.T2 @ a6fad2b6",
    "D2": "✅ CLOSED 2026-04-12 Phase 0.5 S4.T2 @ a6fad2b6",
    "D4": "✅ CLOSED 2026-04-13 Phase 1 ADR-V2-002",
    "D7": "✅ CLOSED 2026-04-11 Phase 1 ADR-V2-001",
    "D47": "✅ CLOSED 2026-04-12 Phase 0 S4.T2",
    "D49": "✅ CLOSED 2026-04-12 Phase 0 S4.T1",
    "D51": "✅ CLOSED 2026-04-15 Phase 2 S3.T5 @ 7cb48eb",
    "D52": "✅ CLOSED 2026-04-12 Phase 0 S4.T1",
    "D53": "✅ CLOSED 2026-04-15 Phase 2 S3.T5 @ 7cb48eb",
    "D54": "✅ CLOSED 2026-04-12 Phase 0.5 S1",
    "D60": "✅ CLOSED 2026-04-15 Phase 2 S2.T5 @ bad4269",
    "D83": "✅ CLOSED 2026-04-14 Phase 2 S1.T4 @ bdc5b8b",
    "D84": "✅ CLOSED 2026-04-15 Phase 2 S4.T2 @ bd55bc4",
    "D85": "✅ CLOSED 2026-04-14 Phase 2 S1.T5 @ bdc5b8b",
    "D86": "✅ CLOSED 2026-04-14 Phase 2 S1.T3 @ d0e6cb0",
    "D87": "✅ CLOSED 2026-04-14 Phase 2 S1.T1 @ bdc4fd5",
    "D89": "✅ CLOSED 2026-04-15 Phase 2 S4.T1 @ 28e6b21",
    "D10": "✅ CLOSED 2026-06-10 Phase 8.0 Plan 03 @ 28a9b15d (L3 dual-transport done; L2/L4 deferred to Phase 9.2)",
    "D14": "✅ CLOSED 2026-06-10 Phase 8.4 Plan 01 @ 20d3f443",
    "D15": "✅ CLOSED 2026-06-10 Phase 8.4 Plan 02 @ 8625f755",
    "D16": "✅ CLOSED 2026-06-10 Phase 8.0 Plan 02 @ b4a2f517",
    "D19": "✅ CLOSED 2026-06-10 Phase 8.0 Plan 02 @ 2a4f87f6",
    "D20": "✅ CLOSED 2026-06-10 Phase 8.0 Plan 01 @ 95d91963",
    "D24": "✅ CLOSED 2026-06-13 Phase 8.6 Plan 01 @ 83dae165",
    "D25": "✅ CLOSED 2026-06-10 Phase 8.0 Plan 02 @ 54616d22",
    "D28": "✅ CLOSED 2026-06-10 Phase 8.2 Plan 02 @ b5c545ff",
    "D29": "✅ CLOSED 2026-06-10 Phase 8.2 Plan 02 @ b5c545ff",
    "D31": "✅ CLOSED 2026-06-10 Phase 8.2 Plan 02 @ b5c545ff",
    "D34": "✅ CLOSED 2026-06-10 Phase 8.2 Plan 01 @ b9741ab3",
    "D38": "✅ CLOSED 2026-06-10 Phase 8.2 Plan 01 @ ddc2cefc",
    "D39": "✅ CLOSED 2026-06-10 Phase 8.2 Plan 02 @ cf2694b5",
    "D42": "✅ CLOSED 2026-06-10 Phase 8.3 Plan 02 @ cbf71505",
    "D43": "✅ CLOSED 2026-06-10 Phase 8.3 Plan 02 @ cbf71505",
    "D44": "✅ CLOSED 2026-06-10 Phase 8.3 Plan 02 @ cbf71505",
    "D45": "✅ CLOSED 2026-06-10 Phase 8.3 Plan 02 @ cbf71505",
    "D48": "✅ CLOSED 2026-06-10 Phase 8.5 Plan 02 @ e6b837a0",
    "D50": "✅ CLOSED 2026-06-10 Phase 8.5 Plan 03 @ 77566619",
    "D56": "✅ CLOSED 2026-06-13 Phase 8.6 Plan 01 @ 93ef61b8",
    "D59": "✅ CLOSED 2026-06-10 Phase 8.4 Plan 02 @ 3a54cb31",
    "D61": "✅ CLOSED 2026-06-10 Phase 8.3 Plan 02 @ c3c828a7",
    "D65": "✅ CLOSED 2026-06-10 Phase 8.5 Plan 01 @ a98a5653",
    "D78": "✅ CLOSED 2026-04-20 Phase 3 S2.T2 @ 4633c0bc",
    "D92": "✅ CLOSED 2026-06-10 Phase 8.4 Plan 01 @ a0bd006b",
    "D95": "✅ CLOSED 2026-06-10 Phase 8.5 Plan 01 @ 6c2bc81a",
    "D96": "✅ CLOSED 2026-06-10 Phase 8.4 Plan 01 @ 20d3f443",
    "D97": "✅ CLOSED 2026-06-10 Phase 8.4 Plan 01 @ 20d3f443",
    "D99": "✅ CLOSED 2026-06-10 Phase 8.4 Plan 01 @ 635617bf",
    "D100": "✅ CLOSED 2026-06-10 Phase 8.5 Plan 01 @ b91a4408",
    "D101": "✅ CLOSED 2026-06-10 Phase 8.4 Plan 01 @ 635617bf",
    "D105": "✅ CLOSED 2026-06-10 Phase 8.5 Plan 02 @ b861a7a0",
    "D107": "✅ CLOSED 2026-06-10 Phase 8.5 Plan 03 @ 8d4d628c",
    "D108": "✅ CLOSED 2026-06-10 Phase 8.5 Plan 03 @ 6400ed8c",
    "D126": "✅ CLOSED 2026-06-13 Phase 8.6 Plan 01 @ 93ef61b8",
    "D127": "✅ CLOSED 2026-06-13 Phase 8.6 Plan 01 @ 93ef61b8",
    "D128": "✅ CLOSED 2026-06-13 Phase 8.6 Plan 01 @ 2861b1be",
    "D129": "✅ CLOSED 2026-06-13 Phase 8.6 Plan 01 @ 93ef61b8",
    "D152": "✅ CLOSED 2026-04-28 Phase 4a T7 @ 86295053",
}

count = 0
for d_id, new_status in section_a.items():
    # Match the D-row line: | **D{N}** | ... | [old status] | ...
    pattern = rf"(^\| \*\*{d_id}\*\* \| .*? \| )(.+?)( \| .*$)"
    match = re.search(pattern, content, re.MULTILINE)
    if match:
        old_middle = match.group(2)
        # Only replace if not already standardized
        if "✅ CLOSED 2026" not in old_middle:
            new_line = match.group(1) + new_status + match.group(3)
            content = content.replace(match.group(0), new_line)
            count += 1
            print(f"  {d_id}: normalized")
    else:
        print(f"  {d_id}: NOT FOUND (may already have standard format)")

print(f"\nNormalized {count} rows in {LEDGER}")

with open(LEDGER, "w") as f:
    f.write(content)

# Verify
new_count = content.count("✅ CLOSED")
print(f"Total ✅ CLOSED entries: {new_count}")
