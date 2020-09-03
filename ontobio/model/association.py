import json
import typing
import collections
import enum
import datetime
import re
import logging

from prefixcommons import curie_util

from ontobio.rdfgen import relations
from ontobio.ecomap import EcoMap

ecomap = EcoMap()
ecomap.mappings()


from typing import List, Optional, NamedTuple, Dict, Callable, Union, TypeVar
from dataclasses import dataclass

logger = logging.getLogger(__name__)


Aspect = typing.NewType("Aspect", str)
Provider = typing.NewType("Provider", str)
Date = typing.NewType("Date", str)

@dataclass
class Error:
    info: str
    entity: str = ""

@dataclass(unsafe_hash=True)
class Curie:
    namespace: str
    identity: str

    def __str__(self) -> str:
        return "{}:{}".format(self.namespace, self.identity)

    @classmethod
    def from_str(Curie, entity: str):
        splitup = entity.split(":", maxsplit=1)
        splitup += [""] * (2 - len(splitup))
        namespace, identity = splitup
        if namespace == "" and identity == "":
            return Error("Namespace and Identity of CURIE is empty")

        if namespace == "":
            return Error("Namespace of CURIE is empty")

        if identity == "":
            return Error("Identity of CURIE is empty")

        return Curie(namespace, identity)


@dataclass(unsafe_hash=True)
class Subject:
    id: Curie
    label: str
    fullname: str
    synonyms: List[str]
    type: str
    taxon: Curie

@dataclass(unsafe_hash=True)
class Term:
    id: Curie
    taxon: Curie

C = TypeVar("C")


@dataclass(unsafe_hash=True)
class ConjunctiveSet:
    """
    The field `elements` can be a list of Curie or ExtensionUnit.
    """
    elements: List

    def __str__(self) -> str:
        return ",".join([str(conj) for conj in self.elements])

    def display(self, conjunct_to_str=lambda c: str(c)) -> str:
        return ",".join([conjunct_to_str(conj) for conj in self.elements])

    @classmethod
    def list_to_str(ConjunctiveSet, conjunctions: List, conjunct_to_str=lambda c: str(c)) -> str:
        """
        List should be a list of ConjunctiveSet
        Given [ConjunctiveSet, ConjunctiveSet]
        """
        return "|".join([conj.display(conjunct_to_str=conjunct_to_str) for conj in conjunctions])

    @classmethod
    def str_to_conjunctions(ConjunctiveSet, entity: str, conjunct_element_builder: Union[C, Error]=lambda el: Curie.from_str(el)) -> Union[List[C], Error]:
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

@dataclass(unsafe_hash=True)
class Evidence:
    type: Curie # Curie of the ECO class
    has_supporting_reference: List[Curie]
    with_support_from: List[ConjunctiveSet]

