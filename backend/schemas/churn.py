"""
backend/schemas/churn.py
========================
Pydantic schemas for churn predictions, risk tiers, and revenue-at-risk priorities.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Union
from pydantic import BaseModel, ConfigDict, Field


class ChurnPrediction(BaseModel):
    """Customer-level churn probability, risk tier, and expected revenue at risk."""

    model_config = ConfigDict(from_attributes=True)

    customer_unique_id: str = Field(..., description="Unique returning customer identifier")
    is_churned: int = Field(..., description="Observed ground truth inactivity label (1=churned, 0=active)")
    churn_probability: float = Field(..., ge=0.0, le=1.0, description="Predicted probability of churn P(Churn)")
    risk_tier: str = Field(..., description="Categorical risk tier: High (>=0.70), Medium (0.30-0.70), Low (<0.30)")
    monetary_value: float = Field(..., ge=0.0, description="Customer lifetime spend in BRL (R$)")
    revenue_at_risk: float = Field(..., ge=0.0, description="Expected monetary revenue at risk P(Churn) * monetary_value")
    retention_priority: str = Field(..., description="Decision matrix retention action group")
    predicted_at: Optional[Union[datetime, str]] = Field(None, description="Timestamp of inference generation")


class RiskTierSummary(BaseModel):
    """Portfolio breakdown aggregated by churn risk tier."""

    model_config = ConfigDict(from_attributes=True)

    risk_tier: str = Field(..., description="Risk tier: High, Medium, Low")
    customer_count: int = Field(..., ge=0, description="Number of customers in this risk tier")
    percentage: float = Field(..., ge=0.0, le=100.0, description="Percentage of customer portfolio")
    total_revenue_at_risk: float = Field(..., ge=0.0, description="Sum of expected revenue at risk in BRL")
    avg_churn_probability: float = Field(..., ge=0.0, le=1.0, description="Mean predicted churn probability")


class RetentionPrioritySummary(BaseModel):
    """Portfolio breakdown aggregated by retention priority action."""

    model_config = ConfigDict(from_attributes=True)

    retention_priority: str = Field(..., description="Strategic retention priority action")
    customer_count: int = Field(..., ge=0, description="Number of customers assigned to this priority")
    percentage: float = Field(..., ge=0.0, le=100.0, description="Percentage of customer portfolio")
    total_revenue_at_risk: float = Field(..., ge=0.0, description="Total revenue at risk tied to this action group")
