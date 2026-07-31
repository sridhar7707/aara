#!/usr/bin/env python3
"""
Forbidden-path guard: fails if any file matching a hardcoded sensitive-path
pattern is tracked in git, regardless of what .gitignore currently says.

Exists because .gitignore alone didn't prevent the bec5c33 incident
(2026-07-29) -- .gitignore was edited to un-ignore docs/architecture/ in
the very commit that tracked it ("chore: track docs/architecture/ in git
instead of gitignoring it"). This check is deliberately independent of
.gitignore's current content, so editing .gitignore alone can never
silently defeat it -- someone has to also edit FORBIDDEN_PATTERNS below,
a separate, more visible change subject to its own review.

Usage:
    python scripts/check_forbidden_paths.py
"""
import fnmatch
import subprocess
import sys

# Confirmed sensitive today -- these are the actual paths involved in the
# bec5c33 exposure (proprietary Sentinel product/business docs) and the
# separately gitignored private planning doc.
CONFIRMED_SENSITIVE = [
    "docs/architecture/*",
    "docs/architecture/**/*",
    "docs/PHASE_PLAN_decision_intelligence.md",
]

# Not present in this repo yet -- guarded preemptively so a future session
# can't casually introduce and track one of these without this check
# catching it. Move an entry up to CONFIRMED_SENSITIVE (with a comment
# explaining why) once something like this actually exists.
PROACTIVE_GUARDS = [
    "docs/PRD/*", "docs/PRD/**/*",
    "docs/SAD/*", "docs/SAD/**/*",
    "docs/ADR/*", "docs/ADR/**/*",
    "docs/roadmap/*", "docs/roadmap/**/*",
    "docs/experiments/*", "docs/experiments/**/*",
    "docs/competitive_analysis/*", "docs/competitive_analysis/**/*",
    "docs/future_features/*", "docs/future_features/**/*",
    "docs/business_strategy/*", "docs/business_strategy/**/*",
    "docs/investor_notes/*", "docs/investor_notes/**/*",
    "docs/prompts/*", "docs/prompts/**/*",
    "docs/meeting_notes/*", "docs/meeting_notes/**/*",
    "docs/private/*", "docs/private/**/*",
    "docs/architecture_private/*", "docs/architecture_private/**/*",
]

FORBIDDEN_PATTERNS = CONFIRMED_SENSITIVE + PROACTIVE_GUARDS


def tracked_files():
    result = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True)
    return result.stdout.splitlines()


def main():
    files = tracked_files()
    violations = []
    for path in files:
        for pattern in FORBIDDEN_PATTERNS:
            if fnmatch.fnmatch(path, pattern):
                violations.append((path, pattern))
                break

    if violations:
        print("FORBIDDEN PATH CHECK FAILED")
        print("The following tracked files match a path that must never be committed:")
        for path, pattern in violations:
            print(f"  - {path}  (matched pattern: {pattern})")
        print()
        print("If this is genuinely intentional, it requires a deliberate edit to")
        print("scripts/check_forbidden_paths.py's FORBIDDEN_PATTERNS -- removing a")
        print(".gitignore line alone must never be sufficient to pass this check.")
        sys.exit(1)

    print(f"Forbidden path check: {len(files)} tracked files checked, 0 violations.")


if __name__ == "__main__":
    main()
