"""
backend/schemas/prediction.py
=============================
Pydantic v2 models for real-time ML inference, counterfactual "what-if"
simulations, and model introspection metadata.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChurnPredictionInput(BaseModel):
    """
    Input feature payload for real-time churn prediction.
    Key operational levers have sensible default baselines so clients can
    supply partial feature subsets (e.g. from UI sliders) without manual imputation.
    """

    customer_lifespan_days: Optional[float] = Field(
        120.0, ge=0.0, description="Customer tenure in days between first and last purchase"
    )
    lifetime_orders: Optional[int] = Field(
        1, ge=1, description="Total count of delivered orders placed"
    )
    is_repeat_buyer: Optional[int] = Field(
        0, ge=0, le=1, description="Binary flag indicating >= 2 lifetime orders"
    )
    lifetime_spend: float = Field(
        150.0, ge=0.0, description="Total gross expenditure including items and freight (BRL)"
    )
    lifetime_product_spend: Optional[float] = Field(
        130.0, ge=0.0, description="Total expenditure on product items excluding freight (BRL)"
    )
    lifetime_freight_spend: Optional[float] = Field(
        20.0, ge=0.0, description="Total freight shipping expenditure (BRL)"
    )
    freight_ratio: Optional[float] = Field(
        0.1333, ge=0.0, le=1.0, description="Freight fees as fraction of total lifetime spend"
    )
    avg_order_value: Optional[float] = Field(
        150.0, ge=0.0, description="Average order value across delivered purchases (BRL)"
    )
    lifetime_items: Optional[int] = Field(1, ge=1, description="Total product line items purchased")
    avg_items_per_order: Optional[float] = Field(
        1.0, ge=1.0, description="Average number of items per delivered order"
    )
    total_unique_products_purchased: Optional[int] = Field(
        1, ge=1, description="Distinct product catalog IDs purchased"
    )
    total_unique_sellers_contacted: Optional[int] = Field(
        1, ge=1, description="Distinct merchant sellers purchased from"
    )
    avg_delivery_delay_days: float = Field(
        0.0,
        description="Average carrier delivery delay in days (+ = late, - = ahead of estimate)",
    )
    max_delivery_delay_days: Optional[float] = Field(
        0.0, description="Maximum single-order delivery delay in days"
    )
    late_orders_count: Optional[int] = Field(
        0, ge=0, description="Total number of orders delivered past estimated date"
    )
    late_order_ratio: Optional[float] = Field(
        0.0, ge=0.0, le=1.0, description="Proportion of orders delivered late"
    )
    has_late_delivery: Optional[int] = Field(
        0, ge=0, le=1, description="Binary flag indicating whether any order was late"
    )
    total_reviews_submitted: Optional[int] = Field(
        1, ge=0, description="Total customer satisfaction surveys submitted"
    )
    avg_review_score: float = Field(
        4.0, ge=1.0, le=5.0, description="Mean star rating given across review surveys (1 to 5)"
    )
    negative_reviews_count: Optional[int] = Field(
        0, ge=0, description="Count of reviews rated 1 or 2 stars"
    )
    positive_reviews_count: Optional[int] = Field(
        1, ge=0, description="Count of reviews rated 4 or 5 stars"
    )
    has_negative_review: Optional[int] = Field(
        0,
        ge=0,
        le=1,
        description="Binary flag indicating whether customer submitted 1-2 star reviews",
    )
    negative_review_ratio: Optional[float] = Field(
        0.0, ge=0.0, le=1.0, description="Ratio of negative reviews to total reviews"
    )
    f_score: Optional[int] = Field(
        1, ge=1, le=5, description="RFM Frequency quintile score (1 to 5)"
    )
    m_score: Optional[int] = Field(
        3, ge=1, le=5, description="RFM Monetary quintile score (1 to 5)"
    )
    segment: Optional[str] = Field("New Customers", description="RFM customer segment name")


class FeatureContribution(BaseModel):
    """Explains an individual feature's impact on the churn probability prediction."""

    feature: str = Field(..., description="Feature column identifier")
    value: Any = Field(..., description="Input feature value evaluated")
    direction: str = Field(
        ..., description="Direction of impact: 'increases_risk', 'decreases_risk', or 'neutral'"
    )
    description: str = Field(..., description="Human-readable explanation of risk influence")


