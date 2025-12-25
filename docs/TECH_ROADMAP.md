
# 🗺️ GrindLab — Technical Roadmap

**Версия:** 2.0
**Дата обновления:** 25 декабря 2025 г.
**Tech Lead:** AI Assistant (GitHub Copilot)
**Статус проекта:** MVP Core (Active Development)

> 📋 **Источник истины:** Бэклог синхронизирован с `docs/Беклог + функциональная карта/GrindLab_Backlog_Cards_v2_FullProject.xlsx`

---

## 📋 Содержание

1. [Текущее состояние](#текущее-состояние)
2. [Релизы и Эпики](#релизы-и-эпики)
3. [Спринты и фичи](#спринты-и-фичи)
4. [Gap Analysis](#gap-analysis)
5. [Технический долг](#технический-долг)
6. [Changelog](#changelog)

---

## 📊 Текущее состояние

### Что готово ✅ (Pre-Backlog работы)

| Компонент | Статус | Описание |
|-----------|--------|----------|
| **Backend API** | ✅ Работает | FastAPI 0.124, 10 роутеров, REST API |
| **Database** | ✅ Работает | SQLAlchemy 2.0, 15 моделей, Alembic миграции |
| **Frontend** | ✅ Работает | React 18 + TypeScript + Vite |
| **Auth (базовая)** | ✅ Работает | JWT токены, опциональная авторизация |
| **Docker** | ✅ Готово | docker-compose для dev/prod |
| **CI/CD** | ✅ Готово | GitHub Actions (test/build/deploy) |
| **Health Checks** | ✅ Готово | `/health`, `/health/ready` |
| **Structured Logging** | ✅ Готово | structlog с JSON output |
| **E2E Tests** | ✅ Готово | Playwright базовые сценарии |

### Метрики кодовой базы

```
Backend:          Frontend:
├── Models: 15    ├── Pages: 8
├── Routers: 10   ├── Components: 15+
├── Schemas: 20+  └── LOC: ~4000
├── Tests: 74
└── LOC: ~6000
```

---

## 🚀 Релизы и Эпики

### Release Overview

| Release | Название | Спринты | Статус |
|---------|----------|---------|--------|
| **1.0 MVP Core** | Базовый функционал | S0-S5 | 🔄 In Progress |
| **1.1 Production Hardening** | Очереди, безопасность | S6 | 📋 Planned |
| **2.0 INKA Integration** | Интеграция с DataHub | S7-S8 | ⏸️ Отложено |
| **3.0 Online Twin** | Real-time контур | S10-S12 | 📋 Future |

---

### 🎯 Release 1.0 — MVP Core

#### EP0: Foundations (S0) — границы, контракты, ADR
| ID | Feature | Component | Priority | Status |
|----|---------|-----------|----------|--------|
| F0.1 | MVP Scope & Release Plan | Product | P0 | ✅ Done |
| F0.2 | Data Contracts: Material/PSD/Blast/KPI | Backend+Core | P0 | ✅ Done |
| F0.3 | ADR: архитектурные решения | Engineering | P1 | 📋 TODO |

#### EP1: Auth (Keycloak) + RBAC/ACL (S1)
| ID | Feature | Component | Priority | Status |
|----|---------|-----------|----------|--------|
| F1.1 | Keycloak docker-compose + realm | DevOps | P0 | 📋 TODO |
| F1.2 | UI: OIDC login/logout (PKCE) | Frontend | P0 | 📋 TODO |
| F1.3 | Backend: JWT validation (JWKS) + RBAC | Backend | P0 | 🔶 Partial |
| F1.4 | ACL на проекты (membership) | Backend+DB | P0 | ✅ Done |

#### EP2: Проекты + версионирование (S1-S2)
| ID | Feature | Component | Priority | Status |
|----|---------|-----------|----------|--------|
| F2.1 | Project CRUD (API + UI) | Backend+Frontend | P0 | ✅ Done |
| F2.2 | Versioning model (immutable artifacts) | Backend+DB | P0 | 🔶 Partial |
| F2.3 | Change Log / Audit minimal | Backend+DB | P1 | 📋 TODO |

#### EP3: Materials & Ingestion (S2-S3)
| ID | Feature | Component | Priority | Status |
|----|---------|-----------|----------|--------|
| F3.1 | Импорт Material из файла | Backend+Frontend | P0 | ✅ Done |
| F3.2 | Валидация + паспорт материала | Backend | P0 | ✅ Done |
| F3.3 | PSD core: bins + rebin + Pxx | Core | P0 | ✅ Done |
| F3.4 | Блендинг материалов | Backend+Core | P1 | 📋 TODO |
| F3.5 | Импорт Blast → Material | Backend | P1 | 📋 TODO |

#### EP4: Flowsheet Designer MVP (S3)
| ID | Feature | Component | Priority | Status |
|----|---------|-----------|----------|--------|
| F4.1 | Flowsheet editor: граф узлов | Frontend+Backend | P0 | ✅ Done |
| F4.2 | Node Library (Crusher/Mill/Cyclone/Screen) | Core+Frontend | P0 | ✅ Done |
| F4.3 | Flowsheet validation rules | Backend+Core | P0 | ✅ Done |
| F4.4 | Назначение Material на feed | Frontend+Backend | P0 | ✅ Done |

#### EP5: Solver / Simulation Core (S4)
| ID | Feature | Component | Priority | Status |
|----|---------|-----------|----------|--------|
| F5.1 | Execution engine + convergence | Core | P0 | ✅ Done |
| F5.2 | KPI computation (P80/P50/P240, CL) | Core | P0 | ✅ Done |
| F5.3 | Run management (RunVersion) | Backend+DB | P0 | ✅ Done |

#### EP6: Calibration & Validation (S5)
| ID | Feature | Component | Priority | Status |
|----|---------|-----------|----------|--------|
| F6.1 | Calibration dataset management | Backend+Frontend | P1 | 📋 TODO |
| F6.2 | Calibration engine (MVP optimizer) | Core | P1 | 📋 TODO |
| F6.3 | Calibration report | Backend+Frontend | P1 | 📋 TODO |

#### EP7: What-if & Compare (S5)
| ID | Feature | Component | Priority | Status |
|----|---------|-----------|----------|--------|
| F7.1 | Scenario builder (what-if) | Frontend+Backend | P1 | 🔶 Partial |
| F7.2 | Batch runs for scenarios | Backend+Core | P1 | 📋 TODO |
| F7.3 | Compare dashboard | Frontend | P1 | 📋 TODO |

#### EP8: Visualization & Reporting (S4-S5)
| ID | Feature | Component | Priority | Status |
|----|---------|-----------|----------|--------|
| F8.1 | PSD plots (включая P240) | Frontend | P0 | 📋 TODO |
| F8.2 | Fact vs Model plots | Frontend | P1 | 📋 TODO |
| F8.3 | Scenario comparison plots | Frontend | P1 | 📋 TODO |
| F8.4 | Export package (PNG + CSV/Excel) | Backend+Frontend | P1 | 📋 TODO |

#### EP9: Platform (S0-S2)
| ID | Feature | Component | Priority | Status |
|----|---------|-----------|----------|--------|
| F9.1 | DB schema + migrations (PostgreSQL) | DB+Backend | P0 | ✅ Done |
| F9.2 | Audit log minimal | Backend | P1 | 📋 TODO |
| F9.3 | Health checks + logging + errors | Backend+DevOps | P0 | ✅ Done |
| F9.4 | CI smoke (build + tests) | DevOps | P0 | ✅ Done |

---

### 🔧 Release 1.1 — Production Hardening (S6)

| Epic | ID | Feature | Priority | Status |
|------|----|---------|----------|--------|
| EP11 | F11.1 | Job Queue + Worker (Redis/Celery) | P0 | 📋 TODO |
| EP11 | F11.2 | Retries + Idempotency | P0 | 📋 TODO |
| EP11 | F11.5 | Artifacts Storage (MinIO/S3) | P1 | 📋 TODO |
| EP16 | F16.2 | Security Hardening | P0 | 📋 TODO |
| EP16 | F16.3 | Backup/Restore + DR | P0 | 📋 TODO |
| EP17 | F17.3 | Regression Suite | P1 | 📋 TODO |

---

### ⏸️ Release 2.0 — INKA Integration (S7-S8) — ОТЛОЖЕНО

| ID | Feature | Status |
|----|---------|--------|
| F10.1-F10.5 | INKA Connectors, Sync Jobs | ⏸️ Postponed |

---

## 📊 Gap Analysis

### Что реализовано vs Бэклог

| Область | Бэклог требует | Текущее состояние | Gap |
|---------|----------------|-------------------|-----|
| **Auth** | Keycloak OIDC + RBAC | JWT базовый | 🔴 Нужен Keycloak |
| **Projects** | CRUD + ACL | ✅ Реализовано | ✅ Готово |
| **Versioning** | Immutable artifacts | Частично | 🟡 Доработать |
| **Materials** | Import + PSD + Blend | Нет | 🔴 Нужно |
| **Flowsheet** | Editor + Nodes | UI есть, Core нет | 🟡 Core нужен |
| **Solver** | Execution + KPI | Мок | 🔴 Нужен Core |
| **Calibration** | Dataset + Optimizer | Нет | 🔴 Нужно |
| **Reports** | Plots + Export | Нет | 🟡 Нужно |
| **Platform** | DB + CI + Health | ✅ Реализовано | ✅ Готово |

### Следующие приоритеты (рекомендация)

1. **F0.2** Data Contracts — определить структуры Material/PSD/KPI
2. **F1.1** Keycloak setup — production-ready auth
3. **F3.1-F3.3** Materials — импорт и PSD ядро
4. **F4.2** Node Library — модели оборудования
5. **F5.1** Solver Core — execution engine

---

## 🔧 Технический долг

| # | Проблема | Статус |
|---|----------|--------|
| TD-1 | Pydantic V2 deprecation | ✅ Fixed |
| TD-2 | FastAPI deprecated on_event | ✅ Fixed |
| TD-3 | SQLAlchemy Query.get() | ✅ Fixed |
| TD-4 | N+1 queries | ✅ Fixed |
| TD-5 | Error messages | ✅ Fixed |
| TD-6 | Frontend unit tests | 📋 TODO |
| TD-7 | Commit message standard | 📋 TODO |

---

## 📝 Changelog

### 2025-12-25 (EP4 Complete — Flowsheet Designer MVP)
- ✅ F4.1 Flowsheet editor: node graph (React Flow)
- ✅ F4.2 Node Library: 8 equipment types with drag-n-drop
- ✅ F4.3 Canvas Editor: pan/zoom/selection/delete
- ✅ F4.4 Material assignment: MaterialSelector + NodePropertyPanel
- 📦 Materials Library API (in-memory, TODO: PostgreSQL)

### 2025-12-24 (v2.0 — Backlog Sync)
- 🔄 Синхронизирован TECH_ROADMAP с официальным бэклогом
- 📊 Добавлен Gap Analysis
- 🎯 Структура по Эпикам (EP0-EP17) и Фичам (F*.*)
- ⏸️ INKA Integration (EP10) отложена

### 2025-12-23 (Phase 2 Complete)
- ✅ Docker/docker-compose
- ✅ CI/CD GitHub Actions
- ✅ Structured logging
- ✅ E2E tests Playwright
- ✅ Branch protection rules

### 2025-12-23 (Phase 1 Complete)
- ✅ Пагинация, N+1 fix, Enums
- ✅ Pre-commit hooks
- ✅ Deprecation fixes
- ✅ 74 tests passing

---

## 📚 Связанные документы

- [GrindLab_Backlog_Cards_v2_FullProject.xlsx](Беклог%20+%20функциональная%20карта/GrindLab_Backlog_Cards_v2_FullProject.xlsx) — Полный бэклог
- [GrindLab_Backlog_Cards_for_AI_v2.docx](Беклог%20+%20функциональная%20карта/GrindLab_Backlog_Cards_for_AI_v2.docx) — Карточки для AI
- [GrindLab_Математическое_ядро_v1.0.docx](Беклог%20+%20функциональная%20карта/GrindLab_Математическое_ядро_и_аппарат_v1.0.docx) — Математика
- [GrindLab_Архитектура_MVP_Core_v1.0.docx](Беклог%20+%20функциональная%20карта/GrindLab_Архитектура_MVP_Core_v1.0.docx) — Архитектура
- [ARCHITECTURE.md](ARCHITECTURE.md) — Техническая архитектура
- [DATA_MODEL.md](DATA_MODEL.md) — Модель данных
- [DOCKER.md](DOCKER.md) — Docker документация

---

*Документ синхронизирован с бэклогом. Последнее обновление: 25 декабря 2025 г.*
