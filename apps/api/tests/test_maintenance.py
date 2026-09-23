from app.core.maintenance import MaintenanceMiddleware

def test_maintenance_middleware_importable():
    assert MaintenanceMiddleware is not None
