# 📊 GrindLab — Модель данных

**Версия:** 1.0
**Дата:** 23 декабря 2025 г.

---

## 1. Обзор сущностей

GrindLab использует реляционную модель данных с 15 основными сущностями.

### Категории сущностей

| Категория | Сущности | Описание |
|-----------|----------|----------|
| **Пользователи** | User, ProjectMember | Управление доступом |
| **Организация** | Plant | Обогатительные фабрики |
| **Проекты** | Project, UserFavorite | Проекты инженеров |
| **Схемы** | Flowsheet, FlowsheetVersion, Unit | Технологические схемы |
| **Расчёты** | CalcScenario, CalcRun, CalcComparison | Моделирование |
| **Коммуникация** | Comment | Комментарии |

---

## 2. Детальное описание сущностей

### 2.1 User (Пользователь)

Пользователь системы — инженер или администратор.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | Integer (PK) | Уникальный идентификатор |
| `email` | String | Email (уникальный) |
| `hashed_password` | String | Хеш пароля (bcrypt) |
| `is_superuser` | Boolean | Флаг администратора |
| `created_at` | DateTime | Дата создания |

**Связи:**
- `projects` → Project (один-ко-многим, владелец)
- `comments` → Comment (один-ко-многим, автор)
- `favorites` → UserFavorite (один-ко-многим)

---

### 2.2 Plant (Фабрика)

Обогатительная фабрика — физический объект.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | UUID (PK) | Уникальный идентификатор |
| `name` | String(255) | Название фабрики |
| `location` | String(255) | Местоположение |
| `created_at` | DateTime | Дата создания |

**Связи:**
- `projects` → Project (один-ко-многим)
- `flowsheets` → Flowsheet (один-ко-многим)

**Примеры:**
- "Фабрика Кумтор" (Кыргызстан)
- "ГОК Михеевский" (Россия)

---

### 2.3 Project (Проект)

Проект инженера — рабочее пространство для моделирования.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | UUID (PK) | Уникальный идентификатор |
| `name` | String(255) | Название проекта |
| `description` | Text | Описание |
| `owner_user_id` | Integer (FK) | Владелец проекта |
| `plant_id` | UUID (FK) | Связанная фабрика |
| `created_at` | DateTime | Дата создания |
| `updated_at` | DateTime | Дата обновления |

**Связи:**
- `owner` → User (многие-к-одному)
- `plant` → Plant (многие-к-одному)
- `flowsheet_versions` → FlowsheetVersion (многие-ко-многим)
- `calc_scenarios` → CalcScenario (один-ко-многим)
- `calc_runs` → CalcRun (один-ко-многим)
- `members` → ProjectMember (один-ко-многим)

---

### 2.4 Flowsheet (Технологическая схема)

Схема дробления-измельчения для фабрики.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | UUID (PK) | Уникальный идентификатор |
| `name` | String(255) | Название схемы |
| `plant_id` | UUID (FK) | Связанная фабрика |
| `created_at` | DateTime | Дата создания |

**Связи:**
- `plant` → Plant (многие-к-одному)
- `versions` → FlowsheetVersion (один-ко-многим)

---

### 2.5 FlowsheetVersion (Версия схемы)

Конкретная версия технологической схемы с историей изменений.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | UUID (PK) | Уникальный идентификатор |
| `flowsheet_id` | UUID (FK) | Родительская схема |
| `version_number` | Integer | Номер версии |
| `data` | JSONB | Данные схемы (структура, связи) |
| `status` | String(32) | Статус: DRAFT, ACTIVE, ARCHIVED |
| `created_at` | DateTime | Дата создания |

**Связи:**
- `flowsheet` → Flowsheet (многие-к-одному)
- `units` → Unit (один-ко-многим)
- `calc_scenarios` → CalcScenario (один-ко-многим)

**Статусы:**
- `DRAFT` — черновик, редактируется
- `ACTIVE` — активная версия
- `ARCHIVED` — архивная версия

---

### 2.6 Unit (Оборудование)

