#!/usr/bin/env python3

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
import sys
import traceback

import yamldown

from functools import wraps

# from ontobio.util.user_agent import get_user_agent
from ontobio.ontol_factory import OntologyFactory
from ontobio.io.gafparser import GafParser
from ontobio.io.gpadparser import GpadParser
from ontobio.io.assocwriter import GafWriter
from ontobio.io.assocwriter import GpadWriter
from ontobio.io import assocparser
from ontobio.io import gafgpibridge
from ontobio.io import entitywriter
from ontobio.io import gaference
from ontobio.rdfgen import assoc_rdfgen
from ontobio.validation import metadata
from ontobio.validation import tools
from ontobio.validation import rules

from typing import Dict, Set

# logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s: %(message)s", level=logging.WARNING)

logger = logging.getLogger("ontobio")

def thispath():
    os.path.normpath(os.path.abspath(__file__))


def download_a_dataset_source(group, dataset_metadata, target_dir, source_url, base_download_url=None, replace_existing_files=True):
    """
    This will download a dataset source given the group name,
    the metadata stanza for the dataset, and the target directory that all downloads
    occur in.

    The path will be built from these elements and then the URL will be found
    from which to download the file.

    `base_download_url` if set will change the URL to a local relative path, rather
    than a true download. This means the dataset_metadata could have "relative/path/to/gaf"
    and the absolute on disk path will be constructed by appending the found metadata
    path to `base_download_url`.

    `replace_existing_files` by default is True. This will overwrite any existing file, always
    updating. With `replace_existing_files` False the path will be checked if a file already
    exists there and if so the actual download will not proceed. The found file
    will be assumed to be the correct file.
    """
    # Local target download path setup - path and then directories
    file_name = source_url.split("/")[-1]
    path = metadata.source_path(dataset_metadata, target_dir, group)

    # Just return the path if we find that it exists already
    if os.path.exists(path) and not replace_existing_files:
        click.echo("{} already exists, no need to download - skipping".format(path))
        return path

    os.makedirs(os.path.split(path)[0], exist_ok=True)

    click.echo("Downloading source to {}".format(path))

    # Parse urls
    source_url_parsed = urllib.parse.urlparse(source_url)
    base_download_url_parsed = urllib.parse.urlparse(base_download_url) if base_download_url != None else None

    # Compute scheme:
    scheme = "file"
    if source_url_parsed.scheme != "":
        scheme = source_url_parsed.scheme
    elif base_download_url_parsed.scheme != "":
        scheme = base_download_url_parsed.scheme

    # Compute joined url, including dealing with relative paths
    joined_url = source_url
    if not source_url_parsed.path.startswith("/"):
        # We're relative
        if base_download_url is not None:
            joined_url = urllib.parse.urljoin(base_download_url, source_url)
        else:
            # This is bad and we have to jump out`since we have no way of constructing a real gaf url
            raise click.ClickException("Option `--base-download-url` was not specified and the config url {} is a relative path.".format(source_url))

    # including scheme and such
    reconstructed_url = urllib.parse.urlunsplit((scheme, urllib.parse.urlparse(joined_url).netloc, urllib.parse.urlparse(joined_url).path, source_url_parsed.query, ""))

    # Using urllib to download if scheme is ftp or file. Otherwise we can use requests and use a progressbar
    if scheme in ["ftp", "file"]:
        urllib.request.urlretrieve(reconstructed_url, path)
    else:
        response = requests.get(reconstructed_url, stream=True)
        content_length = int(response.headers.get("Content-Length", 0))

        with open(path, "wb") as downloaded:
            with click.progressbar(iterable=response.iter_content(chunk_size=512 * 1024), length=content_length, show_percent=True) as chunks:
                for chunk in chunks:
                    if chunk:
                        downloaded.write(chunk)

    return path

