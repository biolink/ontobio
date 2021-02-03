import json
import typing
import collections
import enum
import datetime
import re
import logging

import bidict
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
Date = collections.namedtuple("Date", ["year", "month", "day", "time"])


def ymd_str(date: Date, separator: str) -> str:
    return "{year}{sep}{month}{sep}{day}".format(year=date.year, sep=separator, month=date.month, day=date.day)

@dataclass
class Error:
    info: str
    entity: str = ""

    def is_error(self):
        return True

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

        if " " in namespace or " " in identity:
            return Error("No spaces allowed in CURIEs")

        return Curie(namespace, identity)

    def is_error(self) -> bool:
        return False


@dataclass(unsafe_hash=True)
class Subject:
    id: Curie
    label: str
    """
    label is also `DB_Object_Symbol` in the GPI spec
    """

    fullname: List[str]
    """
    fullname is also `DB_Object_Name` in the GPI spec, cardinality 0+
    """

    synonyms: List[str]
    """
    Cardinality 0+
    """

    type: List[Curie]
    """
    In GPI 1.2, this was a string, corresponding to labels of the Sequence Ontology
    gene, protein_complex; protein; transcript; ncRNA; rRNA; tRNA; snRNA; snoRNA,
    any subclass of ncRNA.
    If the specific type is unknown, use `gene_product`.

    When reading gpi 1.2, these labels should be mapped to the 2.0 spec, stating that
    the type must be a Curie in the Sequence Ontology OR Protein Ontology OR Gene Ontology

    In GPI 1.2, there is only 1 value, and is required.
    In GPI 2.0 there is a minimum of 1, but maybe more.

    If writing out to GPI 1.2/GAF just take the first value in the list.
    """

    taxon: Curie
    """
    Should be NCBITaxon:...
    """

    encoded_by: List[Curie]
    """
    Optional, or cardinality 0+
    """

    parents: List[Curie]
    """
    Optional, or cardinality 0+
    """

    contained_complex_members: List[Curie]
    """
    Optional, or cardinality 0+
    """

    db_xrefs: List[Curie]
    """
    Optional, or cardinality 0+
    """

    properties: Dict[str, str]
    """
    Optional, or cardinality 0+
    """

    def __init__(self, id: Curie, label: str, fullname: List[str], synonyms: List[str], type: Union[List[str], List[Curie]], taxon: Curie,
                    encoded_by: List[Curie]=None, parents: List[Curie]=None, contained_complex_members: List[Curie]=None,
                    db_xrefs: List[Curie]=None, properties: Dict=None):

        if len(type) > 0:
            if isinstance(type[0], str):
                # If the incoming `type` list is strings, then they are labels, so convert to Curie
                self.type = [map_gp_type_label_to_curie(t) for t in type]
            else:
                # We will assume that incoming type is a Curie at this point, if not a string
                self.type = type
        else:
            # If we didn't receive anything, then default to "gene_produce"
            self.type = [Curie(namespace="CHEBI", identity="33695")]

        self.id = id
        self.label = label
        self.fullname = fullname
        self.synonyms = synonyms
        self.taxon = taxon
        self.encoded_by = encoded_by if encoded_by else []
        self.parents = parents if parents else []
        self.contained_complex_members = contained_complex_members if contained_complex_members else []
        self.db_xrefs = db_xrefs if db_xrefs else []
        self.properties = properties if properties else dict()

    def fullname_field(self, max=None) -> str:
        """
        Converts the `fullname` or `DB_Object_Name` into the field text string used in files
        """

        if not max:
            max = len(self.fullname)

        return "|".join([n for n in self.fullname[0:max]])

