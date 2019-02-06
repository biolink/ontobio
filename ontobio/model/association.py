import json
import typing
import collections
import enum
import datetime

from typing import List, Optional, NamedTuple, Dict
from dataclasses import dataclass


# why named tuple and not a class?
Subject = collections.namedtuple("Subject", ["id", "label", "type", "fullname", "synonyms", "taxon"])
Term = collections.namedtuple("Term", ["id", "taxon"])

# this should be kept general for the general association class
Aspect = enum.Enum("Aspect", {
    "F": "F",
    "P": "P",
    "C": "C"
    })
Curie = typing.NewType("Curie", str)
Provider = typing.NewType("Provider", str)
Date = typing.NewType("Date", str) ## actual datetime object is false precision

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

class Association(NamedTuple):
    source_line: str
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

    def __str__(self):
        return self.source_line