relation_tuple = re.compile(r'([\w]+)\((\w+:[\w][\w\.:\-]*)\)')
@dataclass(unsafe_hash=True)
class ExtensionUnit:
    relation: Curie
    term: Curie

    @classmethod
    def from_str(ExtensionUnit, entity: str) -> Union:
        """
        Attempts to parse string entity as an ExtensionUnit
        If the `relation(term)` is not formatted correctly, an Error is returned.
        If the `relation` cannot be found in the `relations` dictionary then an error
        is also returned.
        """
        parsed = relation_tuple.findall(entity)
        if len(parsed) == 1:
            rel, term = parsed[0]
            rel_uri = relations.lookup_label(rel)
            if rel_uri is None:
                # print("Error because rel_uri isn't in the file: {}".format(rel))
                return Error(entity)

            term_curie = Curie.from_str(term)
            rel_curie = Curie.from_str(curie_util.contract_uri(rel_uri, strict=False)[0])
            if isinstance(term_curie, Error):
                # print("Error because term is screwed up: {}".format(term))
                return Error("`{}`: {}".format(term, term_curie.info))
            return ExtensionUnit(rel_curie, term_curie)
        else:
            # print("Just couldn't even parse it at all: {}".format(entity))
            return Error(entity)

    def __str__(self) -> str:
        """
        Display Curie(term)
        """
        return self.display()

    def display(self, use_rel_label=False):
        rel = str(self.relation)
        if use_rel_label:
            rel = self.__relation_to_label()

        return "{rel}({term})".format(rel=rel, term=self.term)

    def __relation_to_label(self) -> str:
        # Curie -> expand to URI -> reverse relation lookup Label
        return relations.lookup_uri(curie_util.expand_uri(str(self.relation), strict=False))

    def to_hash(self, use_label=False) -> dict:
        rel = self.__relation_to_label() if use_label else str(self.relation)
        return {
            "property": rel,
            "filler": str(self.term)
        }

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

        allowed_qualifiers = {"contributes_to", "colocalizes_with"}

        # Curie Object -> CURIE Str -> URI -> Label
        qual_labels = [relations.lookup_uri(curie_util.expand_uri(str(q), strict=False)) for q in self.qualifiers]
        if len(qual_labels) == 1 and qual_labels[0] not in allowed_qualifiers:
            logger.error("Cannot write qualifier `{}` in GAF version 2.1 since only {} are allowed: skipping".format(self.qualifiers[0]), ", ".join(allowed_qualifiers))
            return []

        if self.negated:
            qual_labels.append("NOT")

        qualifier = "|".join(qual_labels)

        self.object.taxon.namespace = "taxon"
        taxon = str(self.object.taxon)
        if self.interacting_taxon:
            self.interacting_taxon.namespace = "taxon"
            taxon = "{taxon}|{interacting}".format(taxon=taxon, interacting=str(self.interacting_taxon))

        # For extensions, we provide the to string function on ConjunctElement that
        # calls its `display` method, with the flag to use labels instead of the CURIE.
        # This function is used to turn the whole column correctly into a string
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
            ConjunctiveSet.list_to_str(self.object_extensions,
                conjunct_to_str=lambda conj: conj.display(use_rel_label=True)),
            gp_isoforms
        ]

    def to_gaf_2_2_tsv(self) -> List:
        gp_isoforms = "" if not self.subject_extensions else self.subject_extensions[0].term

        qual_labels = [relations.lookup_uri(curie_util.expand_uri(str(q), strict=False)) for q in self.qualifers]
        if self.negated:
            qual_labels.append("NOT")

        qualifier = "|".join(qual_labels)

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

        # Curie Object -> CURIE Str -> URI -> Label
        qual_labels = [relations.lookup_uri(curie_util.expand_uri(str(q), strict=False)) for q in self.qualifiers]

        # Try qualifiers first since, if we are going from GAF -> GPAD and the GAF had a qualifier, that would be
        # more specific than the relation, which is calculated from the aspect/Go term.
        if qual_labels == []:
            # If there were no qualifiers, then we'll use the Relation. Gpad requires at least one qualifier (which is the relation)
            qual_labels.append(relations.lookup_uri(curie_util.expand_uri(str(self.relation), strict=False)))

        if self.negated:
            qual_labels = ["NOT"] + qual_labels

        qualifier = "|".join(qual_labels)

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
            ConjunctiveSet.list_to_str(self.object_extensions,
                conjunct_to_str=lambda conj: conj.display(use_rel_label=True)),
            "|".join(props_list)
        ]

    def to_hash_assoc(self) -> dict:
        subject = {
            "id": str(self.subject.id),
            "label": self.subject.label,
            "type": self.subject.type,
            "fullname": self.subject.fullname,
            "synonyms": self.subject.synonyms,
            "taxon": {
                "id": str(self.subject.taxon)
            }
        }

        obj = {
            "id": str(self.object.id),
            "taxon": str(self.object.taxon)
        }

        subject_extensions = [{"property": str(subj.relation), "filler": str(subj.term)} for subj in self.subject_extensions]

        disjunctions = []
        for conjset in self.object_extensions:
            conjunctions = []
            for extension in conjset.elements:
                conjunctions.append(extension.to_hash(use_label=True))
            disjunctions.append({"intersection_of": conjunctions})

        object_extensions = {}
        if len(disjunctions) > 0:
            object_extensions["union_of"] = disjunctions

        withfrom_flat = []
        for withfrom in self.evidence.with_support_from:
            for curie in withfrom.elements:
                withfrom_flat.append(str(curie))

        evidence = {
            "type": ecomap.ecoclass_to_coderef(str(self.evidence.type))[0],
            "has_supporting_reference": [str(ref) for ref in self.evidence.has_supporting_reference],
            "with_support_from": withfrom_flat
        }

        return {
            "source_line": self.source_line,
            "subject": subject,
            "object": obj,
            "negated": self.negated,
            "qualifiers": [str(q) for q in self.qualifiers],
            "aspect": self.aspect,
            "relation": {
                "id": str(self.relation)
            },
            "interacting_taxon": self.interacting_taxon,
            "evidence": evidence,
            "provided_by": self.provided_by,
            "date": self.date,
            "subject_extensions": subject_extensions,
            "object_extensions": object_extensions
        }

@dataclass
class Header:
    souce_line: Optional[str]
