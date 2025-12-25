# GrindLab Demo Environment with Docker

Быстрое разворачивание демо-среды с помощью Docker Compose.

---

## 🚀 Quick Start (1 команда)

```bash
# Полный разворот: backend + frontend + demo data
docker-compose up --build

# Результат:
# ✅ Backend:  http://localhost:8000
# ✅ Frontend: http://localhost:5173
# ✅ Demo data: автоматически загружена
```

## 🎯 Что запускается

```
┌─────────────────────────────────────────┐
│ GrindLab Demo Environment               │
├─────────────────────────────────────────┤
│                                          │
│ Frontend (React)                        │
│ http://localhost:5173                   │
│          ↓                               │
│ Backend (FastAPI)                       │
│ http://localhost:8000                   │
│ Swagger: http://localhost:8000/docs    │
│          ↓                               │
│ PostgreSQL (Database)                   │
│ localhost:5432                          │
│                                          │
│ 📊 Demo Data (автоматически):          │
│ ✓ 3 растения                           │
│ ✓ 5 версий схем                        │
│ ✓ 3 проекта                            │
│ ✓ 27 расчётов                          │
│                                          │
└─────────────────────────────────────────┘
```

## 📝 Сценарии использования

### 1️⃣ Презентация клиенту

```bash
# Запустить демо
docker-compose up

# Открыть в браузере
# http://localhost:5173

# Показать:
# 1. Projects page → Тестовый проект 1
# 2. Dashboard → 3 версии, 6 сценариев
# 3. ScenarioComparison → Fact vs Model
# 4. PSD графики
```

### 2️⃣ Разработка новой фичи

```bash
# Запустить backend + frontend + DB
docker-compose up

# Разработчик работает локально (frontend/backend коды в volume-ах)
# Изменения автоматически пересчитываются (hot reload)

# Backend разработка
# Изменения в backend/ → uvicorn перезагружается

# Frontend разработка
# Изменения в frontend/ → vite перезагружается
```

### 3️⃣ Тестирование API

```bash
# Запустить только backend + DB
docker-compose up backend postgres

# Smoke-тесты
curl http://localhost:8000/health
curl http://localhost:8000/api/projects/my
```

### 4️⃣ CI/CD pipeline

```bash
# В GitHub Actions
docker-compose -f docker-compose.yml -f docker-compose.test.yml up
pytest tests/
```

---

## 🔧 Configuration

### Environment переменные

Создайте файл `.env` в корне проекта:

```env
# Backend
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
DATABASE_URL=postgresql://grindlab:grindlab_pw@postgres:5432/grindlab
SECRET_KEY=dev-secret-key-change-in-production

# Frontend
FRONTEND_HOST=0.0.0.0
FRONTEND_PORT=5173
VITE_API_URL=http://localhost:8000

# Database
POSTGRES_USER=grindlab
POSTGRES_PASSWORD=grindlab_pw
POSTGRES_DB=grindlab
```

### Volumes

```yaml
services:
  backend:
    volumes:
      - ./backend:/app              # Hot reload code
      - backend-venv:/app/.venv     # Cache venv

  frontend:
    volumes:
      - ./frontend:/app             # Hot reload code
      - frontend-node:/app/node_modules  # Cache dependencies

  postgres:
    volumes:
      - postgres-data:/var/lib/postgresql/data  # Persist data
```

---

## 📊 Проверка готовности

```bash
# Все сервисы запущены?
docker-compose ps

# Backend здоров?
curl http://localhost:8000/health
# Response: {"status":"ok","service":"grindlab-backend"}

# Frontend доступен?
curl http://localhost:5173
# Response: HTML страница

# Database готова?
docker-compose exec postgres psql -U grindlab -d grindlab -c "SELECT COUNT(*) FROM projects;"
# Response: 3 (три проекта из demo seed)

# API работает?
curl http://localhost:8000/api/projects/my
# Response: [{"id":1,"name":"..."}]
```

---

## 🛑 Остановка и очистка

```bash
# Остановить контейнеры
docker-compose down

# Остановить + удалить volumes (потеря данных!)
docker-compose down -v

# Посмотреть логи
docker-compose logs -f backend     # Backend логи
docker-compose logs -f frontend    # Frontend логи
docker-compose logs -f postgres    # Database логи

# Смотреть все логи в реальном времени
docker-compose logs -f
```

---

## 🔍 Debugging

### Backend логи

```bash
# Просмотр логов backend
docker-compose logs -f backend

# Выполнить команду внутри контейнера
docker-compose exec backend python -c "print('Hello')"

# Interactive shell
docker-compose exec backend bash
```

### Database доступ

```bash
# Подключиться к PostgreSQL
docker-compose exec postgres psql -U grindlab -d grindlab

# SQL запросы
SELECT COUNT(*) FROM projects;
SELECT COUNT(*) FROM calc_runs;
SELECT * FROM users;
```

### Frontend

```bash
# Очистить node_modules (если проблемы)
docker-compose exec frontend rm -rf node_modules package-lock.json
docker-compose up --build frontend

# Просмотр логов
docker-compose logs -f frontend
```

---

## ⚡ Performance

### Рекомендуемые системные требования

```
CPU:    4+ cores
RAM:    8+ GB
Disk:   10 GB (для image-ов и volume-ов)
```

### Оптимизация

```yaml
# docker-compose.yml
services:
  backend:
    # Ограничить память для backend
    mem_limit: 1g

  postgres:
    # Ограничить память для DB
    mem_limit: 2g
```

---

## 🐛 Известные проблемы

### Port занят

```bash
# Найти процесс на порту 8000
lsof -i :8000

# Убить процесс
kill -9 <PID>

# Или использовать другой порт в .env
BACKEND_PORT=8001
```

### Database не инициализирована

```bash
# Пересоздать
docker-compose down -v
docker-compose up postgres

# Ждать initialization (~10 сек)
# Потом запустить backend
docker-compose up backend
```

### Volume permissions (Linux)

```bash
# Если permission denied при создании files

# Вариант 1: Запустить с правильными permissions
docker-compose up --user $(id -u):$(id -g)

# Вариант 2: Исправить ownership
sudo chown -R $(id -u):$(id -g) ./backend ./frontend
```

---

## 📚 Дополнительные ресурсы

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [GrindLab DEMO_SETUP_AND_USAGE.md](DEMO_SETUP_AND_USAGE.md)
- [GrindLab TECH_ROADMAP.md](TECH_ROADMAP.md)

---

## ✅ Чеклист перед презентацией

- [ ] Все образы собраны: `docker-compose build`
- [ ] Контейнеры запущены: `docker-compose up`
- [ ] Backend здоров: `curl http://localhost:8000/health`
- [ ] Frontend доступен: открыть http://localhost:5173
- [ ] Demo data загружена: `curl http://localhost:8000/api/projects/my`
- [ ] Smoke-тесты проходят: `docker-compose exec backend python scripts/smoke_api.py`
- [ ] Нет ошибок в консоли backend и frontend

---

**Последнее обновление: 25 декабря 2025 г.**
