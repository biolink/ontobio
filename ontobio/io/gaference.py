import re
import enum
import json


from dataclasses import dataclass
from typing import NewType, List, Dict
from prefixcommons import curie_util

from ontobio.model import association
from ontobio.rdfgen import relations

import logging

prefix_context = {key: value for context in curie_util.default_curie_maps + [curie_util.read_biocontext("go_context")] for key, value in context.items()}

aspect_relation_map = {
    "F": "http://purl.obolibrary.org/obo/RO_0002327",
    "P": "http://purl.obolibrary.org/obo/RO_0002331",
    "C": "http://purl.obolibrary.org/obo/BFO_0000050"
}

relation_aspect_map = {
    "http://purl.obolibrary.org/obo/RO_0002327": "F",
    "http://purl.obolibrary.org/obo/RO_0002326": "F",
    "http://purl.obolibrary.org/obo/RO_0002264": "P",
    "http://purl.obolibrary.org/obo/RO_0004032": "P",
    "http://purl.obolibrary.org/obo/RO_0004033": "P",
    "http://purl.obolibrary.org/obo/RO_0002263": "P",
    "http://purl.obolibrary.org/obo/RO_0004034": "P",
    "http://purl.obolibrary.org/obo/RO_0004035": "P",
    "http://purl.obolibrary.org/obo/RO_0002331": "P",
    "http://purl.obolibrary.org/obo/BFO_0000050": "C",
    "http://purl.obolibrary.org/obo/RO_0002432": "C",
    "http://purl.obolibrary.org/obo/RO_0002325": "C"
}

Uri = NewType("Uri", str)
Gaf = NewType("Gaf", List)

# This goes like:
# Turn gaferencer json into Dict[AnnotationKey, InferenceValue]
# For a gaf line: gaf --> List[AnnotationKey]
# Use gaferencer dict x gaf annotation key --> List[InferenceValue]
# gaf x gaferencer --> List[Inferences] --> List[gaf]

@dataclass(unsafe_hash=True)
class RelationTo:
    relation: Uri
    term: Uri

@dataclass(unsafe_hash=True)
class AnnotationKey:
    relation_to: RelationTo
    taxon: Uri
    extension: association.ExtensionConjunctions

@dataclass(unsafe_hash=True)
class InferenceValue:
    satisfiable: bool
    taxon_problem: bool
    inferences: List[RelationTo]

ProblemType = enum.Enum("ProblemType", {"TAXON": "taxon", "EXTENSION": "extension"})


@dataclass
class InferenceResult:
    inferred_gafs: List[Gaf]
    problem: ProblemType
    

def load_gaferencer_inferences_from_file(gaferencer_out) -> Dict[AnnotationKey, InferenceValue]:
    
    gaferencer_out_dict = dict()
    try:
        logging.warning("gaferencer_out = {}".format(gaferencer_out))
        with open(gaferencer_out) as gaferencer_file:
            gaferencer_out_dict = json.load(gaferencer_file)
    except Exception as e:
        logging.warning("Could not load file {}: {}".format(gaferencer_out, str(e)))
        return None
        
    return build_annotation_inferences(gaferencer_out_dict)


def build_annotation_inferences(gaferencer_out: List[Dict]) -> Dict[AnnotationKey, InferenceValue]:
    inferences = dict()  # type Dict[AnnotationKey, InferenceValue]
    for gaference in gaferencer_out:
        key = AnnotationKey(
            RelationTo(
                gaference["annotation"]["annotation"]["relation"],
                gaference["annotation"]["annotation"]["term"]),
            gaference["annotation"]["taxon"],
            make_conjunctions(gaference["annotation"]["extension"])
        )
        value = InferenceValue(
            gaference["satisfiable"],
            gaference["taxonProblem"],
            [RelationTo(inf["relation"], inf["term"]) for inf in gaference["inferences"]]
        )
        inferences[key] = value
    return inferences

def produce_inferences(gaf: Gaf, inference_table: Dict[AnnotationKey, InferenceValue]) -> List:
    keys = make_keys_from_gaf(gaf)  # type: List[AnnotationKey]
    results = []  # type: List[InferenceResult]
    for key in keys:
        inferred_value = inference_table.get(key, None)
        if inferred_value != None:
            inferred_gafs_result = gaf_inferences_from_value(gaf, inferred_value)  # type: InferenceResult
            results.append(inferred_gafs_result)

    return results

def lookup_relation(label):
    label = label.replace('_', ' ')

    # Return the cached label -> URI or None
    if label in relations.label_relation_lookup():
        return relations.label_relation_lookup()[label]
    else:
        return None

def make_conjunctions(extension: List) -> association.ExtensionConjunctions:
    extension_units = []  # type: List[association.ExtensionUnit]
    for unit in extension:
        extension_units.append(association.ExtensionUnit(unit["relation"], unit["term"]))

    return association.ExtensionConjunctions(frozenset(extension_units))

relation_tuple = re.compile(r"(.+)\((.+)\)")
def make_keys_from_gaf(gaf: List[str]) -> List[AnnotationKey]:

    term = curie_util.expand_uri(gaf[4], cmaps=[prefix_context])
    relation = aspect_relation_map[gaf[8]]
    taxon = "http://purl.obolibrary.org/obo/NCBITaxon_{}".format(gaf[12].split("|")[0].split(":")[1])
    extension = gaf[15]

    annotation_keys = []  # type: List[AnnotationKey]
    for conjunction in extension.split("|"):
        # conjunction is foo(bar),hello(world)
        conjunctions = []  # type: List[association.ExtensionUnit]
        for extension_unit in conjunction.split(","):
            # extension_unit is foo(bar)
            found_rel = relation_tuple.match(extension_unit)
            if found_rel:
                rel_label, filler = found_rel.groups()
                ext_relation = lookup_relation(rel_label)  # type: Uri
                fill_id = curie_util.expand_uri(filler, cmaps=[prefix_context])  # type: Uri
                extension_unit = association.ExtensionUnit(ext_relation, fill_id)  # type: association.ExtensionUnit
                # Append the extensions unit to the list of conjunctions
                conjunctions.append(extension_unit)

        extension_conjunction = association.ExtensionConjunctions(frozenset(conjunctions))
        # Build the Key now
        annotation_keys.append(AnnotationKey(RelationTo(relation, term), taxon, extension_conjunction))

    return annotation_keys


def gaf_inferences_from_value(original_gaf: Gaf, inferred_value: InferenceValue) -> InferenceResult:
    # This can be successful, where we materialize more than one inference gafs
    # Or it can go wrong, where it's not satisfiable via taxon problems or wrong extensions
    if not inferred_value.satisfiable:
        # Then it's bad
        problem = ProblemType.TAXON if inferred_value.taxon_problem else ProblemType.EXTENSION
        return InferenceResult([], problem)

    # At this point it has inferences
    inferred_gafs = []  # type: List[Gaf]
    for inference in inferred_value.inferences:
        new_gaf = list(original_gaf)
        goterm = inference.term.rsplit("/", maxsplit=1)[1].replace("_", ":")
        aspect = relation_aspect_map[inference.relation]
        new_gaf[4] = goterm
        new_gaf[8] = aspect
        new_gaf[15] = ""
        inferred_gafs.append(new_gaf)

    return InferenceResult(inferred_gafs, None)
