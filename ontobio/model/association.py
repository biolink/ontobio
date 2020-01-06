import json
import typing
import collections
import enum
import datetime

from ontobio.ecomap import EcoMap
ecomap = EcoMap()
ecomap.mappings()


from typing import List, Optional, NamedTuple, Dict, Callable
from dataclasses import dataclass

Aspect = typing.NewType("Aspect", str)
Curie = typing.NewType("Curie", str)
Provider = typing.NewType("Provider", str)
Date = typing.NewType("Date", str)

@dataclass
class Subject:
    id: Curie
    label: str
    fullname: str
    synonyms: List[str]
    type: str
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

@dataclass(unsafe_hash=True)
class ExtensionUnit:
    relation: Curie
    term: Curie

    def __str__(self) -> str:
        return "{relation}({term})".format(relation=self.relation, term=self.term)

@dataclass(unsafe_hash=True)
class ExtensionConjunctions:
    extensions: List[ExtensionUnit]

    def __str__(self) -> str:
        return ",".join([str(conj) for conj in self.extensions])

@dataclass
class ExtensionExpression:
    """
    ExtensionExpression ::= ConjunctionExpression { "|" ConjunctionExpression }
    ConjunctionExpression ::= ExtensionUnit { "," ExtensionUnit }
    ExtensionUnit ::= Relation "(" Term ")"
    """
    conjunctions: List[ExtensionConjunctions]

    def __str__(self) -> str:
        return "|".join([str(conjunction) for conjunction in self.conjunctions])

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

    def to_gaf_tsv(self) -> List:
        gp_isoforms = "" if not self.subject_extensions else self.subject_extensions[0].term
        db, subid = self.subject.id.split(":", maxsplit=1)
        qualifier = "|".join(self.qualifiers)
        if self.negated:
            qualifier = "NOT|{}".format(qualifier)

        taxon = self.object.taxon.replace("NCBITaxon", "taxon")
        if self.interacting_taxon:
            taxon = "{taxon}|{interacting}".format(taxon=taxon, interacting=self.interacting_taxon)

        return [
            db,
            subid,
            self.subject.label,
            qualifier,
            self.object.id,
            "|".join(self.evidence.has_supporting_reference),
            ecomap.ecoclass_to_coderef(self.evidence.type)[0],
            "|".join(self.evidence.with_support_from),
            self.aspect if self.aspect else "",
            self.subject.fullname,
            "|".join(self.subject.synonyms),
            self.subject.type,
            taxon,
            self.date,
            self.provided_by,
            str(self.object_extensions),
            gp_isoforms
        ]

    def to_gpad_tsv(self) -> List:
        db, subid = self.subject.id.split(":", maxsplit=1)
        qualifiers = "|".join(self.qualifiers)
        if self.negated:
            qualifiers = "NOT|{}".format(qualifiers)

        props_list = ["{key}={value}".format(key=key, value=value) for key, value in self.properties.items()]
        return [
            db,
            subid,
            qualifiers,
            self.object.id,
            "|".join(self.evidence.has_supporting_reference),
            self.evidence.type,
            "|".join(self.evidence.with_support_from),
            self.interacting_taxon if self.interacting_taxon else "",
            self.date,
            self.provided_by,
            str(self.object_extensions),
            "|".join(props_list)
        ]
