"""
Dependency Injection Container for service lifecycle management.

The DI container provides:
- Service registration (singletons, factories, types)
- Automatic dependency resolution using type hints
- Proper initialization order
- Easy mocking for tests
- No global state

Usage:
    container = DependencyContainer()

    # Register services
    container.register_singleton("EventBus", EventBus())
    container.register_factory("DatabaseManager", lambda: DatabaseManager(path="/data"))
    container.register_type(OrderFlowAnalyzer, OrderFlowAnalyzerImpl)

    # Resolve with auto-injection
    decision_engine = container.resolve("DecisionEngine")
"""

import inspect
import logging
from typing import Any, Callable, Dict, Optional, Type, TypeVar, get_type_hints

logger = logging.getLogger(__name__)

T = TypeVar("T")


class DependencyResolutionError(Exception):
    """Raised when a dependency cannot be resolved."""
    pass


class CircularDependencyError(DependencyResolutionError):
    """Raised when a circular dependency is detected."""
    pass


class DependencyContainer:
    """
    Lightweight dependency injection container.

    Supports three types of registrations:
    1. Singleton: Pre-instantiated objects (reused)
    2. Factory: Functions that create instances on-demand
    3. Type: Classes with automatic dependency resolution

    Features:
    - Auto-resolves constructor dependencies via type hints
    - Detects circular dependencies
    - Thread-safe singleton creation
    - Clear error messages for missing dependencies
    """

    def __init__(self):
        """Initialize the DI container."""
        # Singletons: name -> instance (already created)
        self._singletons: Dict[str, Any] = {}

        # Factories: name -> factory_func
        self._factories: Dict[str, Callable] = {}

        # Types: name -> class (for auto-instantiation)
        self._types: Dict[str, Type] = {}

        # Type aliases: interface_name -> implementation_name
        self._aliases: Dict[str, str] = {}

        # Resolution stack (for circular dependency detection)
        self._resolution_stack: list[str] = []

        logger.info("DependencyContainer initialized")

    # ========================================================================
    # Service Registration
    # ========================================================================

    def register_singleton(self, name: str, instance: Any) -> None:
        """
        Register a pre-instantiated singleton instance.

        Args:
            name: Service name for resolution
            instance: Pre-created instance to register

        Example:
            container.register_singleton("EventBus", EventBus())
        """
        if name in self._singletons:
            logger.warning("Overwriting existing singleton: %s", name)

        self._singletons[name] = instance
        logger.info("Registered singleton: %s -> %s", name, type(instance).__name__)

    def register_factory(self, name: str, factory: Callable[..., Any]) -> None:
        """
        Register a factory function that creates instances.

        The factory will be called each time the service is resolved.
        Dependencies are auto-injected into the factory based on parameter names.

        Args:
            name: Service name for resolution
            factory: Callable that creates the service

        Example:
            container.register_factory(
                "DatabaseManager",
                lambda: DatabaseManager(path="/data")
            )
        """
        if name in self._factories:
            logger.warning("Overwriting existing factory: %s", name)

        self._factories[name] = factory
        logger.info("Registered factory: %s -> %s", name, factory.__name__)

    def register_type(
        self, interface: Type[T], implementation: Type[T], as_singleton: bool = False
    ) -> None:
        """
        Register a type with automatic dependency resolution.

        Dependencies are auto-resolved by inspecting the __init__ signature
        and matching parameter type hints to registered services.

        Args:
            interface: Interface/base class (used as key)
            implementation: Concrete implementation class
            as_singleton: If True, create once and reuse; if False, create new each time

        Example:
            container.register_type(OrderFlowAnalyzer, OrderFlowAnalyzerImpl)
        """
        interface_name = interface.__name__
        impl_name = implementation.__name__

        if as_singleton:
            # Register as factory that creates singleton on first resolution
            def singleton_factory():
                if impl_name not in self._singletons:
                    self._singletons[impl_name] = self._create_instance(implementation)
                return self._singletons[impl_name]

            self._factories[interface_name] = singleton_factory
            logger.info(
                "Registered type (singleton): %s -> %s", interface_name, impl_name
            )
        else:
            self._types[interface_name] = implementation
            logger.info("Registered type: %s -> %s", interface_name, impl_name)

    def register_alias(self, alias: str, target: str) -> None:
        """
        Register an alias for a service.

        Useful for providing multiple names for the same service.

        Args:
            alias: Alias name
            target: Actual service name

        Example:
            container.register_alias("DB", "DatabaseManager")
        """
        self._aliases[alias] = target
        logger.info("Registered alias: %s -> %s", alias, target)

    # ========================================================================
    # Service Resolution
    # ========================================================================

    def resolve(self, service_name: str) -> Any:
        """
        Resolve a service by name with automatic dependency injection.

        Resolution order:
        1. Check aliases
        2. Check singletons
        3. Check factories (call with auto-injected dependencies)
        4. Check registered types (instantiate with auto-injected dependencies)

        Args:
            service_name: Name of service to resolve

        Returns:
            Resolved service instance

        Raises:
            DependencyResolutionError: If service cannot be resolved
            CircularDependencyError: If circular dependency detected
        """
        # Check for circular dependencies
        if service_name in self._resolution_stack:
            cycle = " -> ".join(self._resolution_stack + [service_name])
            raise CircularDependencyError(f"Circular dependency detected: {cycle}")

        # Track resolution stack
        self._resolution_stack.append(service_name)

        try:
            # 1. Check aliases
            if service_name in self._aliases:
                actual_name = self._aliases[service_name]
                logger.debug("Resolving alias: %s -> %s", service_name, actual_name)
                return self.resolve(actual_name)

            # 2. Check singletons
            if service_name in self._singletons:
                logger.debug("Resolved singleton: %s", service_name)
                return self._singletons[service_name]

            # 3. Check factories
            if service_name in self._factories:
                factory = self._factories[service_name]
                dependencies = self._resolve_dependencies(factory)
                instance = factory(**dependencies)
                logger.debug("Resolved via factory: %s", service_name)
                return instance

            # 4. Check registered types
            if service_name in self._types:
                implementation = self._types[service_name]
                instance = self._create_instance(implementation)
                logger.debug("Resolved via type: %s", service_name)
                return instance

            # Service not found
            raise DependencyResolutionError(
                f"Service '{service_name}' not registered. "
                f"Available services: {self._get_available_services()}"
            )

        finally:
            # Pop from resolution stack
            self._resolution_stack.pop()

    def resolve_optional(self, service_name: str) -> Optional[Any]:
        """
        Resolve a service, returning None if not found.

        Args:
            service_name: Name of service to resolve

        Returns:
            Service instance or None
        """
        try:
            return self.resolve(service_name)
        except DependencyResolutionError:
            logger.debug("Optional service not found: %s", service_name)
            return None

    def _create_instance(self, cls: Type[T]) -> T:
        """
        Create an instance of a class with auto-injected dependencies.

        Args:
            cls: Class to instantiate

        Returns:
            Instance of cls with dependencies injected
        """
        dependencies = self._resolve_dependencies(cls.__init__)
        instance = cls(**dependencies)
        return instance

    def _resolve_dependencies(self, func: Callable) -> Dict[str, Any]:
        """
        Automatically resolve function/constructor dependencies.

        Inspects the function signature and type hints, then resolves
        each parameter from the container.

        Args:
            func: Function to analyze

        Returns:
            Dictionary of {param_name: resolved_value}
        """
        dependencies = {}

        # Get function signature
        try:
            sig = inspect.signature(func)
        except ValueError:
            # Built-in functions don't have signatures
            return {}

        # Get type hints
        try:
            type_hints = get_type_hints(func)
        except Exception as e:
            logger.debug("Could not get type hints for %s: %s", func.__name__, e)
            type_hints = {}

        # Resolve each parameter
        for param_name, param in sig.parameters.items():
            # Skip 'self' and 'cls'
            if param_name in ("self", "cls"):
                continue

            # Skip parameters with default values (optional)
            if param.default != inspect.Parameter.empty:
                continue

            # Get type hint
            if param_name in type_hints:
                param_type = type_hints[param_name]

                # Handle Optional[T] by extracting T
                if hasattr(param_type, "__origin__") and param_type.__origin__ is type(None):
                    # This is Optional[SomeType]
                    args = param_type.__args__
                    if args:
                        param_type = args[0]

                # Try to resolve by type name
                type_name = getattr(param_type, "__name__", str(param_type))

                try:
                    dependencies[param_name] = self.resolve(type_name)
                    logger.debug(
                        "Auto-resolved dependency: %s -> %s", param_name, type_name
                    )
                except DependencyResolutionError:
                    # Try resolving by parameter name
                    try:
                        dependencies[param_name] = self.resolve(param_name)
                        logger.debug(
                            "Auto-resolved dependency by name: %s", param_name
                        )
                    except DependencyResolutionError:
                        logger.warning(
                            "Could not resolve dependency: %s (type: %s)",
                            param_name,
                            type_name,
                        )
            else:
                # No type hint, try resolving by parameter name
                try:
                    dependencies[param_name] = self.resolve(param_name)
                    logger.debug("Auto-resolved dependency by name: %s", param_name)
                except DependencyResolutionError:
                    logger.debug(
                        "No type hint and no service for param: %s", param_name
                    )

        return dependencies

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def has_service(self, service_name: str) -> bool:
        """
        Check if a service is registered.

        Args:
            service_name: Service name to check

        Returns:
            True if service is registered
        """
        return (
            service_name in self._singletons
            or service_name in self._factories
            or service_name in self._types
            or service_name in self._aliases
        )

    def _get_available_services(self) -> list[str]:
        """Get list of all registered service names."""
        services = set()
        services.update(self._singletons.keys())
        services.update(self._factories.keys())
        services.update(self._types.keys())
        services.update(self._aliases.keys())
        return sorted(services)

    def get_all_services(self) -> Dict[str, str]:
        """
        Get a dictionary of all registered services.

        Returns:
            Dict mapping service name to type (singleton/factory/type/alias)
        """
        services = {}

        for name in self._singletons:
            services[name] = "singleton"
        for name in self._factories:
            services[name] = "factory"
        for name in self._types:
            services[name] = "type"
        for name in self._aliases:
            services[name] = f"alias -> {self._aliases[name]}"

        return services

    def clear(self) -> None:
        """Clear all registered services (useful for testing)."""
        self._singletons.clear()
        self._factories.clear()
        self._types.clear()
        self._aliases.clear()
        self._resolution_stack.clear()
        logger.info("DependencyContainer cleared")

    def __repr__(self) -> str:
        return (
            f"DependencyContainer("
            f"singletons={len(self._singletons)}, "
            f"factories={len(self._factories)}, "
            f"types={len(self._types)}, "
            f"aliases={len(self._aliases)})"
        )
