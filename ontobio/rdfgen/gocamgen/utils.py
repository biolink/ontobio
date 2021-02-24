from os import path
import json
import yaml
import logging
import requests
from typing import List
from ontobio.rdfgen.assoc_rdfgen import prefix_context
from ontobio.rdfgen.gocamgen.errors import ShexException
from ontobio.model.association import Curie
from prefixcommons.curie_util import expand_uri, contract_uri
from pyshexc.parser_impl import generate_shexj

logger = logging.getLogger(__name__)


def expand_uri_wrapper(id):
    uri = expand_uri(id, cmaps=[prefix_context])
    return uri


def contract_uri_wrapper(id):
    uri = contract_uri(id, cmaps=[prefix_context])
    return uri


def sort_terms_by_ontology_specificity(terms: List[Curie]):
    # Used primarily for sorting occurs_in annotation extensions
    # What's first? EMAPA or UBERON? Shouldn't matter for extensions since assertion
    # should chain occurs_in to both EMAPA and UBERON (They would be split into separate assertions or thrown out)
    ONTOLOGY_ORDER = {'SO': 1, 'GO': 2, 'CL': 3, 'WBbt': 4, 'EMAPA': 5, 'UBERON': 6}  # From most specific to most general
    terms.sort(key=lambda t: ONTOLOGY_ORDER[t.namespace])

    return terms


class ShexHelper:
    def __init__(self):
        self.shapes = None

    def load_shapes(self):
        self.shapes = {}
        shapes_to_load = ["ProteinContainingComplex", "MolecularFunction", "CellularComponent", "BiologicalProcess",
                          "AnatomicalEntity", "InformationBiomacromolecule"]
        
        shex_url = "https://raw.githubusercontent.com/geneontology/go-shapes/master/shapes/go-cam-shapes.shex"
        shex_response = requests.get(shex_url)
        shex_raw = shex_response.text
        shex_json_str = generate_shexj.parse(shex_raw)._as_json_dumps()
        full_shex_ds = json.loads(shex_json_str)
        for shape in full_shex_ds["shapes"]:
            shape_name = path.basename(shape["id"])
            if shape_name in shapes_to_load:
                self.shapes[shape_name] = {}
                shexps = shape.get('shapeExprs')
                if shexps is None:
                    shexps = [shape]
                for shexp in shexps:
                    if isinstance(shexp, dict) and 'expression' in shexp:
                        for exp in shexp['expression']['expressions']:
                            if exp['type'] == 'TripleConstraint':
                                predicate = contract_uri_wrapper(exp['predicate'])[0]
                                self.shapes[shape_name][predicate] = []
                                values = exp['valueExpr']
                                if isinstance(values, dict):
                                    values = values['shapeExprs']
                                else:
                                    values = [values]
                                for v in values:
                                    # path.basename(v) - Gets the Shape name minus the URL prefix
                                    # E.g. -
                                    self.shapes[shape_name][predicate].append(path.basename(v))
                del self.shapes[shape_name]["rdf:type"]
        # TODO: Get this into ShEx spec or delete this when we decide against it
        self.shapes["CellularComponent"]["BFO:0000050"].append("CellularComponent")  # CC-part_of->CC

    # Try to minimize replication of ShEx structure/logic since it ideally should be centralized elsewhere
    def shape_from_class(self, class_term, go_aspector):
        complex_term = "GO:0032991"
        # TODO: Can we pull these root terms for shape from spec?
        shape_map = {
            complex_term: "ProteinContainingComplex",
            "GO:0003674": "MolecularFunction",
            "GO:0005575": "CellularComponent",
            "GO:0008150": "BiologicalProcess",
            "CARO:0000000": "AnatomicalEntity",
        }
        aspect = go_aspector.go_aspect(class_term)
        if aspect == "C":
            # Oh great, now we gotta look further into the ontology
            # TODO: ensure reflexive=True in all ancestors calls in ontobio.util.go_utils.get_ancestors_through_subont()
            if complex_term in go_aspector.get_isa_closure(class_term) + [class_term]:
                return shape_map[complex_term]
            else:
                return shape_map["GO:0005575"]
        elif aspect == "F":
            return shape_map["GO:0003674"]
        elif aspect == "P":
            return shape_map["GO:0008150"]
        else:
            return shape_map["CARO:0000000"]

    def relation_lookup(self, subj_shape, obj_shape):
        # Well, crud. Guess we're gunna do this:
        if self.shapes is None:
            self.load_shapes()
        # This will screw up the CC->AnatomicalEntity relations
        # <CellularComponent> @<GoCamEntity> AND EXTRA a {
        #   a ( @<CellularComponentClass> OR @<NegatedCellularComponentClass> ) {1};
        #   part_of: @<AnatomicalEntity> {0,1};
        #   adjacent_to: @<AnatomicalEntity> *;
        #   overlaps: @<AnatomicalEntity> *;
        obj_shapes = [obj_shape]
        if obj_shape == "CellularComponent":
            # Add AnatomicalEntity for CC. Should first look for specific CC matches then check for AnatomicalEntity.
            obj_shapes.append("AnatomicalEntity")
        for relation, allowable_obj_shapes in self.shapes[subj_shape].items():
            for obs in obj_shapes:
                if obs in allowable_obj_shapes:
                    return relation
        # Oh no, we couldn't find a relation. This is a no-go for this model.
        shex_error_message = "No relation found in ShEx for {}->{}".format(subj_shape, obj_shape)
        logger.warning(shex_error_message)
        # Throw Exception and except-skip in model builder
        raise ShexException(shex_error_message)


class GroupsHelper:
    def __init__(self, go_site_branch=None):
        self.groups = None
        self.go_site_branch = go_site_branch
        if go_site_branch is None:
            self.go_site_branch = "master"

    def load_groups(self):
        self.groups = {}
        groups_yaml_url = "https://raw.githubusercontent.com/geneontology/go-site/{}/metadata/groups.yaml".format(self.go_site_branch)
        groups_yaml_response = requests.get(groups_yaml_url)
        groups_yaml_str = groups_yaml_response.text
        groups_list = yaml.load(groups_yaml_str, Loader=yaml.FullLoader)
        for g in groups_list:
            shorthand = g["shorthand"]
            gid = g["id"]
            self.groups[shorthand] = gid

    def lookup_group_id(self, group_name):
        if self.groups is None:
            self.load_groups()
        return self.groups.get(group_name)
