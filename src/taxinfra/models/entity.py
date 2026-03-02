"""Entity models — the legal entities that participate in tax activity."""

from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Entity(BaseModel):
    """A legal entity (company, subsidiary, branch) in the corporate structure."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    legal_name: str = ""
    entity_type: str = ""  # e.g. "corporation", "llc", "branch", "pe"
    country: str  # ISO 3166-1 alpha-2
    tax_id: str = ""  # VAT number, EIN, etc.
    registration_number: str = ""
    incorporation_date: date | None = None
    fiscal_year_end: str = "12-31"  # MM-DD

    # Tax registrations by jurisdiction
    tax_registrations: dict[str, str] = Field(default_factory=dict)

    # Address
    address_line_1: str = ""
    address_line_2: str = ""
    city: str = ""
    state_province: str = ""
    postal_code: str = ""

    is_active: bool = True


class EntityRelationship(BaseModel):
    """A relationship between two entities (parent-subsidiary, branch, etc.)."""

    parent_entity_id: UUID
    child_entity_id: UUID
    relationship_type: str  # "subsidiary", "branch", "pe", "joint_venture"
    ownership_percentage: float = 100.0
    effective_date: date
    end_date: date | None = None


class EntityStructure(BaseModel):
    """The full corporate entity structure — a tree of entities and relationships."""

    entities: list[Entity] = Field(default_factory=list)
    relationships: list[EntityRelationship] = Field(default_factory=list)

    def get_entity(self, entity_id: UUID) -> Entity | None:
        for entity in self.entities:
            if entity.id == entity_id:
                return entity
        return None

    def get_subsidiaries(self, parent_id: UUID) -> list[Entity]:
        child_ids = {
            r.child_entity_id
            for r in self.relationships
            if r.parent_entity_id == parent_id and r.end_date is None
        }
        return [e for e in self.entities if e.id in child_ids]

    def get_entities_in_country(self, country: str) -> list[Entity]:
        return [e for e in self.entities if e.country == country and e.is_active]
