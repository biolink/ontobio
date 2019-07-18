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
import logging
import copy

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

logger = logging.getLogger("INFER")
logger.setLevel(logging.WARNING)

MF = "GO:0003674"
ENABLES = "enables"
HAS_PART = "BFO:0000051"

__ancestors_cache = dict()

@click.group()
@click.option("--log", "-L", type=click.Path(exists=False))
def cli(log):
    global logger
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)
    if log:
        click.echo("Setting up logging to {}".format(log))
        logfile_handler = logging.FileHandler(log, mode="w")
        logfile_handler.setLevel(logging.INFO)
        logger.addHandler(logfile_handler)
        logger.setLevel(logging.INFO)

@cli.command()
@click.option("--ontology", "-o", "ontology_path", type=click.Path(exists=True), required=True)
@click.option("--target", "-t", type=click.File("w"), required=True)
@click.option("--gaf", "-g", type=click.File("r"), required=True)
def infer(ontology_path, target, gaf):
    ontology_graph = ontology(ontology_path)

    writer = GafWriter(file=target)
    assoc_generator = gafparser_generator(ontology_graph, gaf)
    line_count = 0
    for association in assoc_generator:
        if association["relation"]["id"] != ENABLES:
            continue
            # Skip all non enables annotations

        inferred_associations = materialize_inferences(ontology_graph, association)
        if len(inferred_associations) > 0:
            click.echo("Materialized {} associations".format(len(inferred_associations)))

        for inferred in inferred_associations:
            writer.write_assoc(inferred)

        line_count += 1
        if line_count % 100 == 0:
            click.echo("Processed {} lines".format(line_count))

@cli.command()
@click.option("--ontology", "-o", "ontology_path", type=click.Path(exists=True), required=True)
@click.option("--relation", "-r", required=True)
@click.option("--allowed-trees", multiple=True, default=["biological_process", "molecular_function", "cellular_component"])
def termable(ontology_path, relation, allowed_trees):
    ontology_graph = ontology(ontology_path)

    accum = dict()
    for term in ontology_graph.nodes():
        if term.split(":")[0] != "GO":
            continue

        go_tree = [d["val"] for d in ontology_graph.node(term)["meta"]["basicPropertyValues"] if d["pred"] == "OIO:hasOBONamespace"]
        if len(go_tree) > 0 and go_tree[0] not in allowed_trees:
            continue

        ns = neighbor_by_relation(ontology_graph, term, relation)
        if len(ns) > 0:
            accum[term] = ns

    click.echo(json.dumps(accum, indent=4))

    desc = []
    for term in accum.keys():
        if ontology_graph.children(term, relations=["subClassOf"]):
            desc.append(term)

    click.echo(desc)

def ontology(path) -> ontol.Ontology:
    click.echo("Loading ontology from {}...".format(path))
    return OntologyFactory().create(path, ignore_cache=True)

def ancestors(term: str, ontology: ontol.Ontology, cache) -> Set[str]:
    click.echo("Computing ancestors for {}".format(term))
    if term == MF:
        click.echo("Found 0")
        return set()

    if term not in cache:
        anc = set(ontology.ancestors(term, relations=["subClassOf"], reflexive=True))
        cache[term] = anc
        click.echo("Found {} (from adding to cache: {} terms added)".format(len(anc), len(cache)))
    else:
        anc = cache[term]
        click.echo("Found {} (from cache)".format(len(anc)))

    return anc

def gafparser_generator(ontology_graph: ontol.Ontology, gaf_file):
    config = assocparser.AssocParserConfig(
        ontology=ontology_graph,
    )
    parser = GafParser(config=config)

    return parser.association_generator(gaf_file, skipheader=True)

def neighbor_by_relation(ontology_graph: ontol.Ontology, term, relation):
    return ontology_graph.parents(term, relations=[relation])

def transform_relation(mf_annotation, new_mf, ontology_graph):
    new_annotation = copy.deepcopy(mf_annotation)
    new_annotation["object"]["id"] = new_mf
    return new_annotation

def materialize_inferences(ontology_graph: ontol.Ontology, annotation):
    materialized_annotations = [] #(gp, new_mf)

    mf = annotation["object"]["id"]
    gp = annotation["subject"]["id"]
    global __ancestors_cache
    mf_ancestors = ancestors(mf, ontology_graph, __ancestors_cache)

    # if mf_ancestors:
    #     logger.info("For {term} \"{termdef}\":".format(term=mf, termdef=ontology_graph.label(mf)))
    messages = []

    for mf_anc in mf_ancestors:
        has_part_mfs = neighbor_by_relation(ontology_graph, mf_anc, HAS_PART)

        # if has_part_mfs:
        #     logger.info("\tHas Parent --> {parent} \"{parentdef}\"".format(parent=mf_anc, parentdef=ontology_graph.label(mf_anc)))
        if has_part_mfs:
            messages.append((gp, mf, mf_anc, has_part_mfs))


        for new_mf in has_part_mfs:
            # logger.info("\t\thas_part --> {part} \"{partdef}\"".format(part=new_mf, partdef=ontology_graph.label(new_mf)))

            new_annotation = transform_relation(annotation, new_mf, ontology_graph)
            materialized_annotations.append(new_annotation)


    messages = [ message for message in messages if message[3] ] # Filter out empty has_parts
    for message in messages:
        logger.info("\nFor {gp} -> {term} \"{termdef}\":".format(gp=message[0], term=message[1], termdef=ontology_graph.label(message[1])))
        logger.info("\tHas Parent --> {parent} \"{parentdef}\"".format(parent=message[1], parentdef=ontology_graph.label(message[1])))
        for part in message[3]:
            logger.info("\t\t has_part --> {part} \"{partdef}\"".format(part=part, partdef=ontology_graph.label(part)))
    
    return materialized_annotations



if __name__ == "__main__":
    cli()