def download_source_gafs(group_metadata, target_dir, exclusions=[], base_download_url=None, replace_existing_files=True):
    """
    This looks at a group metadata dictionary and downloads each GAF source that is not in the exclusions list.
    For each downloaded file, keep track of the path of the file. If the file is zipped, it will unzip it here.
    This function returns a list of tuples of the dataset dictionary mapped to the downloaded source path.
    """
    # Grab all datasets in a group, excluding non-gaf, datasets that are explicitely excluded from an option, and excluding datasets with the `exclude key` set to true
    gaf_urls = [ (data, data["source"]) for data in group_metadata["datasets"] if data["type"] == "gaf" and data["dataset"] not in exclusions and not data.get("exclude", False)]
    # List of dataset metadata to gaf download url

    click.echo("Found {}".format(", ".join( [ kv[0]["dataset"] for kv in gaf_urls ] )))
    downloaded_paths = []
    for dataset_metadata, gaf_url in gaf_urls:
        dataset = dataset_metadata["dataset"]
        # Local target download path setup - path and then directories
        path = download_a_dataset_source(group_metadata["id"], dataset_metadata, target_dir, gaf_url, base_download_url=base_download_url, replace_existing_files=replace_existing_files)

        if dataset_metadata["compression"] == "gzip":
            # Unzip any downloaded file that has gzip, strip of the gzip extension
            unzipped = os.path.splitext(path)[0]
            unzip(path, unzipped)
            path = unzipped
        else:
            # otherwise file is coming in uncompressed. But we want to make sure
            # to zip up the original source also
            tools.zipup(path)

        downloaded_paths.append((dataset_metadata, path))

    return downloaded_paths

def check_and_download_mixin_source(mixin_metadata, group_id, dataset, target_dir, base_download_url=None, replace_existing_files=True):
    mixin_dataset = tools.find(mixin_metadata["datasets"], lambda d: d.get("merges_into", "") == dataset)
    if mixin_dataset is None:
        return None

    click.echo("Merging mixin dataset {}".format(mixin_dataset["source"]))
    path = download_a_dataset_source(group_id, mixin_dataset, target_dir, mixin_dataset["source"], base_download_url=base_download_url, replace_existing_files=replace_existing_files)

    unzipped = os.path.splitext(path)[0] # Strip off the .gz extension, leaving just the unzipped filename
    unzip(path, unzipped)
    return unzipped

def mixin_dataset(mixin_metadata, dataset):
    mixin_dataset_version = tools.find(mixin_metadata["datasets"], lambda d: d.get("merges_into", "") == dataset)
    if mixin_dataset_version is None:
        return None # Blah

    return mixin_dataset_version

def unzip(path, target):
    click.echo("Unzipping {}".format(path))
    def chunk_gen():
        with gzip.open(path, "rb") as p:
            while True:
                chunk = p.read(size=512 * 1024)
                if not chunk:
                    break
                yield chunk

    with open(target, "wb") as tf:
        with click.progressbar(iterable=chunk_gen()) as chunks:
            for chunk in chunks:
                tf.write(chunk)


def create_parser(config, group, dataset, format="gaf"):
    if format == "gpad":
        return GpadParser(config=config, group=group, dataset=dataset)
    else:
        # We assume it's gaf as we only support in this instant gaf and gpad
        return GafParser(config=config, group=group, dataset=dataset)


