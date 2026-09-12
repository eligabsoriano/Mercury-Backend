"""
backend/routers/predictions.py
==============================
REST API endpoints for real-time churn prediction, counterfactual "what-if"
interventions, and model transparency.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, Path
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas.prediction import (
    ChurnPredictionInput,
    ChurnPredictionResult,
    CounterfactualSimulationRequest,
    CounterfactualSimulationResponse,
    ModelMetadataResponse,
)
from backend.services.prediction_service import PredictionService

router = APIRouter(prefix="/api/predictions", tags=["Predictions"])


def get_prediction_service() -> PredictionService:
    """Dependency provider for the singleton PredictionService."""
    return PredictionService.get_instance()


@router.post(
    "/churn",
    response_model=ChurnPredictionResult,
    summary="Real-Time Churn Prediction",
    description=(
        "Score customer behavioral features in real time using the active trained ML pipeline. "
        "Returns predicted churn probability P(Churn), risk tier, monetary value, revenue at risk, "
        "and top feature contribution factors."
    ),
)
def predict_churn(
    payload: ChurnPredictionInput = Body(
        ...,
        description="Customer behavioral and transactional features to score",
        examples=[
            {
                "lifetime_spend": 320.50,
                "lifetime_orders": 2,
                "avg_delivery_delay_days": 4.5,
                "avg_review_score": 2.0,
                "segment": "At Risk",
            }
        ],
    ),
    service: PredictionService = Depends(get_prediction_service),
) -> ChurnPredictionResult:
    return service.predict(payload)


@router.post(
    "/churn/simulate",
    response_model=CounterfactualSimulationResponse,
    summary="Counterfactual 'What-If' Simulation",
    description=(
        "Simulate operational interventions (e.g. carrier expediting, satisfaction recovery) "
        "against an arbitrary customer baseline. Returns before-and-after metrics, probability deltas, "
        "saved revenue at risk, and risk tier transitions."
    ),
)
def simulate_counterfactual(
    payload: CounterfactualSimulationRequest = Body(
        ...,
        description="Baseline feature payload (or customer ID) with operational adjustments to evaluate",
        examples=[
            {
                "base_features": {
                    "lifetime_spend": 450.0,
                    "lifetime_orders": 2,
                    "avg_delivery_delay_days": 7.0,
                    "avg_review_score": 2.0,
                    "segment": "At Risk",
                },
                "adjustments": {
                    "avg_delivery_delay_days": 0.0,
                    "avg_review_score": 5.0,
                },
            }
        ],
    ),
    db: Session = Depends(get_db),
    service: PredictionService = Depends(get_prediction_service),
) -> CounterfactualSimulationResponse:
    if payload.customer_unique_id:
        return service.simulate_customer(
            customer_unique_id=payload.customer_unique_id,
            adjustments=payload.adjustments,
            db=db,
        )

    base = payload.base_features or ChurnPredictionInput()
    return service.simulate_counterfactual(
        base_features=base,
        adjustments=payload.adjustments,
    )


@router.post(
    "/churn/simulate/{customer_unique_id}",
    response_model=CounterfactualSimulationResponse,
    summary="Customer-Specific Counterfactual Simulation",
    description=(
        "Hydrate baseline features for an existing customer from mart.mart_customer_metrics, "
        "apply operational adjustments (e.g. expediting delivery or upgrading review score), "
        "and calculate exact churn reduction and protected revenue."
    ),
)
def simulate_customer_counterfactual(
    customer_unique_id: str = Path(
        ..., description="Unique customer identifier (customer_unique_id)"
    ),
    adjustments: Dict[str, Any] = Body(
        ...,
        description="Key-value dictionary of feature adjustments to simulate",
        examples=[{"avg_delivery_delay_days": 0.0, "avg_review_score": 4.5}],
    ),
    db: Session = Depends(get_db),
    service: PredictionService = Depends(get_prediction_service),
) -> CounterfactualSimulationResponse:
    return service.simulate_customer(
        customer_unique_id=customer_unique_id,
        adjustments=adjustments,
        db=db,
    )


@router.get(
    "/model/info",
    response_model=ModelMetadataResponse,
    summary="Model Runtime Metadata & Metrics",
    description=(
        "Retrieve runtime metadata, feature lists, training timestamp, and test cohort evaluation metrics "
        "(ROC-AUC, PR-AUC, F1-Score, Precision, Recall, Precision@Top 10%) for the active serving model."
    ),
)
def get_model_info(
    service: PredictionService = Depends(get_prediction_service),
) -> ModelMetadataResponse:
    return service.get_model_info()
