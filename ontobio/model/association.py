import json
import typing
import collections
import enum
import datetime

from typing import List, Optional, NamedTuple, Dict
from dataclasses import dataclass

Aspect = typing.NewType("Aspect", str)
Curie = typing.NewType("Curie", str)
Provider = typing.NewType("Provider", str)
Date = typing.NewType("Date", str)

@dataclass
class Subject:
    id: Curie
    label: str
    type: str
    fullname: str
    synonyms: List[str]
    taxon: Curie

@dataclass
class Term:
    id: Curie
    taxon: Curie

@dataclass
class Evidence:
    type: Curie # Curie of the ECO class
    has_supporting_reference: List[Curie]
    with_support_from: List[Curie]

@dataclass
class ExtensionUnit:
    relation: Curie
    term: Curie

@dataclass
class ExtensionConjunctions:
    extensions: List[ExtensionUnit]

@dataclass
class ExtensionExpression:
    """
    ExtensionExpression ::= ConjunctionExpression { "|" ConjunctionExpression }
    ConjunctionExpression ::= ExtensionUnit { "," ExtensionUnit }
    ExtensionUnit ::= Relation "(" Term ")"
    """
    conjunctions: List[ExtensionConjunctions]

@dataclass(repr=True, unsafe_hash=True)
class GoAssociation:
    source_line: Optional[str]
    subject: Subject
    relation: Curie # This is the relation Curie
    object: Term
    negated: bool
    qualifiers: List[Curie]
    aspect: Optional[Aspect]
    interacting_taxon: Optional[Curie]
    evidence: Evidence
    subject_extensions: List[ExtensionUnit]
    object_extensions: ExtensionExpression
    provided_by: Provider
    date: Date
    properties: Dict[Curie, List[str]]
