# Dependency and client versions

Captured 2026-10-03 from local trees.

## Laravel API / admin panel

| Component | Version / constraint |
| --- | --- |
| PHP | `^8.1` (composer); local CLI currently unavailable in this environment |
| Laravel | `^10.0` |
| Sanctum | `^3.2` |
| Reverb | `^1.4` |
| Product baseline | eSchool SaaS v1.11.0 archive |

## Student web

| Component | Version |
| --- | --- |
| Package name | `eschool-sass-web` `0.1.0` |
| Next.js | `^15.5.9` |
| React / React DOM | `^19.2.3` |
| Axios | `^1.13.2` |
| Redux Toolkit | `^2.11.2` |

## Flutter

| App | Package | Version | SDK |
| --- | --- | --- | --- |
| Student/parent | `eschool` | `1.0.0+1` | Dart `>=3.0.2 <4.0.0` |
| Staff | `eschool_saas_staff` | `1.0.0+1` | Dart `>=3.0.2 <4.0.0` |

## Prototype scaffold (reference only)

| Component | Version |
| --- | --- |
| FastAPI | `0.115.6` |
| Uvicorn | `0.34.0` |
| SQLAlchemy | `2.0.36` |
| Next.js (proto frontend) | `^15.1.0` |
| React (proto frontend) | `^19.0.0` |

## Local toolchain (this machine)

| Tool | Observed |
| --- | --- |
| Python | 3.9.6 |
| Node / npm | v22.22.1 |
| PHP | not on PATH |
| MySQL client | not on PATH |

Phase 0 reproducible environment therefore uses Docker for MySQL/Redis (see `ops/docker-compose.phase0.yml`).
