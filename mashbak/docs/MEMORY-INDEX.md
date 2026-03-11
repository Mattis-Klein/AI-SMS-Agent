# Memory Index

This file tracks where operational memory-like information lives in Mashbak docs.

## Canonical Runtime Memory

- Session context state model: docs/ARCHITECTURE.md
- Runtime config contract: docs/ENVIRONMENT.md
- Regression expectations: docs/TESTING.md

## Persistent Project Knowledge

- System overview: README.md
- Component boundaries: docs/ARCHITECTURE.md
- File layout: docs/PROJECT-STRUCTURE.md
- Operations and startup flows: docs/RUNBOOK.md, docs/QUICK-START.md, docs/INSTALLATION.md

## Legacy Compatibility Notes

- Legacy docs retained under docs/legacy/
- Compatibility API endpoint: POST /run (forwards to /execute)

## Update Policy

When behavior changes in code:
1. Update the specific topic document first.
2. Update this index if canonical locations changed.
3. Keep compatibility behavior labeled as compatibility.

Last Updated: March 11, 2026
