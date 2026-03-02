"""Tests for the explainability module."""

from taxinfra.core.explainability import Decision, DecisionLog, RuleReference


def test_decision_recording():
    log = DecisionLog()

    decision = Decision(
        agent_name="planning_agent",
        decision_type="tax_rate_determination",
        question="What VAT rate applies to SaaS in Germany?",
        conclusion="Standard rate of 19% applies",
        reasoning_steps=[
            "SaaS is classified as electronically supplied service",
            "B2C: buyer's country rules apply (DE)",
            "Standard rate applies — no reduced rate for digital services",
        ],
        rules_applied=[
            RuleReference(
                rule_id="de_ust_12_1",
                jurisdiction="DE",
                regulation_name="UStG § 12 Abs. 1",
                summary="Standard rate of 19%",
            )
        ],
        requires_human_review=False,
    )

    log.record(decision)
    assert len(log.decisions) == 1

    results = log.get_decisions(agent_name="planning_agent")
    assert len(results) == 1
    assert results[0].conclusion == "Standard rate of 19% applies"


def test_pending_reviews():
    log = DecisionLog()

    log.record(
        Decision(
            agent_name="compliance_agent",
            decision_type="filing_generation",
            question="Generate Q1 filing?",
            conclusion="Draft filing created",
            requires_human_review=True,
            human_review_reason="All filings require approval",
        )
    )
    log.record(
        Decision(
            agent_name="compliance_agent",
            decision_type="rate_lookup",
            question="What rate?",
            conclusion="19%",
            requires_human_review=False,
        )
    )

    pending = log.get_pending_reviews()
    assert len(pending) == 1
    assert pending[0].decision_type == "filing_generation"


def test_decision_query_by_entity():
    log = DecisionLog()

    log.record(
        Decision(
            agent_name="test",
            decision_type="test",
            question="q",
            conclusion="c",
            entity_type="filing",
            entity_id="f1",
        )
    )
    log.record(
        Decision(
            agent_name="test",
            decision_type="test",
            question="q",
            conclusion="c",
            entity_type="transaction",
            entity_id="t1",
        )
    )

    results = log.get_decisions_for_entity("filing", "f1")
    assert len(results) == 1