Единица оборудования в схеме (мельница, циклон, конвейер).

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | UUID (PK) | Уникальный идентификатор |
| `flowsheet_version_id` | UUID (FK) | Версия схемы |
| `unit_type` | String(64) | Тип: SAG_MILL, BALL_MILL, CYCLONE, etc |
| `name` | String(255) | Название |
| `params` | JSONB | Параметры оборудования |
| `position_x` | Float | X координата на схеме |
| `position_y` | Float | Y координата на схеме |
| `created_at` | DateTime | Дата создания |

**Типы оборудования (unit_type):**

| Тип | Описание |
|-----|----------|
| `SAG_MILL` | Мельница полусамоизмельчения (SAG) |
| `BALL_MILL` | Шаровая мельница |
| `CYCLONE` | Гидроциклон |
| `CRUSHER` | Дробилка |
| `SCREEN` | Грохот |
| `CONVEYOR` | Конвейер |
| `PUMP` | Насос |
| `SUMP` | Зумпф |

**Пример params для BALL_MILL:**
```json
{
  "diameter_m": 5.5,
  "length_m": 8.5,
  "power_kw": 4500,
  "speed_rpm": 12.5,
  "ball_charge_pct": 32,
  "liner_type": "rubber"
}
```

---

### 2.7 CalcScenario (Сценарий расчёта)

Сценарий "что если?" с набором параметров.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | UUID (PK) | Уникальный идентификатор |
| `name` | String(255) | Название сценария |
| `description` | Text | Описание |
| `is_baseline` | Boolean | Это базовый сценарий? |
| `project_id` | UUID (FK) | Проект |
| `flowsheet_version_id` | UUID (FK) | Версия схемы |
| `parameters` | JSONB | Параметры сценария |
| `created_at` | DateTime | Дата создания |

**Связи:**
- `project` → Project (многие-к-одному)
- `flowsheet_version` → FlowsheetVersion (многие-к-одному)
- `calc_runs` → CalcRun (один-ко-многим)

**Пример parameters:**
```json
{
  "feed": {
    "tonnage_tph": 1200,
    "hardness_kwh_t": 14.5,
    "moisture_pct": 5.0
  },
  "targets": {
    "p80_um": 150
  }
}
```

---

### 2.8 CalcRun (Расчёт)

Выполненный расчёт с входными данными и результатами.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | UUID (PK) | Уникальный идентификатор |
| `scenario_id` | UUID (FK) | Связанный сценарий (опционально) |
| `project_id` | UUID (FK) | Проект |
| `input_json` | JSONB | Входные данные |
| `result_json` | JSONB | Результаты расчёта |
| `status` | String(32) | Статус: PENDING, RUNNING, SUCCESS, FAILED |
| `error_message` | Text | Сообщение об ошибке (если FAILED) |
| `started_at` | DateTime | Время начала |
| `finished_at` | DateTime | Время завершения |
| `created_at` | DateTime | Дата создания |

**Статусы (CalcRunStatus):**
- `PENDING` — ожидает выполнения
- `RUNNING` — выполняется
- `SUCCESS` — успешно завершён
- `FAILED` — ошибка

**Пример result_json:**
```json
{
  "kpi": {
    "throughput_tph": 1180,
    "p80_um": 152,
    "power_kw": 8500,
    "specific_energy_kwh_t": 7.2
  },
  "streams": [...],
  "units": [...]
}
```

---

### 2.9 CalcComparison (Сравнение расчётов)

Сравнение нескольких расчётов между собой.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | UUID (PK) | Уникальный идентификатор |
| `name` | String(255) | Название сравнения |
| `description` | Text | Описание |
| `calc_run_ids` | JSONB (Array) | Список ID расчётов |
| `project_id` | UUID (FK) | Проект |
| `created_at` | DateTime | Дата создания |

---

### 2.10 Comment (Комментарий)

Комментарий к расчёту или сценарию.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | UUID (PK) | Уникальный идентификатор |
| `text` | Text | Текст комментария |
| `author_id` | Integer (FK) | Автор (User) |
| `calc_run_id` | UUID (FK) | Расчёт (опционально) |
| `calc_scenario_id` | UUID (FK) | Сценарий (опционально) |
| `created_at` | DateTime | Дата создания |

---

### 2.11 ProjectMember (Участник проекта)

