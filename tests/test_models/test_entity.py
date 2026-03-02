"""Tests for entity models."""

from datetime import date
from uuid import uuid4

from taxinfra.models.entity import Entity, EntityRelationship, EntityStructure


def test_entity_creation():
    entity = Entity(name="Acme Corp", country="US", tax_id="12-3456789")
    assert entity.name == "Acme Corp"
    assert entity.country == "US"
    assert entity.is_active is True


def test_entity_structure():
    parent = Entity(name="Parent Corp", country="US")
    child_us = Entity(name="US Sub", country="US")
    child_uk = Entity(name="UK Sub", country="GB")

    structure = EntityStructure(
        entities=[parent, child_us, child_uk],
        relationships=[
            EntityRelationship(
                parent_entity_id=parent.id,
                child_entity_id=child_us.id,
                relationship_type="subsidiary",
                effective_date=date(2020, 1, 1),
            ),
            EntityRelationship(
                parent_entity_id=parent.id,
                child_entity_id=child_uk.id,
                relationship_type="subsidiary",
                ownership_percentage=100.0,
                effective_date=date(2021, 6, 1),
            ),
        ],
    )

    assert structure.get_entity(parent.id) == parent
    assert structure.get_entity(uuid4()) is None

    subs = structure.get_subsidiaries(parent.id)
    assert len(subs) == 2

    us_entities = structure.get_entities_in_country("US")
    assert len(us_entities) == 2

    uk_entities = structure.get_entities_in_country("GB")
    assert len(uk_entities) == 1
    assert uk_entities[0].name == "UK Sub"
