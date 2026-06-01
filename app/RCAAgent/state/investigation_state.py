"""
Investigation State Schema - Manufacturing Domain

Typed dataclasses for passing state between agents in the investigation graph.
Domain: Manufacturing / Quality Assurance
"""

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional, Dict, Any
from enum import Enum


class IncidentType(Enum):
    """Type of event that triggered the investigation."""
    QUALITY_DEVIATION = "quality_deviation"
    COMPLAINT = "complaint"


class LotStatus(Enum):
    """Classification status for lots in the investigation."""
    REFERENCE = "reference"
    STUDY = "study"


class CauseVerdict(Enum):
    """Verification verdict for potential causes."""
    RETAINED = "RETAINED"
    ELIMINATED = "ELIMINATED"


class CauseCategory(Enum):
    """Categories for root cause classification."""
    MATERIAL = "Material"
    EQUIPMENT = "Equipment"
    PROCESS = "Process"
    ENVIRONMENT = "Environment"
    PERSONNEL = "Personnel"


@dataclass
class Incident:
    """Information about what triggered the investigation."""
    type: IncidentType
    reference: str
    description: str
    date_reported: date


@dataclass
class LotInfo:
    """Information about a manufactured lot."""
    lot_number: str
    mfg_date: date
    expiry_date: date
    status: LotStatus


@dataclass
class ProblemDefinition:
    """Output from Step 1: Problem Definition."""
    reference: str
    affected_references: List[str]
    process_step: Optional[str]
    lots: List[LotInfo]
    problem_date: date
    problem: str
    symptom: str

    @property
    def reference_lots(self) -> List[LotInfo]:
        return [lot for lot in self.lots if lot.status == LotStatus.REFERENCE]

    @property
    def study_lots(self) -> List[LotInfo]:
        return [lot for lot in self.lots if lot.status == LotStatus.STUDY]


@dataclass
class PotentialCause:
    """A potential cause identified in Step 2."""
    id: str
    category: CauseCategory
    source: str
    description: str
    evidence_summary: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RootCauseAnalysis:
    """Output from Step 2: Root Cause Analysis."""
    potential_causes: List[PotentialCause]

    @property
    def count(self) -> int:
        return len(self.potential_causes)

    def causes_by_category(self) -> Dict[str, List[PotentialCause]]:
        grouped = {}
        for cause in self.potential_causes:
            cat = cause.category.value
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append(cause)
        return grouped


@dataclass
class VerifiedCause:
    """A cause after verification in Step 3."""
    id: str
    category: CauseCategory
    verdict: CauseVerdict
    evidence: str
    reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_retained(self) -> bool:
        return self.verdict == CauseVerdict.RETAINED

    @property
    def is_eliminated(self) -> bool:
        return self.verdict == CauseVerdict.ELIMINATED


@dataclass
class Verification:
    """Output from Step 3: Verification."""
    verified_causes: List[VerifiedCause]

    @property
    def retained_causes(self) -> List[VerifiedCause]:
        return [c for c in self.verified_causes if c.is_retained]

    @property
    def eliminated_causes(self) -> List[VerifiedCause]:
        return [c for c in self.verified_causes if c.is_eliminated]


@dataclass
class InvestigationState:
    """Complete state of an investigation, passed between agents via the graph."""
    investigation_id: str
    incident: Incident
    problem_definition: Optional[ProblemDefinition] = None
    root_cause_analysis: Optional[RootCauseAnalysis] = None
    verification: Optional[Verification] = None
    error: Optional[str] = None

    def is_complete(self) -> bool:
        return (
            self.problem_definition is not None
            and self.root_cause_analysis is not None
            and self.verification is not None
        )
