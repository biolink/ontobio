"""
MME request object, see
https://github.com/ga4gh/mme-apis/blob/87f615/search-api.md
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class Sex(str, Enum):
    FEMALE = 'FEMALE'
    MALE = 'MALE'
    OTHER = 'OTHER'
    MIXED_SAMPLE = 'MIXED_SAMPLE'
    NOT_APPLICABLE = 'NOT_APPLICABLE'


class Observed(str, Enum):
    yes = 'yes'
    no = 'no'

@dataclass
class Contact:
    name: str = None
    institution:  str = None
    href:  str = None
    email: str = None
    roles: List[str] = field(default_factory=list)

@dataclass
class Patient:
    id: str
    label: str = None
    contact: Contact = None

@dataclass
class Disorder:
    id: str
    label: str = None


@dataclass
class Feature:
    id: str
    label: str = None
    observed: Observed = Observed.yes
    ageOfOnset: str = None


@dataclass
class Gene:
    id: str


@dataclass
class Variant:
    assembly: str
    referenceName: str
    start: int
    end: int = None
    referenceBases: str = None
    alternateBases: str = None


@dataclass
class GenomicFeatureType:
    id: str
    label: str = None


@dataclass
class GenomicFeature:
    gene: Gene
    variant: Variant = None
    zygosity: int = None
    type: GenomicFeatureType = None


@dataclass
class MmeRequest:
    id: str
    label: str = None
    disclaimer: str = None
    contact: Contact = None
    terms: str = None
    patient: Patient = None
    species: str = None
    sex: Sex = None,
    ageOfOnset: str = None,
    inheritanceMode: str = None,
    disorders: List[Disorder] = field(default_factory=list)
    features: List[Feature] = field(default_factory=list)
    genomicFeatures: List[GenomicFeature] = field(default_factory=list)
    test: bool = False

    def __post_init__(self):
        if not self.features and not self.genomicFeatures:
            raise ValueError("Request must container either features or genomicFeatures")
