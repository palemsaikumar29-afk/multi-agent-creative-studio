"""Typed contracts for the Creative Studio pipeline."""
from __future__ import annotations

from pydantic import BaseModel, Field


class CreativeBrief(BaseModel):
    product: str = Field(min_length=2)
    description: str = Field(min_length=10)
    audience: str = Field(min_length=2)
    tone: str = "friendly"
    variants: int = Field(default=3, ge=1, le=6)


class CopyVariant(BaseModel):
    tagline: str
    ad_copy: str
    cta: str


class VisualAsset(BaseModel):
    prompt: str
    path: str
    provider: str  # pollinations | dalle | placeholder


class Critique(BaseModel):
    copy_score: float = Field(ge=0.0, le=10.0)
    visual_score: float = Field(ge=0.0, le=10.0)
    notes: list[str] = Field(default_factory=list)
    approved: bool = False


class CampaignBundle(BaseModel):
    brief: CreativeBrief
    copies: list[CopyVariant]
    visuals: list[VisualAsset]
    critique: Critique
    campaign_plan: str
