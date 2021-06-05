from ontobio.rdfgen.gocamgen.gocamgen import AssocGoCamModel
from ontobio.rdfgen.gocamgen.filter_rule import AssocFilter, FilterRule, get_filter_rule
from ontobio.rdfgen.gocamgen.collapsed_assoc import extract_properties
from ontobio.rdfgen.gocamgen.errors import GocamgenException, GeneErrorSet
from ontobio.io import gpadparser
from ontobio.io.assocparser import AssocParserConfig
from ontobio.io.entityparser import GpiParser
from ontobio.model.association import GoAssociation
from ontobio.ontol_factory import OntologyFactory
from ontobio.util.go_utils import GoAspector
import argparse
import logging
import requests
from requests.exceptions import ConnectionError
import gzip
import time
import click
from os import path
from typing import List
# from abc import ABC, abstractmethod
from rdflib.graph import ConjunctiveGraph
from rdflib.store import Store
from rdflib import plugin

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")

parser = argparse.ArgumentParser()
parser.add_argument('-g', '--gpad_file', help="Filepath of GPAD source with annotations to model", required=True)
parser.add_argument('-s', '--specific_gene', help="If specified, will only translate model for annotations "
                                                  "to this specific gene")
parser.add_argument('-o', '--ontology', help="Path to GO-LEGO ontology file")
parser.add_argument('-n', '--max_model_limit', help="Only translate specified number of models. Mainly for testing.")
parser.add_argument('-m', '--mod', help="MOD rules to follow for filtering and translating.")
parser.add_argument('-d', '--output_directory', help="Directory to output model ttl files to")
parser.add_argument('-r', '--report', help="Generate report", action="store_const", const=True)
parser.add_argument('-N', '--nquads', help="Filepath to write model file in N-Quads format")

# GoCamInputHandler


class GoCamBuilder:
    def __init__(self, parser_config: AssocParserConfig, modelstate=None):
        self.config = parser_config
        self.aspector = GoAspector(self.config.ontology)
        self.store = plugin.get('IOMemory', Store)()
        self.errors = GeneErrorSet()  # Errors by gene ID
        self.gpi_entities = self.parse_gpi(parser_config.gpi_authority_path)
        self.modelstate = modelstate

    def translate_to_model(self, gene, assocs: List[GoAssociation]):
        model_id = gene.replace(":", "_")
        model = AssocGoCamModel(gene,
                                assocs,
                                config=self.config,
                                store=self.store,
                                gpi_entities=self.gpi_entities,
                                model_id=model_id,
                                modelstate=self.modelstate)
        model.go_aspector = self.aspector  # TODO: Grab aspect from ontology node
        model.translate()

        return model

    def make_model(self, gene, annotations: List[GoAssociation], output_directory=None, nquads=False):
        # All these retry shenanigans are to prevent mid-run crashes due to an external resource simply blipping
        # out for a second.
        retry_count = 0
        retry_limit = 5
        while True:
            try:
                start_time = time.time()
                model = self.translate_to_model(gene, annotations)
                # add_to_conjunctive_graph(model, conjunctive_graph)
                if nquads:
                    logger.info(
                        "Model for {} added to graphstore in {} sec".format(gene, (time.time() - start_time)))
                else:
                    out_filename = "{}.ttl".format(gene.replace(":", "_"))
                    if output_directory is not None:
                        out_filename = path.join(output_directory, out_filename)
                    model.write(out_filename)
                    logger.info("Model for {} written to {} in {} sec".format(gene, out_filename,
                                                                              (time.time() - start_time)))
                for err in model.errors:
                    self.errors.add_error(gene, err)
                return model
            except GocamgenException as ex:
                self.errors.add_error(gene, ex)
            except (TimeoutError, ConnectionError) as ex:
                # This has been happening randomly and breaking full runs
                self.errors.add_error(gene, ex)
                if retry_count < retry_limit:
                    retry_count += 1
                    continue  # retry
                self.errors.add_error(gene,
                                 GocamgenException(f"Bailing on model for {gene} after {retry_count} retries"))
            break  # Done with this model. Move on to the next one.

    def make_model_and_add_to_store(self, gene, annotations):
        return self.make_model(gene, annotations, nquads=True)

    def make_model_and_write_out(self, gene, annotations, output_directory=None):
        return self.make_model(gene, annotations, output_directory=output_directory, nquads=False)

    def write_out_store_to_nquads(self, filepath):
        cg = ConjunctiveGraph(self.store)
        cg.serialize(destination=filepath, format="nquads")
        logger.info(f"Full model graphstore written out in N-Quads format to {filepath}")

    def write_report(self, report_filepath):
        with open(report_filepath, "w+") as reportf:
            for gene, errs in self.errors.errors.items():
                for ex in errs:
                    reportf.write(f"{type(ex).__name__} - {gene}: {ex}\n")

    @staticmethod
    def extract_relations_ontology(ontology_graph):
        # TODO: This is probably all wrong - trying to reconstruct RO from broader ontology_graph
        # According to Ontobee RO top-level terms are RO:0002410 (causally related to)
        #  and RO:0002222 (temporally related to) - try reconstructing RO with these
        ro_terms = []
        for t in [
            "RO:0002410",  # causally related to
            "RO:0002222",  # temporally related to
            "RO:0002323",  # mereotopologically related to - for BFO:0000050
        ]:
            ro_terms = ro_terms + ontology_graph.descendants(t, reflexive=True)
        return ontology_graph.subontology(nodes=ro_terms)

    @staticmethod
    def parse_gpi(gpi_file):
        # {
        #    "id":"MGI:MGI:87853",
        #    "label":"a",
        #    "full_name":"nonagouti",
        #    "synonyms":[
        #       "agouti",
        #       "As",
        #       "agouti signal protein",
        #       "ASP"
        #    ],
        #    "type":"gene",
        #    "parents":[
        #
        #    ],
        #    "xrefs":[
        #       "UniProtKB:Q03288"
        #    ],
        #    "taxon":{
        #       "id":"NCBITaxon:10090"
        #    }
        # }
        if gpi_file is None:
            return None
        parser = GpiParser()
        gpi_entities = {}
        entities = parser.parse(gpi_file)
        for entity in entities:
            gpi_entities[entity['id']] = entity
        return gpi_entities