"""
Produce validated gaf using the gaf parser/
"""
@tools.gzips
def produce_gaf(dataset, source_gaf, ontology_graph, gpipath=None, paint=False, group="unknown", rule_metadata=None, goref_metadata=None, db_entities=None, group_idspace=None, format="gaf", suppress_rule_reporting_tags=[], annotation_inferences=None):
    filtered_associations = open(os.path.join(os.path.split(source_gaf)[0], "{}_noiea.gaf".format(dataset)), "w")

    config = assocparser.AssocParserConfig(
        ontology=ontology_graph,
        filter_out_evidence=["IEA"],
        filtered_evidence_file=filtered_associations,
        gpi_authority_path=gpipath,
        paint=paint,
        rule_metadata=rule_metadata,
        goref_metadata=goref_metadata,
        entity_idspaces=db_entities,
        group_idspace=group_idspace,
        suppress_rule_reporting_tags=suppress_rule_reporting_tags,
        annotation_inferences=annotation_inferences
    )
    logger.info("AssocParserConfig used: {}".format(config))
    split_source = os.path.split(source_gaf)[0]
    validated_gaf_path = os.path.join(split_source, "{}_valid.gaf".format(dataset))
    outfile = open(validated_gaf_path, "w")
    gafwriter = GafWriter(file=outfile, source=dataset)

    click.echo("Validating source {}: {}".format(format, source_gaf))
    parser = create_parser(config, group, dataset, format)
    with open(source_gaf) as sg:
        lines = sum(1 for line in sg)

    with open(source_gaf) as gaf:
        with click.progressbar(iterable=parser.association_generator(file=gaf), length=lines) as associations:
            for assoc in associations:
                gafwriter.write_assoc(assoc)

    outfile.close()
    filtered_associations.close()
    
    report_markdown_path = os.path.join(os.path.split(source_gaf)[0], "{}.report.md".format(dataset))
    logger.info("About to write markdown report to {}".format(report_markdown_path))
    with open(report_markdown_path, "w") as report_md:
        logger.info("Opened for writing {}".format(report_markdown_path))
        report_md.write(parser.report.to_markdown())
    
    logger.info("markdown {} written out".format(report_markdown_path))
    logger.info("Markdown current stack:")
    traceback.print_stack()

    report_json_path = os.path.join(os.path.split(source_gaf)[0], "{}.report.json".format(dataset))
    logger.info("About to write json report to {}".format(report_json_path))
    with open(report_json_path, "w") as report_json:
        logger.info("Opened for writing {}".format(report_json_path))
        report_json.write(json.dumps(parser.report.to_report_json(), indent=4))
    
    logger.info("json {} written out".format(report_markdown_path))
    logger.info("json current Stack:")
    traceback.print_stack()

    return [validated_gaf_path, filtered_associations.name]


@tools.gzips
def make_products(dataset, target_dir, gaf_path, products, ontology_graph):
    gafparser = GafParser()
    gafparser.config = assocparser.AssocParserConfig(
        ontology=ontology_graph,
        paint=True
    )

    with open(gaf_path) as sg:
        lines = sum(1 for line in sg)

    product_files = {
        "gpad": open(os.path.join(os.path.split(gaf_path)[0], "{}.gpad".format(dataset)), "w"),
        "ttl": open(os.path.join(os.path.split(gaf_path)[0], "{}_cam.ttl".format(dataset)), "wb")
    }
    
    if not products["gpad"] and not products["ttl"]:
        # Bail if we have no products
        return []

    # def write_gpi_entity(association, bridge, gpiwriter):
    with open(gaf_path) as gf:
        # gpi info:
        click.echo("Using {} as the gaf to build data products with".format(gaf_path))
        if products["ttl"]:
            click.echo("Setting up {}".format(product_files["ttl"].name))
            rdf_writer = assoc_rdfgen.TurtleRdfWriter(label=os.path.split(product_files["ttl"].name)[1] )
            transformer = assoc_rdfgen.CamRdfTransform(writer=rdf_writer)
            parser_config = assocparser.AssocParserConfig(ontology=ontology_graph)

        if products["gpad"]:
            click.echo("Setting up {}".format(product_files["gpad"].name))
            gpadwriter = GpadWriter(file=product_files["gpad"])

        click.echo("Making products...")
        with click.progressbar(iterable=gafparser.association_generator(file=gf), length=lines) as associations:
            for association in associations:
                if products["ttl"]:
                    if "header" not in association or not association["header"]:
                        transformer.provenance()
                        transformer.translate(association)

                if products["gpad"]:
                    gpadwriter.write_assoc(association)

        # post ttl steps
        if products["ttl"]:
            click.echo("Writing ttl to disk")
            rdf_writer.serialize(destination=product_files["ttl"])

        # After we run through associations
        for f in product_files.values():
            f.close()

    return [product_files[prod].name for prod in sorted(product_files.keys()) if products[prod]]

@tools.gzips
def produce_gpi(dataset, target_dir, gaf_path, ontology_graph):
    gafparser = GafParser()
    gafparser.config = assocparser.AssocParserConfig(
        ontology=ontology_graph
    )
    with open(gaf_path) as sg:
        lines = sum(1 for line in sg)

    gpi_path = os.path.join(os.path.split(gaf_path)[0], "{}.gpi".format(dataset))
    with open(gaf_path) as gf, open(gpi_path, "w") as gpi:
        click.echo("Using {} as the gaf to build gpi with".format(gaf_path))
        bridge = gafgpibridge.GafGpiBridge()
        gpiwriter = entitywriter.GpiWriter(file=gpi)
        gpi_cache = set()

        with click.progressbar(iterable=gafparser.association_generator(file=gf), length=lines) as associations:
            for association in associations:
                entity = bridge.convert_association(association)
                if entity not in gpi_cache and entity is not None:
                    # If the entity is not in the cache, add it and write it out
                    gpi_cache.add(entity)
                    gpiwriter.write_entity(entity)

    return gpi_path


