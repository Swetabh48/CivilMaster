"""ProblemSpec and per-topic body models (Pydantic v2, topic discriminator)."""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, model_validator


class Quantity(BaseModel):
    value: float
    unit: str  # pint-parsable, e.g. "kN/m", "mm", "N/mm**2"


class Load(BaseModel):
    kind: Literal["point", "udl", "uvl", "moment"]
    magnitude: Quantity  # uvl: start intensity
    magnitude_end: Quantity | None = None
    position: Quantity | None = None  # point / moment
    start: Quantity | None = None  # distributed
    end: Quantity | None = None


class BeamSpec(BaseModel):
    topic: Literal["beam_analysis"] = "beam_analysis"
    support: Literal["simply_supported", "cantilever", "overhang"]
    span: Quantity
    overhang_left: Quantity | None = None
    overhang_right: Quantity | None = None
    loads: list[Load]
    find: list[
        Literal["reactions", "sfd", "bmd", "max_bm", "max_sf", "contraflexure"]
    ]


class BoltedJointSpec(BaseModel):
    topic: Literal["is800_bolted_joint"] = "is800_bolted_joint"
    joint: Literal["lap", "butt_single_cover", "butt_double_cover"]
    force: Quantity
    force_is_factored: bool
    bolt_dia: Quantity
    bolt_grade: str  # e.g. "4.6"
    plate_thickness: Quantity
    plate_width: Quantity
    steel_grade: str  # e.g. "E250"


class LsmBeamSpec(BaseModel):
    topic: Literal["rcc_lsm_beam"] = "rcc_lsm_beam"
    b: Quantity
    d: Quantity
    Mu: Quantity
    fck: Quantity
    fy: Quantity


class SectionStressSpec(BaseModel):
    topic: Literal["section_bending_stress"] = "section_bending_stress"
    b: Quantity
    d: Quantity
    M: Quantity


class SoilPhaseSpec(BaseModel):
    topic: Literal["soil_phase"] = "soil_phase"
    G: float
    w: float  # water content as decimal or percent — solver interprets
    gamma: Quantity | None = None
    rho: Quantity | None = None

    @model_validator(mode="after")
    def _require_gamma_or_rho(self) -> SoilPhaseSpec:
        if self.gamma is None and self.rho is None:
            raise ValueError("SoilPhaseSpec requires gamma or rho")
        return self


class FormulaLookupSpec(BaseModel):
    """Fallback when no dedicated topic solver applies."""

    topic: Literal["formula_lookup"] = "formula_lookup"
    text: str


ProblemBody = Annotated[
    Union[
        BeamSpec,
        BoltedJointSpec,
        LsmBeamSpec,
        SectionStressSpec,
        SoilPhaseSpec,
        FormulaLookupSpec,
    ],
    Field(discriminator="topic"),
]


class ProblemSpec(BaseModel):
    id: str
    title: str
    question_text: str
    kind: Literal["numerical", "design", "theory", "detailing"]
    body: ProblemBody
    assumptions: list[str] = Field(default_factory=list)
