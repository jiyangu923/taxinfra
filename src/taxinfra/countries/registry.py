"""Country registry — manages available country modules."""

from __future__ import annotations

from taxinfra.countries.base import CountryModule


class CountryRegistry:
    """Registry of country modules. Provides lookup and discovery."""

    def __init__(self) -> None:
        self._modules: dict[str, CountryModule] = {}

    def register(self, module: CountryModule) -> None:
        """Register a country module."""
        self._modules[module.country_code] = module

    def get(self, country_code: str) -> CountryModule | None:
        """Get a country module by code."""
        return self._modules.get(country_code)

    def list_countries(self) -> list[str]:
        """List all registered country codes."""
        return sorted(self._modules.keys())

    def has_country(self, country_code: str) -> bool:
        """Check if a country module is registered."""
        return country_code in self._modules

    @classmethod
    def create_default(cls) -> CountryRegistry:
        """Create a registry with all built-in country modules."""
        from taxinfra.countries.de import DEModule
        from taxinfra.countries.uk import UKModule
        from taxinfra.countries.us import USModule

        registry = cls()
        registry.register(USModule())
        registry.register(UKModule())
        registry.register(DEModule())
        return registry
