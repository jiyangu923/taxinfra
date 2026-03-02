"""Country skill library — jurisdiction-specific tax rules and logic.

Each country module includes:
- Filing schemas
- Local rules
- Penalty logic
- Safe harbor rules
- Documentation requirements
- E-invoicing standards
- Payment rails
- Regulatory API connectors

This becomes the Tax Intelligence Graph — defensible IP over time.
"""

from taxinfra.countries.base import CountryModule
from taxinfra.countries.registry import CountryRegistry
from taxinfra.countries.us import USModule
from taxinfra.countries.uk import UKModule
from taxinfra.countries.de import DEModule

__all__ = [
    "CountryModule",
    "CountryRegistry",
    "DEModule",
    "UKModule",
    "USModule",
]