class AssocExtractor:
    def __init__(self, gpad_file, parser_config: AssocParserConfig):
        self.assocs = []
        self.gpad_parser = gpadparser.GpadParser(config=parser_config)
        with open(gpad_file) as sg:
            lines = sum(1 for line in sg)

        with open(gpad_file) as gf:
            click.echo("Making products...")
            with click.progressbar(iterable=self.gpad_parser.association_generator(file=gf, skipheader=True),
                                   length=lines) as associations:
                self.assocs = list(associations)

        self.entity_parents = self.parse_gpi_parents(parser_config.gpi_authority_path)

    def group_assocs(self):
        assocs_by_gene = {}
        for a in self.assocs:
            subject_id = str(a.subject.id)
            # If entity has parent, assign to parent entity model
            if subject_id in self.entity_parents:
                subject_id = self.entity_parents[subject_id]
            if subject_id in assocs_by_gene:
                assocs_by_gene[subject_id].append(a)
            else:
                assocs_by_gene[subject_id] = [a]
        return assocs_by_gene

    @staticmethod
    def extract_properties_from_assocs(assocs):
        new_assoc_list = []
        for a in assocs:
            new_assoc_list.append(extract_properties(a))
        return new_assoc_list

    @staticmethod
    def parse_gpi_parents(gpi_file):
        if gpi_file is None:
            return None
        parser = GpiParser()
        entity_parents = {}
        entities = parser.parse(gpi_file)
        for entity in entities:
            entity_id = entity['id']
            if len(entity['encoded_by']) > 0:
                entity_parents[entity_id] = entity['encoded_by'][0]  # There may only be one
        return entity_parents


def unzip(filepath):
    input_file = gzip.GzipFile(filepath, "rb")
    s = input_file.read()
    input_file.close()

    target = path.splitext(filepath)[0]
    logger.info("Gunzipping file: {}".format(filepath))
    with open(target, "wb") as output:
        output.write(s)
    return target


def handle_gpad_file(args_gpad_file):
    if args_gpad_file.startswith("http://"):
        gpad_file_target = args_gpad_file.split("/")[-1]
        logger.info("Downloading GPAD from {} and saving to {}".format(args_gpad_file, gpad_file_target))
        response = requests.get(args_gpad_file)
        with open(gpad_file_target, "wb") as gft:
            gft.write(response.content)
        if gpad_file_target.endswith(".gz"):
            gpad_file = unzip(gpad_file_target)
        else:
            gpad_file = gpad_file_target
    else:
        gpad_file = args.gpad_file
    return gpad_file


def parse_header(gpad_file):
    header_data = {
        "date": ""
    }
    with open(gpad_file) as gf:
        for l in gf.readlines():
            if l.startswith("!"):
                date_key = "!date: "
                if l.startswith(date_key):
                    header_data["date"] = l.split(date_key)[1].split("$")[0].strip()
            else:
                break
    return header_data


if __name__ == "__main__":
    args = parser.parse_args()

    filter_rule = get_filter_rule(args.mod)

    gpad_file = handle_gpad_file(args.gpad_file)
    relevant_header_data = parse_header(gpad_file)
    gpad_file_metadata = {
        "source_path": args.gpad_file,
        # TODO: Figure out how to get real creation date from file
        "download_date": time.ctime(path.getmtime(gpad_file)),
        "header_date": relevant_header_data["date"]
    }

    extractor = AssocExtractor(gpad_file)
    assocs_by_gene = extractor.group_assocs()
    logger.debug("{} distinct genes".format(len(assocs_by_gene)))

    ontology_graph = OntologyFactory().create(args.ontology)
    builder = GoCamBuilder(ontology_graph)

    model_count = 0
    if args.specific_gene:
        for specific_gene in args.specific_gene.split(","):
            if specific_gene not in assocs_by_gene:
                logger.error("ERROR: specific gene {} not found in filtered annotation list".format(specific_gene))
            else:
                logger.debug("{} filtered annotations to translate for {}".format(len(assocs_by_gene[specific_gene]), specific_gene))
                builder.make_model(specific_gene, annotations=assocs_by_gene[specific_gene], output_directory=args.output_directory, nquads=args.nquads)
                model_count += 1
    else:
        for gene in assocs_by_gene:
            builder.make_model(gene, annotations=assocs_by_gene[gene], output_directory=args.output_directory, nquads=args.nquads)
            model_count += 1
            if args.max_model_limit and model_count == int(args.max_model_limit):
                break

    if args.nquads:
        builder.write_out_store_to_nquads(filepath=args.nquads)

    if args.report:
        report_file_path = "{}.report".format(gpad_file)
        with open(report_file_path, "w+") as reportf:
            for k in gpad_file_metadata:
                reportf.write("{}: {}\n".format(k, gpad_file_metadata[k]))
            # TODO FilterRule().__str__() to display filters
            reportf.write("# of models generated: {}\n".format(model_count))
            for gene, errs in builder.errors.errors.items():
                for ex in errs:
                    reportf.write(f"{type(ex).__name__} - {gene}: {ex}\n")
        logger.info("Report file generated at {}".format(report_file_path))
