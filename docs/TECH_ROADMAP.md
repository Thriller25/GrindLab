# 🗺️ GrindLab — Technical Roadmap

**Версия:** 1.0
**Дата создания:** 23 декабря 2025 г.
**Tech Lead:** AI Assistant (GitHub Copilot)
**Статус проекта:** MVP 1.0 (Active Development)

---

## 📋 Содержание

1. [Текущее состояние](#текущее-состояние)
2. [Архитектура](#архитектура)
3. [Roadmap по фазам](#roadmap-по-фазам)
4. [Технический долг](#технический-долг)
5. [Открытые вопросы](#открытые-вопросы)
6. [Changelog](#changelog)

---

## 📊 Текущее состояние

### Что готово ✅

| Компонент | Статус | Описание |
|-----------|--------|----------|
| **Backend API** | ✅ Работает | FastAPI 0.124, 10 роутеров, REST API |
| **Database** | ✅ Работает | SQLAlchemy 2.0, 15 моделей, Alembic миграции |
| **Frontend** | ✅ Работает | React 18 + TypeScript + Vite |
| **Auth** | ✅ Базовая | JWT токены, опциональная авторизация |
| **Rate Limiting** | ✅ Настроен | SlowAPI middleware |
| **CORS** | ✅ Настроен | Через env переменные |
| **Smoke Tests** | ✅ Есть | `scripts/smoke_api.py` |
| **Dev Scripts** | ✅ Есть | `scripts/dev.ps1` |

### Ключевые метрики

```
Backend:
├── Models:     15 ORM сущностей
├── Routers:    10 API endpoints групп
├── Schemas:    20+ Pydantic моделей
├── Services:   3 сервиса (calc, project, metrics)
├── Tests:      13+ тестовых файлов
└── LOC:        ~5000-6000 строк Python

Frontend:
├── Pages:      8 страниц
├── Components: 15+ компонентов
├── Features:   KPI, Flowsheet, Projects, Scenarios
└── LOC:        ~4000-5000 строк TypeScript
```

---

## 🏗️ Архитектура

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                 │
│                    React 18 + TypeScript                         │
│                         Vite 5.0                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP/REST (JSON)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         BACKEND                                  │
│                      FastAPI 0.124                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │   Routers    │  │   Services   │  │   Schemas    │           │
│  │  (10 групп)  │  │ (calc, etc)  │  │  (Pydantic)  │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│                              │                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │    Models    │  │     Core     │  │   Alembic    │           │
│  │ (SQLAlchemy) │  │  (settings)  │  │ (migrations) │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ SQLAlchemy ORM
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        DATABASE                                  │
│              PostgreSQL (prod) / SQLite (dev)                    │
│                                                                  │
│  Tables: User, Plant, Project, Flowsheet, FlowsheetVersion,     │
│          Unit, CalcScenario, CalcRun, CalcComparison,           │
│          Comment, ProjectMember, UserFavorite, ...              │
└─────────────────────────────────────────────────────────────────┘
```

### Ключевые сущности (Data Model)

```
User (пользователь)
  │
  ├── Project (проект инженера)
  │     │
  │     ├── → Plant (фабрика)
  │     │
  │     ├── → FlowsheetVersion (версия схемы)
  │     │         │
  │     │         └── Flowsheet (технологическая схема)
  │     │               │
  │     │               └── Unit (оборудование: мельницы, циклоны)
  │     │
  │     ├── CalcScenario (сценарий расчёта)
  │     │     │
  │     │     └── CalcRun (выполненный расчёт)
  │     │
  │     └── CalcComparison (сравнение расчётов)
  │
  ├── Comment (комментарии)
  └── UserFavorite (избранное)
```

---

## 🚀 Roadmap по фазам

### Фаза 1: MVP Stabilization (Текущая)
**Срок:** До конца декабря 2025

| # | Задача | Приоритет | Статус | Ответственный |
|---|--------|-----------|--------|---------------|
| 1.1 | Пагинация в list endpoints | 🔴 High | ✅ Done | AI |
| 1.2 | N+1 query оптимизация (joinedload) | 🔴 High | ✅ Done | AI |
| 1.3 | Enum для статусов (CalcRunStatus, etc) | 🟡 Medium | ✅ Done | AI |
| 1.4 | Pre-commit hooks (black, flake8) | 🟡 Medium | ✅ Done | AI |
| 1.5 | .env.example файл | 🟢 Low | ✅ Done | AI |
| 1.6 | Улучшить error messages | 🟡 Medium | ✅ Done | AI |
| 1.7 | **Исправить тесты после пагинации** | 🔴 High | ✅ Done | AI |
| 1.8 | **Миграция Pydantic V2 (orm_mode → from_attributes)** | 🟡 Medium | ✅ Done | AI |
| 1.9 | **Обновить deprecated APIs (FastAPI lifespan)** | 🟢 Low | ✅ Done | AI |

### Фаза 2: Production Readiness
**Срок:** Январь 2026

| # | Задача | Приоритет | Статус |
|---|--------|-----------|--------|
| 2.1 | Docker / docker-compose | 🔴 High | ✅ Done |
| 2.2 | CI/CD pipeline (GitHub Actions) | 🔴 High | 📋 TODO |
| 2.3 | PostgreSQL production setup | 🔴 High | ✅ Done |
| 2.4 | Structured logging (JSON) | 🟡 Medium | 📋 TODO |
| 2.5 | Health checks / monitoring | 🟡 Medium | ✅ Done |
| 2.6 | E2E tests (Playwright) | 🟡 Medium | 📋 TODO |

### Фаза 3: Feature Expansion
**Срок:** Февраль 2026+

| # | Задача | Приоритет | Статус |
|---|--------|-----------|--------|
| 3.1 | Реальные модели оборудования (SAG, Ball Mill) | 🔴 High | 📋 TODO |
| 3.2 | Интеграция с INKA/Data Hub | 🔴 High | 📋 TODO |
| 3.3 | Экспорт отчётов (PDF/Excel) | 🟡 Medium | 📋 TODO |
| 3.4 | Real-time notifications (WebSocket) | 🟢 Low | 📋 TODO |
| 3.5 | Multi-tenant support | 🟢 Low | 📋 TODO |

---

## 🔧 Технический долг

### 🔴 Критический (нужно исправить СЕЙЧАС)

| # | Проблема | Файл | Решение | Статус |
|---|----------|------|---------|--------|
| TD-1 | ~~15 тестов падают~~ | `tests/*.py` | Rate limiter reset + тесты обновлены | ✅ Done |
| TD-2 | ~~Pydantic V2 deprecation warnings~~ | `schemas/*.py` | `model_config = ConfigDict(from_attributes=True)` | ✅ Done |
| TD-3 | ~~FastAPI deprecated `on_event`~~ | `main.py` | Migrated to `lifespan` context manager | ✅ Done |
| TD-4 | ~~SQLAlchemy deprecated `Query.get()`~~ | `routers/*.py` | Replaced with `db.get(Model, id)` | ✅ Done |
| TD-5 | ~~Pydantic deprecated `.dict()`~~ | `routers/*.py` | Replaced with `.model_dump()` | ✅ Done |

### 🟡 Средний приоритет

| # | Проблема | Решение |
|---|----------|---------|
| TD-6 | N+1 queries в projects.py | Использовать joinedload |
| TD-7 | Нет structured logging | Добавить JSON логирование |

### 🟢 Низкий приоритет

| # | Проблема | Решение |
|---|----------|---------|
| TD-8 | Frontend unit tests отсутствуют | Добавить Vitest |
| TD-9 | Нет стандарта commit messages | Добавить commitlint |

---

## ❓ Открытые вопросы

### Бизнес-вопросы (требуют ответа от стейкхолдеров)

| # | Вопрос | Статус | Ответ |
|---|--------|--------|-------|
| Q-1 | Кто основные пользователи системы? | ❓ Открыт | - |
| Q-2 | Какие фабрики/клиенты планируются для пилота? | ❓ Открыт | - |
| Q-3 | Какой timeline для production релиза? | ❓ Открыт | - |
| Q-4 | Есть ли требования по безопасности (SOC2, ISO)? | ❓ Открыт | - |

### Технические вопросы

| # | Вопрос | Статус | Ответ |
|---|--------|--------|-------|
| Q-5 | Где будет хоститься production? (Cloud/On-premise) | ❓ Открыт | - |
| Q-6 | Интеграция с INKA — есть API документация? | ❓ Открыт | - |
| Q-7 | Модели оборудования — кто пишет математику? | ❓ Открыт | - |
| Q-8 | Нужен ли отдельный Calc Service микросервис? | ❓ Открыт | - |

---

## 📝 Changelog

### 2025-12-23 (Анализ #2)
- 🔍 Проведён полный анализ проекта
- 🧪 Обнаружено: 74 теста, 15 падают (из-за изменения API пагинации)
- ⚠️ Найдено 28+ deprecation warnings (Pydantic V2, FastAPI, SQLAlchemy)
- 📋 Обновлён список технического долга с приоритетами
- ✅ Отмечены выполненные задачи (пагинация, enum, pre-commit, .env.example)

### 2025-12-23 (Инициализация)
- ✨ Создан TECH_ROADMAP.md
- 📊 Задокументировано текущее состояние проекта
- 🗺️ Определены фазы развития (MVP → Production → Expansion)
- 📋 Составлен список технического долга
- ❓ Зафиксированы открытые вопросы

---

## 📚 Связанные документы

- [README.md](../README.md) — Общее описание проекта
- [DEVELOPMENT_RULES.md](../DEVELOPMENT_RULES.md) — Правила разработки
- [CODE_ANALYSIS.md](../CODE_ANALYSIS.md) — Анализ качества кода
- [testing.md](testing.md) — Чек-лист тестирования
- [dev.md](dev.md) — Команды для разработки

---

*Документ обновляется по мере прогресса. Последнее обновление: 23 декабря 2025 г.*
