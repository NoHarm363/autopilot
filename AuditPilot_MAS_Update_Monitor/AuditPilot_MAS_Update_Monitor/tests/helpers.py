"""Synthetic model response used only in isolated tests, never runtime data."""
from auditpilot.models import Assessment, Claim

def model_response(source):
    quote = source.text
    return Assessment(summary="Analyst summary: review CDD obligations.", sub_areas=["customer_due_diligence"], risk_level="medium", risk_rationale="Test judgment only", impacted_population="Banks", actual_impact="Not quantified", recommendations=["Human reviewer: review CDD controls"], claims=[Claim(statement=quote, quote=quote)], assessment_method="test-model")