@tools.gzips
def produce_ttl(dataset, target_dir, gaf_path, ontology_graph):
    gafparser = GafParser()
    gafparser.config = assocparser.AssocParserConfig(
        ontology=ontology_graph
    )

    with open(gaf_path) as sg:
        lines = sum(1 for line in sg)

    ttl_path = os.path.join(os.path.split(gaf_path)[0], "{}_cam.ttl".format(dataset))
    click.echo("Producing ttl: {}".format(ttl_path))
    rdf_writer = assoc_rdfgen.TurtleRdfWriter()
    transformer = assoc_rdfgen.CamRdfTransform(writer=rdf_writer)
    parser_config = assocparser.AssocParserConfig(ontology=ontology_graph)

    with open(gaf_path) as gf:
        with click.progressbar(iterable=gafparser.association_generator(file=gf), length=lines) as associations:
            for association in associations:
                if "header" not in association or not association["header"]:
                    transformer.provenance()
                    transformer.translate(association)

    with open(ttl_path, "wb") as ttl:
        click.echo("Writing ttl to disk")
        rdf_writer.serialize(destination=ttl)

    return ttl_path


@tools.gzips
def merge_all_mixin_gaf_into_mod_gaf(valid_gaf_path, mixin_gaf_paths):
    def header_and_annotations(gaf_file):
        headers = []
        annotations = []

        for line in gaf_file.readlines():
            line = line.rstrip("\n")
            if line.startswith("!"):
                headers.append(line)
            else:
                annotations.append(line)

        return (headers, annotations)

    def make_mixin_header(header_lines, path):
        the_header = [
            "!Header copied from {}".format(os.path.basename(path)),
            "!================================="
        ] + header_lines[8:] + ["!"]
        return the_header
    # ####################################################################

    # Set up merged final gaf product path
    dirs, name = os.path.split(valid_gaf_path)
    merged_path = os.path.join(dirs, "{}.gaf".format(name.rsplit("_", maxsplit=1)[0]))
    valid_header = []
    annotations = []
    with open(valid_gaf_path) as valid_file:
        valid_header, annotations = header_and_annotations(valid_file)

    mixin_headers = []
    for mixin_gaf_path in mixin_gaf_paths:
        with open(mixin_gaf_path) as mixin_file:
            mixin_header, mixin_annotations = header_and_annotations(mixin_file)

            mixin_headers += make_mixin_header(mixin_header, mixin_gaf_path)
            annotations += mixin_annotations

    full_header = valid_header + \
    [
        "!=================================",
        "!"
    ] + mixin_headers + \
    [
        "!=================================",
        "!",
        "!Documentation about this header can be found here: https://github.com/geneontology/go-site/blob/master/docs/gaf_validation.md",
        "!"
    ]
    all_lines = full_header + annotations

    with open(merged_path, "w") as merged_file:
        merged_file.write("\n".join(all_lines))

    return merged_path

def mixin_a_dataset(valid_gaf, mixin_metadata_list, group_id, dataset, target, ontology, gpipath=None, base_download_url=None, replace_existing_files=True):

    end_gaf = valid_gaf
    mixin_gaf_paths = []
    for mixin_metadata in mixin_metadata_list:
        mixin_src = check_and_download_mixin_source(mixin_metadata, group_id, dataset, target, base_download_url=base_download_url, replace_existing_files=replace_existing_files)

        if mixin_src is not None:
            mixin_dataset_metadata = mixin_dataset(mixin_metadata, dataset)
            mixin_dataset_id = mixin_dataset_metadata["dataset"]
            format = mixin_dataset_metadata["type"]
            mixin_gaf = produce_gaf(mixin_dataset_id, mixin_src, ontology, gpipath=gpipath, paint=mixin_metadata["id"]=="paint", group=mixin_metadata["id"], format=format)[0]
            mixin_gaf_paths.append(mixin_gaf)

    if mixin_gaf_paths:
        # If we found and processed any mixin gafs, then lets merge them.
        end_gaf = merge_all_mixin_gaf_into_mod_gaf(valid_gaf, mixin_gaf_paths)
    else:
        gafgz = "{}.gz".format(valid_gaf)
        shutil.copyfile(gafgz, os.path.join(os.path.split(gafgz)[0], "{}.gaf.gz".format(dataset)))

    return end_gaf


