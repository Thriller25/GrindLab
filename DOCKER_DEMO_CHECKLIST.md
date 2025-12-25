# Docker Demo Checklist

## Предусловия
- [ ] Docker Desktop установлен
- [ ] Docker Desktop запущен (в системном трее)
- [ ] Git repository клонирован/обновлён

## Проверка окружения
```powershell
# Проверить Docker
docker --version
docker ps

# Проверить что находитесь в корне репо
cd GrindLab
ls docker-compose.demo.yml
```

## Запуск демо

### Вариант 1: Windows (рекомендуется)
```powershell
# Из корня репо
scripts\demo-up.bat

# Или PowerShell
docker-compose -f docker-compose.demo.yml up --build
```

### Вариант 2: Linux/macOS
```bash
./scripts/demo-up.sh
```

### Вариант 3: Прямой Docker Compose (все ОС)
```bash
docker-compose -f docker-compose.demo.yml up --build
```

## Примерный вывод при успешном запуске
```
[+] Running 3/3
 ✔ Container grindlab-demo-db       Started (PostgreSQL)
 ✔ Container grindlab-demo-backend  Started
 ✔ Container grindlab-demo-frontend Started

[demo] Creating database tables...
[demo] Tables created.
[demo] Seeding demo data...
[OK] Demo plants, flowsheets, and versions created successfully.
[OK] Demo projects created successfully.
[OK] Demo grind_mvp_v1 runs created successfully.
[demo] Starting backend...
INFO:     Application startup complete
```

## Открыть приложение
- Frontend: http://localhost:5173
- Backend API: http://localhost:8001
- Health: http://localhost:8001/health

## Проверка UI (быстро)
- [ ] Зайти в проект с расчётами ("Тестовый проект 1")
- [ ] KPI-графики рендерятся; режимы "Все расчёты" / "Базовый vs Лучший" переключаются
- [ ] Фильтр по версии схемы меняет данные на графиках
- [ ] Деталь расчёта: PSD-графики отображаются, есть P80/P50 (Fact vs Model)

## Мониторинг
```powershell
# Логи backend (в новой вкладке PowerShell)
docker-compose -f docker-compose.demo.yml logs backend -f

# Логи frontend
docker-compose -f docker-compose.demo.yml logs frontend -f

# Все логи
docker-compose -f docker-compose.demo.yml logs -f
```

## Остановка
```powershell
# Graceful shutdown (данные сохраняются)
Ctrl+C

# Полная остановка
docker-compose -f docker-compose.demo.yml down

# Очистка всего (включая БД)
docker-compose -f docker-compose.demo.yml down -v
```

## Решение проблем

### "docker: command not found"
- Docker Desktop не установлен или не в PATH
- Перезагрузитесь после установки

### "Connection refused на http://localhost:8001"
- Backend ещё стартует (ждите 15+ секунд)
- Проверьте логи: `docker-compose -f docker-compose.demo.yml logs backend`

### "Port already in use"
```powershell
# Найти и убить процессы на портах
netstat -ano | findstr ":8001\|:5173"
taskkill /PID <PID> /F

# или просто пересоздать контейнеры
docker-compose -f docker-compose.demo.yml down -v
docker-compose -f docker-compose.demo.yml up --build
```

### "Cannot connect to Docker daemon"
- Docker Desktop не запущен
- Запустите Docker Desktop из меню Пуск

### Образы занимают много места
```powershell
# Очистить неиспользуемые образы
docker image prune -a

# Очистить всё (контейнеры, образы, волюмы)
docker system prune -a --volumes
```

## Типичные сценарии

### Разработка (изменяем код бэкенда)
```powershell
# Пересоздать и пересобрать
docker-compose -f docker-compose.demo.yml down
docker-compose -f docker-compose.demo.yml up --build
```

### Очистить БД, оставить контейнеры
```powershell
docker volume rm grindlab-demo-db
docker-compose -f docker-compose.demo.yml up
```

### Запустить в фоновом режиме
```powershell
docker-compose -f docker-compose.demo.yml up -d
# Остановить: docker-compose -f docker-compose.demo.yml down
```

### Посмотреть запущенные контейнеры
```powershell
docker ps
# или
docker-compose -f docker-compose.demo.yml ps
```