# ===============================================================================
__default_entity_type_to_curie_mapping = bidict.bidict({
    "protein_coding_gene": Curie.from_str("SO:0001217"),
    "snRNA": Curie.from_str("SO:0000274"),
    "ncRNA": Curie.from_str("SO:0000655"),
    "rRNA": Curie.from_str("SO:0000252"),
    "mRNA": Curie.from_str("SO:0000234"),
    "lnc_RNA": Curie.from_str("SO:0001877"),
    "lincRNA": Curie.from_str("SO:0001463"),
    "tRNA": Curie.from_str("SO:0000253"),
    "snoRNA": Curie.from_str("SO:0000275"),
    "miRNA": Curie.from_str("SO:0000276"),
    "RNA": Curie.from_str("SO:0000356"),
    "scRNA": Curie.from_str("SO:0000013"),
    "piRNA": Curie.from_str("SO:0001035"),
    "tmRNA": Curie.from_str("SO:0000584"),
    "SRP_RNA": Curie.from_str("SO:0000590"),
    "primary_transcript": Curie.from_str("SO:0000185"),
    "ribozyme": Curie.from_str("SO:0000374"),
    "telomerase_RNA": Curie.from_str("SO:0000390"),
    "RNase_P_RNA": Curie.from_str("SO:0000386"),
    "antisense_RNA": Curie.from_str("SO:0000644"),
    "RNase_MRP_RNA": Curie.from_str("SO:0000385"),
    "guide_RNA": Curie.from_str("SO:0000602"),
    "hammerhead_ribozyme": Curie.from_str("SO:0000380"),
    "protein": Curie.from_str("PR:000000001"),
    "marker or uncloned locus": Curie.from_str("SO:0001645"),
    "gene segment": Curie.from_str("SO:3000000"),
    "pseudogene": Curie.from_str("SO:0000336"),
    "gene": Curie.from_str("SO:0000704"),
    "biological region": Curie.from_str("SO:0001411"),
    "protein_complex": Curie.from_str("GO:0032991"),
    "transcript": Curie.from_str("SO:0000673"),
    "gene_product": Curie.from_str("CHEBI:33695"),
    "ncRNA-coding gene": Curie.from_str("SO:0001263"),
    "antisense_lncRNA": Curie.from_str("SO:0001904"),
    "transposable_element_gene": Curie.from_str("SO:0000111")
})

def map_gp_type_label_to_curie(type_label: str) -> Curie:
    """
    Map entity types in GAF or GPI 1.2 into CURIEs in Sequence Ontology (SO),
    Protein Ontology (PRO), or Gene Ontology (GO).

    This is a measure to upgrade the pseudo-labels into proper Curies. Present here are
    the existing set of labels in current use, and how they should be mapped into CURIEs.
    """
    # normalized_label = type_label.translate()
    global __default_entity_type_to_curie_mapping
    return __default_entity_type_to_curie_mapping.get(type_label, __default_entity_type_to_curie_mapping["gene_product"])

def gp_type_label_to_curie(type: Curie) -> str:
    """
    This is the reverse of `map_gp_type_label_to_curie`
    """
    global __default_entity_type_to_curie_mapping
    return __default_entity_type_to_curie_mapping.inverse.get(type, "gene_product")

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

    def is_error(self) -> bool:
        return False

@dataclass(unsafe_hash=True)
class Evidence:
    type: Curie # Curie of the ECO class
    has_supporting_reference: List[Curie]
    with_support_from: List[ConjunctiveSet]


