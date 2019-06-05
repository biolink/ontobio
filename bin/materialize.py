import click
import json
import os
import yaml
import requests
import gzip
import urllib
import shutil
import re
import glob

import yamldown

from functools import wraps

# from ontobio.util.user_agent import get_user_agent
from ontobio.ontol_factory import OntologyFactory
from ontobio import ontol
from ontobio.io.gafparser import GafParser
from ontobio.io.gpadparser import GpadParser
from ontobio.io.assocwriter import GafWriter
from ontobio.io.assocwriter import GpadWriter
from ontobio.io import assocparser
from ontobio.io import gafgpibridge
from ontobio.io import entitywriter
from ontobio.rdfgen import relations

from typing import Dict, Set

MF = "GO:0003674"
ENABLES = "enables"
HAS_PART = "BFO:0000051"

__ancestors_cache = dict()

@click.group()
def cli():
    pass

@cli.command()
@click.option("--ontology", "-o", "ontology_path", type=click.Path(exists=True), required=True)
@click.option("--target", "-t", type=click.File("w"), required=True)
@click.option("--gaf", "-g", type=click.File("r"), required=True)
def infer(ontology_path, target, gaf):
    ontology_graph = ontology(ontology_path)
    mf_set = molecular_function_set(ontology_graph)
    definitions = logical_definitions(ontology_graph)

    writer = GafWriter(file=target)
    assoc_generator = gafparser_generator(ontology_graph, gaf)
    for association in assoc_generator:
        if association["relation"]["id"] != ENABLES:
            continue
            # Skip all non enables annotations

        inferred_associations = materialize_inferences(ontology_graph, definitions, association, mf_set)
        click.echo("Materialized {} associations".format(len(inferred_associations)))
        for inferred in inferred_associations:
            writer.write_assoc(inferred)



def ontology(path) -> ontol.Ontology:
    click.echo("Loading ontology from {}...".format(path))
    return OntologyFactory().create(path, ignore_cache=True)

def molecular_function_set(ontology: ontol.Ontology) -> Set[str]:
    click.echo("Computing Molecular Function ({}) terms...".format(MF))
    return set(ontology.descendants(MF, "subClassOf", reflexive=True))

def ancestors(term: str, ontology: ontol.Ontology) -> Set[str]:
    click.echo("Computing ancestors for {}".format(term))
    if term == MF:
        click.echo("Found 0")
        return set()

    global __ancestors_cache
    if term not in __ancestors_cache:
        anc = set(ontology.ancestors(term, relations=["subClassOf"]))
        __ancestors_cache[term] = anc
    else:
        anc = __ancestors_cache[term]

    click.echo("Found {}".format(len(anc)))
    return anc

def logical_definitions(ontology: ontol.Ontology) -> Dict:
    click.echo("Re-normalizing logical definitions...")
    definition_by_id = dict()
    for definition in ontology.all_logical_definitions:
        if definition not in definition_by_id:
            definition_by_id[definition.class_id] = [definition]
        else:
            definition_by_id[definition.class_id].append(definition)
    return definition_by_id

def gafparser_generator(ontology_graph: ontol.Ontology, gaf_file):
    config = assocparser.AssocParserConfig(
        ontology=ontology_graph,
    )
    parser = GafParser(config=config)

    return parser.association_generator(gaf_file, skipheader=True)

def restrictions_for_term(term, logical_definitions: Dict):
    restrictions = dict() # Property --> Filler
    defs = logical_definitions.get(term, [])
    click.echo("Restrictions for {}: {}".format(term, defs))
    for d in defs:
        for r in d.restrictions:
            restrictions[r[0]] = r[1]
    return restrictions

def transorm_relation(mf_annotation, new_mf, ontology_graph):
    new_annotation = mf_annotation
    new_annotation["object"]["id"] = new_mf
    # new_annotation["object"]["taxon"] How to taxon?
    return new_annotation

def materialize_inferences(ontology_graph: ontol.Ontology, logical_definitions: Dict, annotation, mf_set):
    materialized_annotations = [] #(gp, new_mf)

    mf = annotation["object"]["id"]
    mf_ancestors = ancestors(mf, ontology_graph)
    for mf_anc in mf_ancestors:
        restrictions = restrictions_for_term(mf_anc, logical_definitions)
        click.echo("There are {} restrictions for {}".format(len(restrictions), mf_anc))
        # Filter restrictions for all has_part and that the filler is a MF
        has_part_restrictions = { prop: filler for prop, filler in restrictions.items() if (prop == HAS_PART) and (filler in mf_set)}
        click.echo("Found {} has_part restrictions from the above set".format(len(has_part_restrictions)))
        for has_part, new_mf in has_part_restrictions.items():
            new_annotation = transorm_relation(annotation, new_mf, ontology_graph)
            materialized_annotations.append(new_annotation)

    return materialized_annotations



if __name__ == "__main__":
    cli()
