"""Simple drawing intermediate representation (primitives + Drawing container)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union


@dataclass
class Line:
    x1: float
    y1: float
    x2: float
    y2: float
    stroke: str = "#1c2430"
    stroke_width: float = 1.5
    dash: str | None = None


@dataclass
class Polyline:
    points: list[tuple[float, float]]
    stroke: str = "#1c2430"
    stroke_width: float = 1.5
    fill: str = "none"
    closed: bool = False
    dash: str | None = None


@dataclass
class Circle:
    cx: float
    cy: float
    r: float
    stroke: str = "#1c2430"
    stroke_width: float = 1.5
    fill: str = "none"


@dataclass
class Text:
    x: float
    y: float
    content: str
    font_size: float = 12
    fill: str = "#1c2430"
    anchor: str = "start"  # start | middle | end
    font_family: str = "IBM Plex Sans, sans-serif"


@dataclass
class Arrow:
    x1: float
    y1: float
    x2: float
    y2: float
    stroke: str = "#1c2430"
    stroke_width: float = 1.5
    head_size: float = 8


@dataclass
class Dimension:
    """Linear dimension between two points with offset label."""

    x1: float
    y1: float
    x2: float
    y2: float
    label: str
    offset: float = 18
    stroke: str = "#5a6573"
    stroke_width: float = 1.0
    font_size: float = 11


Primitive = Union[Line, Polyline, Circle, Text, Arrow, Dimension]


@dataclass
class Drawing:
    width: float
    height: float
    elements: list[Primitive] = field(default_factory=list)
    title: str = "Diagram"
    background: str = "#f7f6f2"

    def add(self, *elems: Primitive) -> None:
        self.elements.extend(elems)