@click.group()
@click.option("--verbose", "-v", is_flag=True, default=False)
@click.pass_context
def cli(ctx, verbose):    
    if verbose:
        logger.setLevel(logging.INFO)

@cli.command()
@click.pass_context
@click.argument("group")
@click.option("--metadata", "-m", "metadata_dir", type=click.Path(), required=True)
@click.option("--gpad", default=False, is_flag=True)
@click.option("--ttl", default=False, is_flag=True)
@click.option("--target", "-t", type=click.Path(), required=True)
@click.option("--ontology", "-o", type=click.Path(exists=True), required=False)
@click.option("--exclude", "-x", multiple=True)
@click.option("--base-download-url", "-b", default=None)
@click.option("--suppress-rule-reporting-tag", "-S", multiple=True, help="Suppress markdown output messages from rules tagged with this tag")
@click.option("--skip-existing-files", is_flag=True, default=False, help="When downloading files, if a file already exists it won't downloaded over")
@click.option("--gaferencer-file", "-I", type=click.Path(exists=True), default=None, required=False, help="Path to Gaferencer output to be used for inferences")
def produce(ctx, group, metadata_dir, gpad, ttl, target, ontology, exclude, base_download_url, suppress_rule_reporting_tag, skip_existing_files, gaferencer_file):

    logger.info("Logging is verbose")
    products = {
        "gaf": True,
        "gpi": True,
        "gpad": gpad,
        "ttl": ttl
    }
    click.echo("Making products {}.".format(", ".join([key for key in products if products[key]])))
    absolute_target = os.path.abspath(target)
    os.makedirs(os.path.join(absolute_target, "groups"), exist_ok=True)
    click.echo("Products will go in {}".format(absolute_target))
    absolute_metadata = os.path.abspath(metadata_dir)

    group_metadata = metadata.dataset_metadata_file(absolute_metadata, group)
    click.echo("Loading ontology: {}...".format(ontology))
    ontology_graph = OntologyFactory().create(ontology, ignore_cache=True)

    downloaded_gaf_sources = download_source_gafs(group_metadata, absolute_target, exclusions=exclude, base_download_url=base_download_url, replace_existing_files=not skip_existing_files)

    # extract the titles for the go rules, this is a dictionary comprehension
    rule_metadata = metadata.yamldown_lookup(os.path.join(absolute_metadata, "rules"))
    goref_metadata = metadata.yamldown_lookup(os.path.join(absolute_metadata, "gorefs"))
    
    click.echo("Found {} GO Rules".format(len(rule_metadata.keys())))
    click.echo("Found {} GO_REFs".format(len(goref_metadata.keys())))

    paint_metadata = metadata.dataset_metadata_file(absolute_metadata, "paint")
    noctua_metadata = metadata.dataset_metadata_file(absolute_metadata, "noctua")
    mixin_metadata_list = list(filter(lambda m: m != None, [paint_metadata, noctua_metadata]))

    db_entities = metadata.database_entities(absolute_metadata)
    group_ids = metadata.groups(absolute_metadata)

    gaferences = None
    if gaferencer_file:
        gaferences = gaference.load_gaferencer_inferences_from_file(gaferencer_file)
            
    for dataset_metadata, source_gaf in downloaded_gaf_sources:
        dataset = dataset_metadata["dataset"]
        # Set paint to True when the group is "paint".
        # This will prevent filtering of IBA (GO_RULE:26) when paint is being treated as a top level group, like for paint_other.
        valid_gaf = produce_gaf(dataset, source_gaf, ontology_graph,
            paint=(group=="paint"),
            group=group,
            rule_metadata=rule_metadata,
            goref_metadata=goref_metadata,
            db_entities=db_entities,
            group_idspace=group_ids,
            suppress_rule_reporting_tags=suppress_rule_reporting_tag,
            annotation_inferences=gaferences
            )[0]

        gpi = produce_gpi(dataset, absolute_target, valid_gaf, ontology_graph)

        end_gaf = mixin_a_dataset(valid_gaf, mixin_metadata_list, group_metadata["id"], dataset, absolute_target, ontology_graph, gpipath=gpi, base_download_url=base_download_url, replace_existing_files=not skip_existing_files)
        make_products(dataset, absolute_target, end_gaf, products, ontology_graph)



