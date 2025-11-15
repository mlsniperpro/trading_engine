"""
Unit tests for the DependencyContainer.

Tests:
- Service registration (singleton, factory, type)
- Dependency resolution
- Auto-injection
- Circular dependency detection
- Error handling
"""

import pytest
from src.core.di_container import (
    DependencyContainer,
    DependencyResolutionError,
    CircularDependencyError,
)


# ============================================================================
# Test Services (Mock Classes)
# ============================================================================

class DatabaseConnection:
    """Mock database connection."""

    def __init__(self, connection_string: str = "mock://localhost"):
        self.connection_string = connection_string
        self.connected = True


class CacheService:
    """Mock cache service."""

    def __init__(self, host: str = "localhost", port: int = 6379):
        self.host = host
        self.port = port


class DataRepository:
    """Mock repository with dependencies."""

    def __init__(self, database: DatabaseConnection, cache: CacheService):
        self.database = database
        self.cache = cache


class OrderService:
    """Mock service with dependencies."""

    def __init__(self, repository: DataRepository):
        self.repository = repository


class NotificationService:
    """Mock notification service."""

    def __init__(self, api_key: str = "test_key"):
        self.api_key = api_key


# Circular dependency example
class ServiceA:
    def __init__(self, service_b: "ServiceB"):
        self.service_b = service_b


class ServiceB:
    def __init__(self, service_a: ServiceA):
        self.service_a = service_a


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def container():
    """Create a fresh dependency container for each test."""
    return DependencyContainer()


@pytest.fixture
def configured_container():
    """Create a container with pre-configured services."""
    container = DependencyContainer()

    # Register singletons
    db = DatabaseConnection(connection_string="test://db")
    container.register_singleton("DatabaseConnection", db)

    # Register factories
    container.register_factory("CacheService", lambda: CacheService(host="cache-server"))

    # Register types
    container.register_type(DataRepository, DataRepository)

    return container


# ============================================================================
# Basic Registration Tests
# ============================================================================

def test_register_singleton(container):
    """Test registering a singleton instance."""
    db = DatabaseConnection()
    container.register_singleton("DatabaseConnection", db)

    # Resolve should return same instance
    resolved = container.resolve("DatabaseConnection")
    assert resolved is db
    assert resolved.connected


def test_register_factory(container):
    """Test registering a factory function."""
    container.register_factory("DatabaseConnection", lambda: DatabaseConnection("factory://db"))

    # Resolve should create new instance via factory
    resolved = container.resolve("DatabaseConnection")
    assert isinstance(resolved, DatabaseConnection)
    assert resolved.connection_string == "factory://db"


def test_register_type(container):
    """Test registering a type with auto-instantiation."""
    container.register_type(DatabaseConnection, DatabaseConnection)

    # Resolve should create new instance
    resolved = container.resolve("DatabaseConnection")
    assert isinstance(resolved, DatabaseConnection)


def test_register_alias(container):
    """Test registering an alias for a service."""
    db = DatabaseConnection()
    container.register_singleton("DatabaseConnection", db)
    container.register_alias("DB", "DatabaseConnection")

    # Resolve via alias
    resolved = container.resolve("DB")
    assert resolved is db


# ============================================================================
# Auto-Injection Tests
# ============================================================================

def test_auto_injection_simple(container):
    """Test auto-injection of simple dependencies."""
    # Register dependencies
    db = DatabaseConnection()
    cache = CacheService()
    container.register_singleton("DatabaseConnection", db)
    container.register_singleton("CacheService", cache)

    # Register type that requires dependencies
    container.register_type(DataRepository, DataRepository)

    # Resolve - should auto-inject dependencies
    repo = container.resolve("DataRepository")
    assert isinstance(repo, DataRepository)
    assert repo.database is db
    assert repo.cache is cache


def test_auto_injection_nested(container):
    """Test auto-injection of nested dependencies."""
    # Register all dependencies
    db = DatabaseConnection()
    cache = CacheService()
    container.register_singleton("DatabaseConnection", db)
    container.register_singleton("CacheService", cache)
    container.register_type(DataRepository, DataRepository)

    # Register service with nested dependency
    container.register_type(OrderService, OrderService)

    # Resolve - should auto-inject all nested dependencies
    order_service = container.resolve("OrderService")
    assert isinstance(order_service, OrderService)
    assert isinstance(order_service.repository, DataRepository)
    assert order_service.repository.database is db


def test_factory_with_dependencies(container):
    """Test factory function with auto-injected dependencies."""
    db = DatabaseConnection()
    cache = CacheService()
    container.register_singleton("DatabaseConnection", db)
    container.register_singleton("CacheService", cache)

    # Factory that requires dependencies
    def create_repository(database: DatabaseConnection, cache: CacheService) -> DataRepository:
        return DataRepository(database, cache)

    container.register_factory("DataRepository", create_repository)

    # Resolve - factory should receive dependencies
    repo = container.resolve("DataRepository")
    assert isinstance(repo, DataRepository)
    assert repo.database is db
    assert repo.cache is cache


# ============================================================================
# Singleton vs Factory Behavior Tests
# ============================================================================

def test_singleton_returns_same_instance(container):
    """Test singletons return the same instance."""
    db = DatabaseConnection()
    container.register_singleton("DatabaseConnection", db)

    # Multiple resolves should return same instance
    resolved1 = container.resolve("DatabaseConnection")
    resolved2 = container.resolve("DatabaseConnection")

    assert resolved1 is resolved2
    assert resolved1 is db


