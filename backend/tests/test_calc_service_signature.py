import inspect

from app.services import calc_service


def test_calc_service_accepts_started_by_user_id_arg():
    params = inspect.signature(calc_service.run_flowsheet_calculation_by_scenario).parameters
    assert "started_by_user_id" in params