class ChurnPredictionResult(BaseModel):
    """Comprehensive real-time churn prediction response with financial exposure."""

    churn_probability: float = Field(
        ..., ge=0.0, le=1.0, description="Predicted churn probability P(Churn) in [0.0000, 1.0000]"
    )
    risk_tier: str = Field(
        ..., description="Risk tier: High (>=0.70), Medium (0.30-0.70), Low (<0.30)"
    )
    monetary_value: float = Field(
        ..., ge=0.0, description="Customer lifetime spend evaluated (BRL)"
    )
    revenue_at_risk: float = Field(
        ..., ge=0.0, description="Expected financial exposure = P(Churn) * monetary_value (BRL)"
    )
    retention_priority: str = Field(
        ..., description="Action priority from the Decision Matrix (Priority 1 through 4)"
    )
    top_feature_contributions: List[FeatureContribution] = Field(
        default_factory=list, description="Top positive and negative risk contributors"
    )


class CounterfactualSimulationRequest(BaseModel):
    """
    Request schema for simulating 'what-if' operational adjustments against a customer baseline.
    Provide either an inline `base_features` payload or a `customer_unique_id` to hydrate from DB.
    """

    customer_unique_id: Optional[str] = Field(
        None, description="Optional customer unique ID to hydrate baseline features from DB"
    )
    base_features: Optional[ChurnPredictionInput] = Field(
        None,
        description="Baseline feature payload. If omitted, customer_unique_id must be provided.",
    )
    adjustments: Dict[str, Any] = Field(
        ...,
        description=(
            "Key-value dictionary of operational adjustments to simulate. "
            "Example: {'avg_delivery_delay_days': 0.0, 'avg_review_score': 5.0}"
        ),
    )


class CounterfactualSimulationResponse(BaseModel):
    """Comparative outcome delta showing before-and-after simulation metrics."""

    customer_unique_id: Optional[str] = Field(
        None, description="Customer unique ID if hydrated from database"
    )
    baseline: ChurnPredictionResult = Field(
        ..., description="Baseline prediction before applying adjustments"
    )
    simulated: ChurnPredictionResult = Field(
        ..., description="Simulated prediction after applying adjustments"
    )
    delta_churn_probability: float = Field(
        ..., description="Change in P(Churn): simulated - baseline (negative = risk reduction)"
    )
    delta_revenue_at_risk: float = Field(
        ...,
        description="Change in Revenue at Risk: simulated - baseline (negative = financial savings)",
    )
    risk_tier_transition: str = Field(
        ..., description="Risk tier transition indicator (e.g. 'High -> Medium')"
    )
    retention_priority_transition: str = Field(
        ..., description="Retention priority transition indicator (e.g. 'Priority 1 -> Priority 2')"
    )
    impact_summary: str = Field(
        ..., description="Natural-language executive summary of the simulated intervention"
    )


class ModelMetadataResponse(BaseModel):
    """Metadata, feature schema, and evaluation metrics for the active serving model."""

    model_name: str = Field(..., description="Active machine-learning classifier algorithm")
    trained_at: Optional[str] = Field(
        None, description="Timestamp when model artifact was serialized"
    )
    window_days: int = Field(..., description="Time-bounded churn window in days (default 90)")
    numeric_features: List[str] = Field(..., description="List of numeric feature column names")
    categorical_features: List[str] = Field(
        ..., description="List of categorical feature column names"
    )
    eval_metrics: Dict[str, float] = Field(
        ...,
        description="Test cohort evaluation metrics (ROC-AUC, PR-AUC, F1, Precision, Recall, P@10%)",
    )
