import json
import typing
import collections
import enum
import datetime

from typing import List, Optional, NamedTuple

# Note: This requires python 3.7

Subject = collections.namedtuple("Subject", ["id", "label", "type", "fullname", "synonyms", "taxon"])
Term = collections.namedtuple("Term", ["id", "taxon"])
Aspect = enum.Enum("Aspect", {
    "F": "F",
    "P": "P",
    "C": "C"
    })
Curie = typing.NewType("Curie", str)

class Evidence(NamedTuple):
    type: Curie # Curie of the ECO class
    has_supporting_reference: List[Curie]
    with_support_from: List[Curie]

class ExtensionUnit(NamedTuple):
    relation: Curie
    term: Curie

class ExtensionConjunctions(NamedTuple):
    extensions: List[ExtensionUnit]

class ExtensionExpression(NamedTuple):
    """
    ExtensionExpression ::= ConjunctionExpression { "|" ConjunctionExpression }
    ConjunctionExpression ::= ExtensionUnit { "," ExtensionUnit }
    ExtensionUnit ::= Relation "(" Term ")"
    """
    conjunctions: List[ExtensionConjunctions]

@dataclass(repr=False, unsafe_hash=True)
class Association:
    source_line: str
    subject: Subject
    relation: Curie # This is the relation Curie
    object: Term
    negated: bool
    qualifiers: List[str]
    aspect: Aspect
    interacting_taxon: Optional[Curie]
    evidence: Evidence
    subject_extensions: List[ExtensionUnit]
    object_extensions: ExtensionExpression
    provided_by: str
    date: datetime.datetime
    properties: Dict[Curie, List[str]]

    def __repr__(self):
        return self.source_line
