# Rate limiting configuration for GrindLab
# Использует slowapi для защиты API от абуза и DDoS

from slowapi import Limiter
from slowapi.util import get_remote_address

# Инициализация лимитера с использованием IP адреса клиента
limiter = Limiter(key_func=get_remote_address)

# Предустановленные лимиты для различных типов операций
RATE_LIMITS = {
    # Расчетные операции (самые дорогостоящие)
    "calc_operations": "10/minute",  # max 10 расчетов в минуту с одного IP
    "flowsheet_run": "10/minute",
    "grind_mvp_run": "10/minute",
    # Операции с данными (средние)
    "scenario_operations": "30/minute",  # max 30 операций в минуту
    "project_operations": "30/minute",
    # Операции чтения (легкие)
    "read_operations": "100/minute",  # max 100 чтений в минуту
    # Аутентификация
    "auth_operations": "20/minute",  # max 20 попыток аутентификации
}

__all__ = ["limiter", "RATE_LIMITS"]