Связь пользователя с проектом (для совместной работы).

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | UUID (PK) | Уникальный идентификатор |
| `project_id` | UUID (FK) | Проект |
| `user_id` | Integer (FK) | Пользователь |
| `role` | String(32) | Роль: OWNER, EDITOR, VIEWER |
| `created_at` | DateTime | Дата добавления |

**Роли:**
- `OWNER` — владелец, полный доступ
- `EDITOR` — редактор, может изменять
- `VIEWER` — только просмотр

---

### 2.12 UserFavorite (Избранное)

Избранные проекты/расчёты пользователя.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | UUID (PK) | Уникальный идентификатор |
| `user_id` | Integer (FK) | Пользователь |
| `project_id` | UUID (FK) | Проект (опционально) |
| `calc_run_id` | UUID (FK) | Расчёт (опционально) |
| `created_at` | DateTime | Дата добавления |

---

### 2.13 ProjectFlowsheetVersion (Связь проект-версия схемы)

Связующая таблица для many-to-many между Project и FlowsheetVersion.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | UUID (PK) | Уникальный идентификатор |
| `project_id` | UUID (FK) | Проект |
| `flowsheet_version_id` | UUID (FK) | Версия схемы |
| `created_at` | DateTime | Дата связи |

---

## 3. ER-диаграмма

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  ┌────────┐         ┌──────────────┐         ┌─────────────────┐            │
│  │  User  │────────▶│ProjectMember │◀────────│     Project     │            │
│  └────┬───┘         └──────────────┘         └────────┬────────┘            │
│       │                                               │                      │
│       │                                               │                      │
│       ▼                                               ▼                      │
│  ┌────────────┐                              ┌────────────────┐             │
│  │UserFavorite│                              │   CalcScenario │             │
│  └────────────┘                              └───────┬────────┘             │
│                                                      │                      │
│                                                      ▼                      │
│  ┌────────┐     ┌───────────┐     ┌─────────────────────────────┐          │
│  │ Plant  │────▶│ Flowsheet │────▶│      FlowsheetVersion       │          │
│  └────────┘     └───────────┘     └──────────────┬──────────────┘          │
│                                                   │                         │
│                                                   ▼                         │
│                                            ┌─────────────┐                  │
│                                            │    Unit     │                  │
│                                            └─────────────┘                  │
│                                                                             │
│  ┌─────────────┐     ┌─────────────────┐     ┌─────────────┐               │
│  │   CalcRun   │────▶│ CalcComparison  │     │   Comment   │               │
│  └─────────────┘     └─────────────────┘     └─────────────┘               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Индексы и ограничения

### Рекомендуемые индексы

```sql
-- User
CREATE UNIQUE INDEX ix_user_email ON "user"(email);

-- Project
CREATE INDEX ix_project_owner ON project(owner_user_id);
CREATE INDEX ix_project_plant ON project(plant_id);

-- FlowsheetVersion
CREATE INDEX ix_fv_flowsheet ON flowsheet_version(flowsheet_id);
CREATE INDEX ix_fv_status ON flowsheet_version(status);

-- CalcRun
CREATE INDEX ix_calcrun_project ON calc_run(project_id);
CREATE INDEX ix_calcrun_scenario ON calc_run(scenario_id);
CREATE INDEX ix_calcrun_status ON calc_run(status);
CREATE INDEX ix_calcrun_created ON calc_run(created_at DESC);

-- Unit
CREATE INDEX ix_unit_fv ON unit(flowsheet_version_id);
CREATE INDEX ix_unit_type ON unit(unit_type);
```

### Ограничения

- `User.email` — UNIQUE
- `FlowsheetVersion.version_number` — UNIQUE per flowsheet
- `CalcRun.status` — CHECK IN ('PENDING', 'RUNNING', 'SUCCESS', 'FAILED')
- `ProjectMember.role` — CHECK IN ('OWNER', 'EDITOR', 'VIEWER')

---

## 5. Миграции (Alembic)

Миграции хранятся в `backend/migrations/versions/`.

### Команды

```bash
# Создать новую миграцию
cd backend
alembic revision --autogenerate -m "description"

# Применить миграции
alembic upgrade head

# Откатить последнюю миграцию
alembic downgrade -1

# Показать текущую версию
alembic current
```

---

*Документ обновляется при изменении схемы БД. Последнее обновление: 23 декабря 2025 г.*
