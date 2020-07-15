import json
import typing
import collections
import enum
import datetime
import re

from ontobio.ecomap import EcoMap
ecomap = EcoMap()
ecomap.mappings()


from typing import List, Optional, NamedTuple, Dict, Callable, Union, TypeVar
from dataclasses import dataclass

Aspect = typing.NewType("Aspect", str)
Provider = typing.NewType("Provider", str)
Date = typing.NewType("Date", str)

@dataclass
class Error:
    info: str

@dataclass
class Curie:
    namespace: str
    identity: str

    def __str__(self) -> str:
        return "{}:{}".format(self.namespace, self.identity)

    @classmethod
    def from_str(Curie, entity: str):
        splitup = entity.rsplit(":", maxsplit=1)
        splitup += [""] * (2 - len(splitup))
        namespace, identity = splitup
        if namespace == "" and identity == "":
            return Error("Namespace and Identity of CURIE is empty")

        if namespace == "":
            return Error("Namespace of CURIE is empty")

        if identity == "":
            return Error("Identity of CURIE is empty")

        return Curie(namespace, identity)


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

C = TypeVar("C")

@dataclass(unsafe_hash=True)
class ConjunctiveSet:
    elements: List

    def __str__(self) -> str:
        return ",".join([str(conj) for conj in self.elements])

    @classmethod
    def list_to_str(ConjunctiveSet, conjunctions: List) -> str:
        """
        List should be a list of ConjunctiveSet
        """
        return "|".join([str(conj) for conj in conjunctions])

    @classmethod
    def str_to_conjunctions(ConjunctiveSet, entity: str, conjunct_element_builder: Union[C, Error]=lambda el: str(el)) -> Union[List[C], Error]:
        """
        Takes a field that conforms to the pipe (|) and comma (,) separator type. The parsed version is a list of pipe separated values
        which are themselves a comma separated list.

        If the elements inside the comma separated list should not just be strings, but be converted into a value of a type, `conjunct_element_builder` can be provided which should take a string and return a parsed value or an instance of an Error type (defined above).

        If there is an error in producing the values of the conjunctions, then this function will return early with the error.

        This function will return a List of ConjunctiveSet
        """
        conjunctions = []
        for conj in filter(None, entity.split("|")):
            conjunct = []
            for el in filter(None, conj.split(",")):
                built = conjunct_element_builder(el)
                if isinstance(built, Error):
                    # Returning an Error instance
                    return built

                conjunct.append(built)

            conjunctions.append(ConjunctiveSet(conjunct))

        return conjunctions

@dataclass
class Evidence:
    type: Curie # Curie of the ECO class
    has_supporting_reference: List[Curie]
    with_support_from: List[ConjunctiveSet]

relation_tuple = re.compile(r'(.+)\((.+)\)')

@dataclass(unsafe_hash=True)
class ExtensionUnit:
    relation: Curie
    term: Curie

    @classmethod
    def from_str(ExtensionUnit, entity: str) -> Union:
        """
        Attempts to parse string entity as an ExtensionUnit
        """
        parsed = relation_tuple.findall(entity)
        if len(parsed) == 1:
            rel, term = parsed[0]
            return ExtensionUnit(rel, term)
        else:
            return Error(entity)

    def __str__(self) -> str:
        return "{relation}({term})".format(relation=self.relation, term=self.term)

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
    object_extensions: List[ConjunctiveSet]
    provided_by: Provider
    date: Date
    properties: Dict[Curie, List[str]]

    def to_gaf_2_1_tsv(self) -> List:
        gp_isoforms = "" if not self.subject_extensions else self.subject_extensions[0].term
        qualifiers = []
        qualifiers.extend([str(q) for q in self.qualifiers])
        if self.negated:
            qualifiers.append("NOT")

        qualifier = "|".join(qualifiers)
        self.object.taxon.namespace = "taxon"
        taxon = str(self.object.taxon)
        if self.interacting_taxon:
            self.interacting_taxon.namespace = "taxon"
            taxon = "{taxon}|{interacting}".format(taxon=taxon, interacting=str(self.interacting_taxon))

        return [
            self.subject.id.namespace,
            self.subject.id.identity,
            self.subject.label,
            qualifier,
            str(self.object.id),
            "|".join([str(ref) for ref in self.evidence.has_supporting_reference]),
            ecomap.ecoclass_to_coderef(str(self.evidence.type))[0],
            ConjunctiveSet.list_to_str(self.evidence.with_support_from),
            self.aspect if self.aspect else "",
            self.subject.fullname,
            "|".join(self.subject.synonyms),
            self.subject.type,
            taxon,
            self.date,
            self.provided_by,
            ConjunctiveSet.list_to_str(self.object_extensions),
            gp_isoforms
        ]

    def to_gaf_2_2_tsv(self) -> List:
        gp_isoforms = "" if not self.subject_extensions else self.subject_extensions[0].term

        allowed_qualifiers = {"contributes_to", "colocalizes_with"}
        if len(self.qualifiers) == 1 and self.qualifiers[0]

        qualifier = "|".join(qualifiers)
        self.object.taxon.namespace = "taxon"
        taxon = str(self.object.taxon)
        if self.interacting_taxon:
            self.interacting_taxon.namespace = "taxon"
            taxon = "{taxon}|{interacting}".format(taxon=taxon, interacting=str(self.interacting_taxon))

        return [
            self.subject.id.namespace,
            self.subject.id.identity,
            self.subject.label,
            qualifier,
            str(self.object.id),
            "|".join([str(ref) for ref in self.evidence.has_supporting_reference]),
            ecomap.ecoclass_to_coderef(str(self.evidence.type))[0],
            ConjunctiveSet.list_to_str(self.evidence.with_support_from),
            self.aspect if self.aspect else "",
            self.subject.fullname,
            "|".join(self.subject.synonyms),
            self.subject.type,
            taxon,
            self.date,
            self.provided_by,
            ConjunctiveSet.list_to_str(self.object_extensions),
            gp_isoforms
        ]

    def to_gpad_tsv(self) -> List:
        db, subid = self.subject.id.split(":", maxsplit=1)
        qualifiers = []
        qualifiers.extend([str(q) for q in self.qualifiers])
        if self.negated:
            qualifiers.append("NOT")

        qualifier = "|".join(qualifiers)

        props_list = ["{key}={value}".format(key=key, value=value) for key, value in self.properties.items()]
        return [
            self.subject.id.namespace,
            self.subject.id.identity,
            qualifier,
            str(self.object.id),
            "|".join([str(ref) for ref in self.evidence.has_supporting_reference]),
            str(self.evidence.type),
            ConjunctiveSet.list_to_str(self.evidence.with_support_from),
            str(self.interacting_taxon) if self.interacting_taxon else "",
            self.date,
            self.provided_by,
            ConjunctiveSet.list_to_str(self.object_extensions),
            "|".join(props_list)
        ]

@dataclass
class Header:
    souce_line: Optional[str]