def test_factory_returns_new_instances(container):
    """Test factories return new instances each time."""
    container.register_factory("DatabaseConnection", lambda: DatabaseConnection())

    # Multiple resolves should return different instances
    resolved1 = container.resolve("DatabaseConnection")
    resolved2 = container.resolve("DatabaseConnection")

    assert resolved1 is not resolved2
    assert isinstance(resolved1, DatabaseConnection)
    assert isinstance(resolved2, DatabaseConnection)


def test_type_returns_new_instances(container):
    """Test type registration returns new instances each time."""
    container.register_type(DatabaseConnection, DatabaseConnection)

    # Multiple resolves should return different instances
    resolved1 = container.resolve("DatabaseConnection")
    resolved2 = container.resolve("DatabaseConnection")

    assert resolved1 is not resolved2


def test_register_type_as_singleton(container):
    """Test registering type as singleton."""
    container.register_type(DatabaseConnection, DatabaseConnection, as_singleton=True)

    # Multiple resolves should return same instance
    resolved1 = container.resolve("DatabaseConnection")
    resolved2 = container.resolve("DatabaseConnection")

    assert resolved1 is resolved2


# ============================================================================
# Error Handling Tests
# ============================================================================

def test_resolve_unregistered_service(container):
    """Test resolving unregistered service raises error."""
    with pytest.raises(DependencyResolutionError) as exc_info:
        container.resolve("NonExistentService")

    assert "not registered" in str(exc_info.value)


def test_circular_dependency_detection(container):
    """Test circular dependencies are detected."""
    # Register services with circular dependency
    container.register_type(ServiceA, ServiceA)
    container.register_type(ServiceB, ServiceB)

    # Resolving should detect circular dependency
    with pytest.raises(CircularDependencyError) as exc_info:
        container.resolve("ServiceA")

    assert "Circular dependency" in str(exc_info.value)


def test_missing_dependency_error(container):
    """Test error when required dependency is missing."""
    # Register service that requires DatabaseConnection
    container.register_type(DataRepository, DataRepository)

    # Resolve without registering dependencies
    # Should raise error (though may create empty instance with optional params)
    with pytest.raises(DependencyResolutionError):
        container.resolve("DataRepository")


# ============================================================================
# Utility Method Tests
# ============================================================================

def test_has_service(container):
    """Test checking if service is registered."""
    assert not container.has_service("DatabaseConnection")

    container.register_singleton("DatabaseConnection", DatabaseConnection())
    assert container.has_service("DatabaseConnection")


def test_get_all_services(container):
    """Test getting all registered services."""
    db = DatabaseConnection()
    container.register_singleton("DatabaseConnection", db)
    container.register_factory("CacheService", lambda: CacheService())
    container.register_type(DataRepository, DataRepository)
    container.register_alias("DB", "DatabaseConnection")

    services = container.get_all_services()

    assert "DatabaseConnection" in services
    assert services["DatabaseConnection"] == "singleton"
    assert "CacheService" in services
    assert services["CacheService"] == "factory"
    assert "DataRepository" in services
    assert services["DataRepository"] == "type"
    assert "DB" in services
    assert "alias" in services["DB"]


def test_clear(container):
    """Test clearing all services."""
    container.register_singleton("DatabaseConnection", DatabaseConnection())
    container.register_factory("CacheService", lambda: CacheService())

    assert container.has_service("DatabaseConnection")
    assert container.has_service("CacheService")

    container.clear()

    assert not container.has_service("DatabaseConnection")
    assert not container.has_service("CacheService")


def test_resolve_optional(container):
    """Test resolving optional service returns None if not found."""
    # Service not registered
    result = container.resolve_optional("NonExistentService")
    assert result is None

    # Service registered
    db = DatabaseConnection()
    container.register_singleton("DatabaseConnection", db)
    result = container.resolve_optional("DatabaseConnection")
    assert result is db


# ============================================================================
# Integration Tests
# ============================================================================

def test_full_dependency_graph(container):
    """Test resolving complex dependency graph."""
    # Setup full dependency graph
    db = DatabaseConnection(connection_string="production://db")
    cache = CacheService(host="prod-cache", port=6380)

    container.register_singleton("DatabaseConnection", db)
    container.register_singleton("CacheService", cache)
    container.register_type(DataRepository, DataRepository)
    container.register_type(OrderService, OrderService)

    # Resolve top-level service
    order_service = container.resolve("OrderService")

    # Verify entire graph
    assert isinstance(order_service, OrderService)
    assert isinstance(order_service.repository, DataRepository)
    assert order_service.repository.database is db
    assert order_service.repository.cache is cache
    assert cache.host == "prod-cache"
    assert cache.port == 6380


def test_override_existing_service(container):
    """Test overriding an existing service registration."""
    # Register initial service
    db1 = DatabaseConnection(connection_string="db1")
    container.register_singleton("DatabaseConnection", db1)

    assert container.resolve("DatabaseConnection") is db1

    # Override with new service
    db2 = DatabaseConnection(connection_string="db2")
    container.register_singleton("DatabaseConnection", db2)

    # Should resolve to new service
    assert container.resolve("DatabaseConnection") is db2
    assert container.resolve("DatabaseConnection") is not db1


def test_container_repr(container):
    """Test container string representation."""
    container.register_singleton("DB", DatabaseConnection())
    container.register_factory("Cache", lambda: CacheService())
    container.register_type(DataRepository, DataRepository)

    repr_str = repr(container)

    assert "DependencyContainer" in repr_str
    assert "singletons=1" in repr_str
    assert "factories=1" in repr_str
    assert "types=1" in repr_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
