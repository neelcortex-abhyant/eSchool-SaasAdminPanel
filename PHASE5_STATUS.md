# Phase 5 status — Student and parent reads

## Done

- All client-reachable read/write routes not yet implemented are registered as contract stubs in `backend/app/api/stubs.py` (217 routes) returning a Laravel-shaped error envelope (`details=contract-stub`).
- Manifest remains source of truth for encoding/auth.

## Not done

- Real implementations for settings, profile, subjects, lessons, timetable, attendance, assignments, exams, gallery, notifications, certificates, PDFs, tracking, chat history
- Student Next.js E2E against FastAPI

## Gate

**Blocked** on Phase 4 complete resources + MySQL fixtures. Stubs must never be canaried.