relation_tuple = re.compile(r'([\w]+)\((\w+:[\w][\w\.:\-]*)\)')
curie_relation_tuple = re.compile(r"(.+)\((.+)\)")
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
            rel_curie = relations.obo_uri_to_curie(rel_uri)
            if isinstance(term_curie, Error):
                # print("Error because term is screwed up: {}".format(term))
                return Error("`{}`: {}".format(term, term_curie.info))
            return ExtensionUnit(rel_curie, term_curie)
        else:
            # print("Just couldn't even parse it at all: {}".format(entity))
            return Error(entity)

    @classmethod
    def from_curie_str(ExtensionUnit, entity: str) -> Union:
        """
        Attempts to parse string entity as an ExtensionUnit
        If the `relation(term)` is not formatted correctly, an Error is returned.
        `relation` is a Curie, and so is any errors in formatting are delegated to Curie.from_str()
        """
        parsed = curie_relation_tuple.findall(entity)
        if len(parsed) == 1:
            rel, term = parsed[0]

            rel_curie = Curie.from_str(rel)
            term_curie = Curie.from_str(term)
            if term_curie.is_error():
                return Error("`{}`: {}".format(term, term_curie.info))
            if rel_curie.is_error():
                return Error("`{}`: {}".format(rel, rel_curie.info))
            return ExtensionUnit(rel_curie, term_curie)

        else:
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
        return relations.lookup_uri(relations.curie_to_obo_uri(self.relation))

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
    properties: Dict[str, List[str]]

    def to_gaf_2_1_tsv(self) -> List:
        gp_isoforms = "" if not self.subject_extensions else self.subject_extensions[0].term

        allowed_qualifiers = {"contributes_to", "colocalizes_with"}

        # Curie Object -> CURIE Str -> URI -> Label
        qual_labels = [relations.lookup_uri(curie_util.expand_uri(str(q), strict=False)) for q in self.qualifiers]
        if len(qual_labels) == 1 and qual_labels[0] not in allowed_qualifiers:
            logger.warning("Cannot write qualifier `{}` in GAF version 2.1 since only {} are allowed: skipping".format(self.qualifiers[0], ", ".join(allowed_qualifiers)))
            # If the qualifier is wrong, blank out the qualifiers
            qual_labels = []

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
            self.subject.fullname_field(),
            "|".join(self.subject.synonyms),
            gp_type_label_to_curie(self.subject.type[0]),
            taxon,
            ymd_str(self.date, ""),
            self.provided_by,
            ConjunctiveSet.list_to_str(self.object_extensions,
                conjunct_to_str=lambda conj: conj.display(use_rel_label=True)),
            gp_isoforms
        ]

    def to_gaf_2_2_tsv(self) -> List:
        gp_isoforms = "" if not self.subject_extensions else self.subject_extensions[0].term

        qual_labels = [relations.lookup_uri(curie_util.expand_uri(str(q), strict=False)) for q in self.qualifiers]
        if self.negated:
            qual_labels.insert(0, "NOT")

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
            self.subject.fullname_field(),
            "|".join(self.subject.synonyms),
            gp_type_label_to_curie(self.subject.type[0]),
            taxon,
            ymd_str(self.date, ""),
            self.provided_by,
            ConjunctiveSet.list_to_str(self.object_extensions),
            gp_isoforms
        ]

    def to_gpad_1_2_tsv(self) -> List:

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
            ymd_str(self.date, ""),
            self.provided_by,
            ConjunctiveSet.list_to_str(self.object_extensions,
                conjunct_to_str=lambda conj: conj.display(use_rel_label=True)),
            "|".join(props_list)
        ]

    def to_gpad_2_0_tsv(self) -> List:

        props_list = ["{key}={value}".format(key=key, value=value) for key, value in self.properties.items()]
        return [
            str(self.subject.id),
            "NOT" if self.negated else "",
            str(self.relation),
            str(self.object.id),
            "|".join([str(ref) for ref in self.evidence.has_supporting_reference]),
            str(self.evidence.type),
            ConjunctiveSet.list_to_str(self.evidence.with_support_from),
            str(self.interacting_taxon) if self.interacting_taxon else "",
            ymd_str(self.date, "-"),
            self.provided_by,
            ConjunctiveSet.list_to_str(self.object_extensions,
                conjunct_to_str=lambda conj: conj.display()),
            "|".join(props_list)
        ]

    def to_hash_assoc(self) -> dict:
        subject = {
            "id": str(self.subject.id),
            "label": self.subject.label,
            "type": gp_type_label_to_curie(self.subject.type[0]),
            "fullname": self.subject.fullname[0],
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
            "date": ymd_str(self.date, ""),
            "subject_extensions": subject_extensions,
            "object_extensions": object_extensions
        }

@dataclass
class Header:
    souce_line: Optional[str]