@cli.command()
@click.argument("group")
@click.argument("dataset")
@click.option("--metadata", "-m", type=click.Path(), required=True)
@click.option("--target", type=click.Path(), required=True)
@click.option("--ontology", type=click.Path(), required=True)
def paint(group, dataset, metadata, target, ontology):
    absolute_metadata = os.path.abspath(metadata)
    absolute_target = os.path.abspath(target)
    os.makedirs(os.path.join(absolute_target, "groups"), exist_ok=True)
    paint_metadata = metadata.dataset_metadata_file(absolute_metadata, "paint")
    paint_src_gaf = check_and_download_mixin_source(paint_metadata, dataset, absolute_target)

    click.echo("Loading ontology: {}...".format(ontology))
    ontology_graph = OntologyFactory().create(ontology)

    gpi_path = os.path.join(absolute_target, "groups", dataset, "{}.gpi".format(dataset))
    click.echo("Using GPI at {}".format(gpi_path))
    paint_gaf = produce_gaf("paint_{}".format(dataset), paint_src_gaf, ontology_graph, gpipath=gpi_path)


@cli.command()
@click.option("--metadata", "-m", "metadata_dir", type=click.Path(), required=True)
@click.option("--out", type=click.Path(), required=False)
@click.option("--ontology", type=click.Path(), required=True)
@click.option("--gaferencer-file", "-I", type=click.Path(exists=True), default=None, required=False, help="Path to Gaferencer output to be used for inferences")
def rule(metadata_dir, out, ontology, gaferencer_file):
    absolute_metadata = os.path.abspath(metadata_dir)

    click.echo("Loading ontology: {}...".format(ontology))
    ontology_graph = OntologyFactory().create(ontology)
    
    goref_metadata = metadata.yamldown_lookup(os.path.join(absolute_metadata, "gorefs"))
    gorule_metadata = metadata.yamldown_lookup(os.path.join(absolute_metadata, "rules"))
    
    click.echo("Found {} GO Rules".format(len(gorule_metadata.keys())))
    
    db_entities = metadata.database_entities(absolute_metadata)
    group_ids = metadata.groups(absolute_metadata)
    
    gaferences = None
    if gaferencer_file:
        gaferences = gaference.load_gaferencer_inferences_from_file(gaferencer_file)
    
    config = assocparser.AssocParserConfig(
        ontology=ontology_graph,
        goref_metadata=goref_metadata,
        entity_idspaces=db_entities,
        group_idspace=group_ids,
        annotation_inferences=gaferences
    )
    all_examples_valid = True
    all_results = []
    for rule_id, rule_meta in gorule_metadata.items():
        examples = rules.RuleExample.example_from_json(rule_meta)
        if len(examples) == 0:
            # skip if there are no examples
            continue
        
        click.echo("==============================================================================")
        click.echo("Validating {} examples for {}".format(len(examples), rule_id.upper().replace("-", ":")))
        results = rules.validate_all_examples(examples, config=config)
        successes = sum(1 for r in results if r.success)
        click.echo("\t* {}/{} success".format(successes, len(results)))
        for r in results:
            if not r.success:
                click.echo("\tRule example failed: {}".format(r.reason))
                click.echo("\tInput: >> `{}`".format(r.example.input))
                all_examples_valid = False
                
        all_results += results
    
    if out:
        absolute_out = os.path.abspath(out)
        os.makedirs(os.path.dirname(absolute_out), exist_ok=True)
        try:
            with open(absolute_out, "w") as outfile:
                json.dump(rules.validation_report(all_results), outfile, indent=4)
        except Exception as e:
            raise click.ClickException("Could not write report to {}: ".format(out, e))
    
    if not all_examples_valid:
        raise click.ClickException("At least one rule example was not validated.")


if __name__ == "__main__":
    cli(obj={})
