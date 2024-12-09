#!/usr/bin/env python3

import click
import json
import os
import requests
import gzip
import urllib
import shutil
import logging

from ontobio.model.association import GoAssociation
from ontobio.model.association import Curie, ExtensionUnit
from ontobio.io.entityparser import GpiParser
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
from ontobio.rdfgen.gocamgen.gocam_builder import GoCamBuilder, AssocExtractor
from ontobio.validation import metadata
from ontobio.validation import tools
from ontobio.validation import rules

from typing import Dict, Set, List

# logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s: %(message)s", level=logging.WARNING)

logger = logging.getLogger("ontobio")


def thispath():
    os.path.normpath(os.path.abspath(__file__))


def download_a_dataset_source(group, dataset_metadata, target_dir, source_url, base_download_url=None,
                              replace_existing_files=True):
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
            raise click.ClickException(
                "Option `--base-download-url` was not specified and the config url {} is a relative path.".format(
                    source_url))

    # including scheme and such
    reconstructed_url = urllib.parse.urlunsplit((scheme, urllib.parse.urlparse(joined_url).netloc,
                                                 urllib.parse.urlparse(joined_url).path, source_url_parsed.query, ""))

    click.echo("Using URL `{}`".format(reconstructed_url))

    # Using urllib to download if scheme is ftp or file. Otherwise we can use requests and use a progressbar
    if scheme in ["ftp", "file"]:
        urllib.request.urlretrieve(reconstructed_url, path)
    else:
        response = requests.get(reconstructed_url, stream=True)
        content_length = int(response.headers.get("Content-Length", 0))

        with open(path, "wb") as downloaded:
            with click.progressbar(iterable=response.iter_content(chunk_size=512 * 1024), length=content_length,
                                   show_percent=True) as chunks:
                for chunk in chunks:
                    if chunk:
                        downloaded.write(chunk)

    return path


def download_source_gafs(group_metadata,
                         target_dir,
                         exclusions=[],
                         base_download_url=None,
                         replace_existing_files=True,
                         only_dataset=None):
    """
    This looks at a group metadata dictionary and downloads each GAF source that is not in the exclusions list.
    For each downloaded file, keep track of the path of the file. If the file is zipped, it will unzip it here.
    This function returns a list of tuples of the dataset dictionary mapped to the downloaded source path.
    """
    # Grab all datasets in a group, excluding non-gaf, datasets that are explicitly excluded
    # from an option, and excluding datasets with the `exclude key` set to true

    gaf_urls = []
    if only_dataset is None:
        gaf_urls = [(data, data["source"]) for data in group_metadata["datasets"] if
                    data["type"] == "gaf" and data["dataset"] not in exclusions and not data.get("exclude", False)]
    else:
        gaf_urls = [(data, data["source"]) for data in group_metadata["datasets"] if data["dataset"] == only_dataset]
    # List of dataset metadata to gaf download url

    click.echo("Found gaf_urls {}".format(", ".join([kv[0]["dataset"] for kv in gaf_urls])))
    downloaded_paths = []
    for dataset_metadata, gaf_url in gaf_urls:
        dataset = dataset_metadata["dataset"]
        # Local target download path setup - path and then directories
        path = download_a_dataset_source(group_metadata["id"], dataset_metadata, target_dir, gaf_url,
                                         base_download_url=base_download_url,
                                         replace_existing_files=replace_existing_files)

        if dataset_metadata.get("compression", None) == "gzip":
            # Unzip any downloaded file that has gzip, strip of the gzip extension
            path = unzip_simple(path)
        else:
            # otherwise file is coming in uncompressed. But we want to make sure
            # to zip up the original source also
            tools.zipup(path)
        click.echo("Downloaded {}".format(path))
        downloaded_paths.append((dataset_metadata, path))

    return downloaded_paths


def check_and_download_mixin_source(mixin_metadata, group_id, dataset, target_dir, base_download_url=None,
                                    replace_existing_files=True):
    mixin_dataset = tools.find(mixin_metadata["datasets"], lambda d: d.get("merges_into", "") == dataset)
    if mixin_dataset is None:
        return None

    click.echo("Downloading dataset {}".format(mixin_dataset["source"]))
    path = download_a_dataset_source(group_id, mixin_dataset, target_dir, mixin_dataset["source"],
                                     base_download_url=base_download_url, replace_existing_files=replace_existing_files)

    unzipped = unzip_simple(path)  # Strip off the .gz extension, leaving just the unzipped filename
    return unzipped


def mixin_dataset(mixin_metadata, dataset):
    mixin_dataset_version = tools.find(mixin_metadata["datasets"], lambda d: d.get("merges_into", "") == dataset)
    if mixin_dataset_version is None:
        return None  # Blah

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


def unzip_simple(zipped_path):
    # 'Simple' meaning no chunking like in unzip()
    unzipped = os.path.splitext(zipped_path)[0]  # Strip off the .gz extension, leaving just the unzipped filename
    unzip(zipped_path, unzipped)
    return unzipped


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
def produce_gaf(dataset, source_gaf, ontology_graph, gpipaths=None, paint=False, group="unknown", rule_metadata=None,
                goref_metadata=None, ref_species_metadata=None, db_type_name_regex_id_syntax=None,
                retracted_pub_set=None, db_entities=None, group_idspace=None,
                format="gaf", suppress_rule_reporting_tags=[], annotation_inferences=None, group_metadata=None,
                extensions_constraints=None, rule_contexts=[], gaf_output_version="2.2",
                rule_set=assocparser.RuleSet.ALL) -> list[str]:
    filtered_associations = open(os.path.join(os.path.split(source_gaf)[0], "{}_noiea.gaf".format(dataset)), "w")
    config = assocparser.AssocParserConfig(
        ontology=ontology_graph,
        filter_out_evidence=["IEA"],
        filtered_evidence_file=filtered_associations,
        gpi_authority_path=gpipaths,
        paint=paint,
        rule_metadata=rule_metadata,
        goref_metadata=goref_metadata,
        ref_species_metadata=ref_species_metadata,
        db_type_name_regex_id_syntax=db_type_name_regex_id_syntax,
        retracted_pub_set=retracted_pub_set,
        entity_idspaces=db_entities,
        group_idspace=group_idspace,
        suppress_rule_reporting_tags=suppress_rule_reporting_tags,
        annotation_inferences=annotation_inferences,
        group_metadata=group_metadata,
        extensions_constraints=extensions_constraints,
        rule_contexts=rule_contexts,
        rule_set=rule_set,
    )
    click.echo("Producing {}".format(source_gaf))
    # logger.info("AssocParserConfig used: {}".format(config))
    split_source = os.path.split(source_gaf)[0]
    validated_gaf_path = os.path.join(split_source, "{}_valid.gaf".format(dataset))
    outfile = open(validated_gaf_path, "w")
    gafwriter = GafWriter(file=outfile, source=dataset, version=gaf_output_version)

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
    click.echo("About to write markdown report to {}".format(report_markdown_path))
    with open(report_markdown_path, "w") as report_md:
        click.echo("Opened for writing {}".format(report_markdown_path))
        report_md.write(parser.report.to_markdown())

    click.echo("markdown {} written out".format(report_markdown_path))
    # click.echo("Markdown current stack:")
    # if logger.getEffectiveLevel() == logging.INFO:
    #     traceback.print_stack()

    report_json_path = os.path.join(os.path.split(source_gaf)[0], "{}.report.json".format(dataset))
    click.echo("About to write json report to {}".format(report_json_path))
    with open(report_json_path, "w") as report_json:
        click.echo("Opened for writing {}".format(report_json_path))
        report_json.write(json.dumps(parser.report.to_report_json(), indent=4))

    click.echo("json {} written out".format(report_markdown_path))
    click.echo("gorule-13 first 10 messages: {}".format(
        json.dumps(parser.report.to_report_json()["messages"].get("gorule-0000013", [])[:10], indent=4)))
    # logger.info("json current Stack:")
    # if logger.getEffectiveLevel() == logging.INFO:
    #     traceback.print_stack()

    return [validated_gaf_path, filtered_associations.name]


@tools.gzips
def make_ttls(dataset, gaf_path, products, ontology_graph):
    with open(gaf_path) as sg:
        lines = sum(1 for line in sg)

    product_files = {
        "ttl": open(os.path.join(os.path.split(gaf_path)[0], "{}_cam.ttl".format(dataset)), "wb")
    }

    if not products["ttl"]:
        # Bail if we have no products
        return []

    # def write_gpi_entity(association, bridge, gpiwriter):
    with open(gaf_path) as gf:
        gafparser = GafParser(config=assocparser.AssocParserConfig(
            ontology=ontology_graph,
            paint=True,
        ))

        # gpi info:
        click.echo("Using {} as the gaf to build data products with".format(gaf_path))
        if products["ttl"]:
            click.echo("Setting up {}".format(product_files["ttl"].name))
            rdf_writer = assoc_rdfgen.TurtleRdfWriter(label=os.path.split(product_files["ttl"].name)[1])
            transformer = assoc_rdfgen.CamRdfTransform(writer=rdf_writer)

        click.echo("Making ttl products...")
        with click.progressbar(iterable=gafparser.association_generator(file=gf), length=lines) as associations:
            for association in associations:
                if products["ttl"]:
                    transformer.provenance()
                    transformer.translate(association)

        # post ttl steps
        if products["ttl"]:
            click.echo("Writing ttl to disk")
            rdf_writer.serialize(destination=product_files["ttl"])

        # After we run through associations
        for f in product_files.values():
            f.close()

    return [product_files[prod].name for prod in sorted(product_files.keys()) if products[prod]]


@tools.gzips
def make_gpads(dataset, gaf_path, products, ontology_graph,
               noctua_gpad_file, paint_gaf_src, gpi, gpad_gpi_output_version) -> (List[GoAssociation], List[str]):
    """
    Using the gaf files and the noctua gpad file, produce a gpad file that contains both kinds of annotations
    without any loss.

    :param dataset: The dataset name
    :param gaf_path: The path to the gaf file
    :param products: The products to make
    :param ontology_graph: The ontology graph to use for parsing the associations
    :param noctua_gpad_file: The path to the noctua gpad file
    :param paint_gaf_src: The source of the paint gaf file
    :param gpi: The path to the gpi file -- needed to convert isoform annotations from Noctua files
                                            to gene annotations in GAF outputs.
    :return: (The path to the gpad file, the headers from all the files that contributed to the final GPAD file)

    """
    gpad_file_path = os.path.join(os.path.split(gaf_path)[0], f"{dataset}.gpad")

    if not products["gpad"]:
        return []
    noctua_header = None
    all_gaf_headers = None
    noctua_associations = []
    all_gaf_associations = []

    # Open the file once and keep it open for all operations within this block
    with open(gpad_file_path, "w") as outfile:
        gpadwriter = GpadWriter(file=outfile, version=gpad_gpi_output_version)
        headers = []
        # If there's a noctua gpad file, process it, return the parsing Report so we can get its headers for
        # the final file provenance
        if noctua_gpad_file:
            click.echo("Making noctua gpad products...")
            # Process noctua gpad file
            (noctua_associations, noctua_header) = process_noctua_gpad_file(noctua_gpad_file, ontology_graph)
            headers.append(noctua_header)
        # Process the GAF file, store the report object so we can get its headers for the final file provenance
        (all_gaf_associations, all_gaf_headers) = process_gaf_file(gaf_path, ontology_graph, paint_gaf_src)

        if noctua_header:
            for header in noctua_header:
                gpadwriter._write("!Header from source noctua GPAD file\n")
                gpadwriter._write("!=================================\n")
                gpadwriter._write(header)
        if all_gaf_headers:
            for header in all_gaf_headers:
                gpadwriter._write("!Header from source GAF file(s)\n")
                gpadwriter._write("!=================================\n")
                for header_line in header:
                    gpadwriter._write(header_line+"\n")

        click.echo("Wrote all headers for GPAD, now writing associations...")
        if noctua_associations:
            for assoc in noctua_associations:
                gpadwriter.write_assoc(assoc)
        if all_gaf_associations:
            for assoc in all_gaf_associations:
                gpadwriter.write_assoc(assoc)

    # The file will be automatically closed here, after exiting the 'with' block
    return [gpad_file_path]

def process_noctua_gpad_file(noctua_gpad_file, ontology_graph) -> (List[GoAssociation], List[str]):
    """
    Process a noctua gpad file and write the associations to the gpad writer.

    :param noctua_gpad_file: The path to the noctua gpad file
    :param ontology_graph: The ontology graph to use for parsing the associations
    """

    processed_associations = []
    with open(noctua_gpad_file) as nf:
        lines = sum(1 for line in nf)
        nf.seek(0)  # Reset file pointer to the beginning after counting lines
        gpadparser = GpadParser(config=assocparser.AssocParserConfig(ontology=ontology_graph,
                                                                     paint=False,
                                                                     rule_set="all"))

        click.echo("Making noctua gpad products...")
        with click.progressbar(iterable=gpadparser.association_generator(file=nf), length=lines) as associations:
            for association in associations:
                # If the association is an isoform annotation, convert it to a gene annotation
                processed_associations.append(association)

    return processed_associations, gpadparser.report.header


def process_gaf_file(gaf_path, ontology_graph, paint_gaf_src) -> (List[GoAssociation], List[str]):
    """
    Process a gaf file and write the associations to the gpad writer.

    :param gaf_path: The path to the gaf file
    :param ontology_graph: The ontology graph to use for parsing the associations
    :param paint_gaf_src: The source of the paint gaf file

    :return: The headers from the variious gaf files in a list of Report objects
    """
    headers = []
    associations = []
    with open(gaf_path) as gf:
        lines = sum(1 for line in gf)
        gf.seek(0)  # Reset file pointer to the beginning after counting lines
        gafparser = GafParser(config=assocparser.AssocParserConfig(ontology=ontology_graph,
                                                                   paint=True,
                                                                   rule_set="all"))
        click.echo("Merging in source gaf to gpad product...")
        with click.progressbar(iterable=gafparser.association_generator(file=gf), length=lines) as gaf_assocs:
            for association in gaf_assocs:
                associations.append(association)
        headers.append(gafparser.report.header)

    if paint_gaf_src is not None:
        with open(paint_gaf_src) as pgf:
            lines = sum(1 for line in pgf)
            pgf.seek(0)
            gafparser = GafParser(config=assocparser.AssocParserConfig(ontology=ontology_graph,
                                                                       paint=True,
                                                                       rule_set="all"))
            click.echo("Merging in paint gaf to gpad product...")
            with click.progressbar(iterable=gafparser.association_generator(file=pgf), length=lines) as paint_assocs:
                for association in paint_assocs:
                    associations.append(association)
            headers.append(gafparser.report.header)

    return associations, headers

@tools.gzips
def produce_gpi(dataset, target_dir, gaf_path, ontology_graph, gpad_gpi_output_version):
    gafparser = GafParser()
    gafparser.config = assocparser.AssocParserConfig(
        ontology=ontology_graph
    )
    with open(gaf_path) as sg:
        lines = sum(1 for line in sg)

    gpi_path = os.path.join(os.path.split(gaf_path)[0], "{}.gpi".format(dataset))
    with open(gaf_path) as gf, open(gpi_path, "w") as gpi:
        click.echo("Using {} as the gaf to build gpi with".format(gaf_path))
        bridge = gafgpibridge
        gpiwriter = entitywriter.GpiWriter(file=gpi, version=gpad_gpi_output_version)
        gpi_cache = set()

        with click.progressbar(iterable=gafparser.association_generator(file=gf), length=lines) as associations:
            for association in associations:
                entity = bridge.convert_association(association)
                if entity not in gpi_cache and entity is not None:
                    # If the entity is not in the cache, add it and write it out
                    gpi_cache.add(entity)
                    gpiwriter.write_entity(entity)
    print("Wrote gpi to disk: {}".format(gpi_path))
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


def mixin_a_dataset(valid_gaf, mixin_metadata_list, group_id, dataset, target, ontology, gpipaths=None,
                    base_download_url=None, rule_metadata={}, replace_existing_files=True, rule_contexts=[],
                    gaf_output_version="2.2"):
    end_gaf = valid_gaf
    mixin_gaf_paths = []
    for mixin_metadata in mixin_metadata_list:
        click.echo("Merging mixin dataset {}".format(mixin_metadata["id"]))
        mixin_src = check_and_download_mixin_source(mixin_metadata, group_id, dataset, target,
                                                    base_download_url=base_download_url,
                                                    replace_existing_files=replace_existing_files)

        if mixin_src is not None:
            mixin_dataset_metadata = mixin_dataset(mixin_metadata, dataset)
            mixin_dataset_id = mixin_dataset_metadata["dataset"]
            format = mixin_dataset_metadata["type"]
            context = ["import"] if mixin_metadata.get("import", False) else []
            mixin_gaf = produce_gaf(mixin_dataset_id, mixin_src, ontology, gpipaths=gpipaths, paint=True,
                                    group=mixin_metadata["id"], rule_metadata=rule_metadata, format=format,
                                    rule_contexts=context, gaf_output_version=gaf_output_version)[0]
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
@click.option("--gpad-gpi-output-version", default="1.2", type=click.Choice(["1.2", "2.0"]))
@click.option("--ttl", default=False, is_flag=True)
@click.option("--target", "-t", type=click.Path(), required=True)
@click.option("--ontology", "-o", type=click.Path(exists=True), required=False)
@click.option("--exclude", "-x", multiple=True)
@click.option("--base-download-url", "-b", default=None)
@click.option("--suppress-rule-reporting-tag", "-S", multiple=True,
              help="Suppress markdown output messages from rules tagged with this tag")
@click.option("--skip-existing-files", "-K", is_flag=True, default=False,
              help="When downloading files, if a file already exists it won't downloaded over")
@click.option("--gaferencer-file", "-I", type=click.Path(exists=True), default=None, required=False,
              help="Path to Gaferencer output to be used for inferences")
@click.option("--only-dataset", default=None)
@click.option("--gaf-output-version", default="2.2", type=click.Choice(["2.1", "2.2"]))
@click.option("--rule-set", "-l", "rule_set", default=[assocparser.RuleSet.ALL], multiple=True)
@click.option("--retracted_pub_set", type=click.Path(exists=True), default=None, required=False,
              help="Path to retracted publications file")
def produce(ctx, group, metadata_dir, gpad, gpad_gpi_output_version, ttl, target, ontology, exclude, base_download_url,
            suppress_rule_reporting_tag, skip_existing_files, gaferencer_file, only_dataset, gaf_output_version,
            rule_set, retracted_pub_set):
    """
    Produce GAF, GPI, and TTL files for a group.

    This command will download the GAF files for a group, validate them, and then produce GPI and TTL files.
    :param ctx: Click context
    :param group: The group to produce files for
    :param metadata_dir: The directory containing the metadata files
    :param gpad: Produce GPAD files
    :param gpad_gpi_output_version: The version of the GPAD and GPI files to produce
    :param ttl:  TTL files
    :param target: The directory to put the files in
    :param ontology: The ontology to use for validation
    :param exclude: Datasets to exclude
    :param base_download_url: The base URL to download files from
    :param suppress_rule_reporting_tag: Tags to suppress in the rule reporting
    :param skip_existing_files: Skip downloading files that already exist
    :param gaferencer_file: The path to the Gaferencer output file
    :param only_dataset: Only process a single dataset
    :param gaf_output_version: The version of the GAF files to produce
    :param rule_set: The rule set to use
    :param retracted_pub_set: The path to the retracted publications file
    """
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

    print("group", group)
    group_metadata = metadata.dataset_metadata_file(absolute_metadata, group)
    click.echo("Loading ontology: {}...".format(ontology))
    ontology_graph = OntologyFactory().create(ontology, ignore_cache=True)

    downloaded_gaf_sources = download_source_gafs(group_metadata, absolute_target, exclusions=exclude,
                                                  base_download_url=base_download_url,
                                                  replace_existing_files=not skip_existing_files,
                                                  only_dataset=only_dataset)

    click.echo("Downloaded GAF sources")
    # extract the titles for the go rules, this is a dictionary comprehension
    rule_metadata = metadata.yamldown_lookup(os.path.join(absolute_metadata, "rules"))
    goref_metadata = metadata.yamldown_lookup(os.path.join(absolute_metadata, "gorefs"))
    ref_species_metadata = metadata.yaml_set(absolute_metadata, "go-reference-species.yaml", "taxon_id")

    click.echo("Found {} GO Rules".format(len(rule_metadata.keys())))
    click.echo("Found {} GO_REFs".format(len(goref_metadata.keys())))
    click.echo("Found {} Reference Species".format(len(ref_species_metadata)))

    paint_metadata = metadata.dataset_metadata_file(absolute_metadata, "paint")
    noctua_metadata = metadata.dataset_metadata_file(absolute_metadata, "noctua")
    mixin_metadata_list = list(filter(lambda m: m != None, [paint_metadata]))

    db_entities = metadata.database_entities(absolute_metadata)
    group_ids = metadata.groups(absolute_metadata)
    extensions_constraints = metadata.extensions_constraints_file(absolute_metadata)

    gaferences = None
    if gaferencer_file:
        gaferences = gaference.load_gaferencer_inferences_from_file(gaferencer_file)

    # Default comes through as single-element tuple
    if rule_set == (assocparser.RuleSet.ALL,):
        rule_set = assocparser.RuleSet.ALL

    db_type_name_regex_id_syntax = metadata.database_type_name_regex_id_syntax(absolute_metadata)

    if retracted_pub_set:
        retracted_pubs = metadata.retracted_pub_set(retracted_pub_set)
    else:
        retracted_pubs = metadata.retracted_pub_set_from_meta(absolute_metadata)

    for dataset_metadata, source_gaf in downloaded_gaf_sources:
        dataset = dataset_metadata["dataset"]
        # Set paint to True when the group is "paint".
        # This will prevent filtering of IBA (GO_RULE:26) when paint is being treated as a top level group,
        # like for paint_other.
        click.echo("Producing GAF by passing through validation rules... {}".format(dataset))
        valid_gaf = produce_gaf(dataset, source_gaf, ontology_graph,
                                paint=(group == "paint"),
                                group=group,
                                rule_metadata=rule_metadata,
                                goref_metadata=goref_metadata,
                                ref_species_metadata=ref_species_metadata,
                                db_type_name_regex_id_syntax=db_type_name_regex_id_syntax,
                                retracted_pub_set=retracted_pubs,
                                db_entities=db_entities,
                                group_idspace=group_ids,
                                suppress_rule_reporting_tags=suppress_rule_reporting_tag,
                                annotation_inferences=gaferences,
                                group_metadata=group_metadata,
                                extensions_constraints=extensions_constraints,
                                rule_contexts=["import"] if dataset_metadata.get("import", False) else [],
                                gaf_output_version=gaf_output_version,
                                rule_set=rule_set
                                )[0]

        gpi_list = []

        matching_gpi_path = None
        click.echo("Try to find other GPIs in metadata and merge...")

        for ds in group_metadata["datasets"]:
            # Where type=GPI for the same dataset (e.g. "zfin", "goa_cow")
            if ds["type"] == "gpi" and ds["dataset"] == dataset and ds.get("source"):
                matching_gpi_path = download_a_dataset_source(group, ds, absolute_target, ds["source"],
                                                              replace_existing_files=not skip_existing_files)
                if ds.get("compression", None) == "gzip":
                    matching_gpi_path = unzip_simple(matching_gpi_path)
                gpi_list.append(matching_gpi_path)

        click.echo("Found the matching gpi path...{}".format(matching_gpi_path))

        click.echo("Downloading the noctua and paint GPAD files...")
        noctua_gpad_src = check_and_download_mixin_source(noctua_metadata, group_metadata["id"], dataset, target,
                                                          base_download_url=base_download_url,
                                                          replace_existing_files=not skip_existing_files)
        paint_gaf_src = (check_and_download_mixin_source(paint_metadata, group_metadata["id"], dataset, target,
                                                         base_download_url=base_download_url,
                                                         replace_existing_files=not skip_existing_files)
                         if paint_metadata else None)

        click.echo("Producing GPI for use in creating GPADs...")
        gpi = produce_gpi(dataset, absolute_target, valid_gaf, ontology_graph, gpad_gpi_output_version)
        click.echo("GPI file produced first time...{}".format(gpi))
        gpi_list.append(gpi)
        click.echo("GPI list...{}".format(gpi_list))
        click.echo("Executing 'make_gpads' in validate.produce with all the assembled GAF files...")
        make_gpads(dataset, valid_gaf, products,
                   ontology_graph, noctua_gpad_src, paint_gaf_src,
                   gpi, gpad_gpi_output_version)


        end_gaf = mixin_a_dataset(valid_gaf, [noctua_metadata, paint_metadata],
                                  group_metadata["id"], dataset, absolute_target,
                                  ontology_graph, gpipaths=gpi_list, base_download_url=base_download_url,
                                  rule_metadata=rule_metadata, replace_existing_files=not skip_existing_files,
                                  gaf_output_version=gaf_output_version)
        click.echo("Merged mixin datasets into the final GAF...{}".format(end_gaf))

        click.echo("Pre-isoform fix gaf file...{}".format(end_gaf))
        click.echo("Executing the isoform fixing step in validate.produce...")
        # run the resulting gaf through one last parse and replace, to handle the isoforms
        # see: https://github.com/geneontology/go-site/issues/2291
        click.echo("path to end gaf _temp.gaf")

        click.echo(os.path.split(end_gaf)[0])
        temp_output_gaf_path = os.path.join(os.path.split(end_gaf)[0], "{}_temp.gaf".format(dataset))
        click.echo("temp_output_gaf_path: {}".format(temp_output_gaf_path))
        click.echo("matching_gpi_path: {}".format(gpi))

        if matching_gpi_path is None:
            matching_gpi_path = gpi
        isoform_fixed_gaf = fix_pro_isoforms_in_gaf(end_gaf, matching_gpi_path, ontology_graph, temp_output_gaf_path)
        click.echo("isoform_fixed_gaf: {}".format(isoform_fixed_gaf))

        final_output_gaf_path = os.path.join(os.path.split(end_gaf)[0], "{}.gaf".format(dataset))

        click.echo("Rename the temporary isoform fixed file to the final GAF...")
        os.rename(temp_output_gaf_path, final_output_gaf_path)
        click.echo("final_output_gaf_path: {}".format(final_output_gaf_path))

        click.echo("Producing final GPI after all GAF corrections...")
        final_gpi = produce_gpi(dataset, absolute_target, final_output_gaf_path, ontology_graph, gpad_gpi_output_version)
        click.echo("final_gpi: {}".format(final_gpi))

        click.echo("Creating ttl files...")
        make_ttls(dataset, final_output_gaf_path, products, ontology_graph)


def fix_pro_isoforms_in_gaf(gaf_file_to_fix: str,
                            gpi_file: str,
                            ontology_graph,
                            output_file_path: str) -> str:
    """
    Given a GAF file and a GPI file, fix the GAF file by converting isoform annotations to gene annotations. Storing
    the isoforms back in subject_extensions collection, changing the full_name, synonyms, label, and type back to the
    gene in the GPI file.
    :param gaf_file_to_fix: The path to the GAF file to fix
    :param gpi_file: The path to the GPI file
    :param ontology_graph: The ontology graph to use for parsing the associations
    :param output_file_path: The path to write the fixed GAF file to
    :return: The path to the fixed GAF file
    """
    fixed_associations = []
    print("gpi_file", gpi_file)
    if gpi_file is None:
        raise ValueError("GPI file is required to fix the GAF file.", gpi_file)
    gpiparser = GpiParser(config=assocparser.AssocParserConfig(ontology=ontology_graph))
    # Parse the GPI file, creating a map of identifiers to GPI entries
    gpis = gpiparser.parse(gpi_file, None)
    gpi_map = {}
    for gpi_entry in gpis:
        gpi_map[gpi_entry.get('id')] = {"encoded_by": gpi_entry.get('encoded_by'),
                                        "full_name": gpi_entry.get('full_name'),
                                        "label": gpi_entry.get('label'),
                                        "synonyms": gpi_entry.get('synonyms'),
                                        # GPI spec says this is single valued, but GpiParser returns this as a list.
                                        "type": gpi_entry.get('type')[0],
                                        "id": gpi_entry.get('id')}

    gafparser = GafParser(config=assocparser.AssocParserConfig(ontology=ontology_graph))
    gafwriter = GafWriter(file=open(output_file_path, "w"), version="2.2")

    # these are statistic parameters that record when a substitution is made.
    substitution_count = 0
    no_substitution_count = 0

    with open(gaf_file_to_fix, "r") as file:
        for line in file:
            annotation = gafparser.parse_line(line)
            for source_assoc in annotation.associations:
                if isinstance(source_assoc, dict):
                    continue  # skip the header
                if source_assoc.subject.id.namespace.startswith("PR"):
                    full_old_identifier = source_assoc.subject.id.namespace + ":" + source_assoc.subject.id.identity
                    old_namespace = source_assoc.subject.id.namespace
                    old_identity = source_assoc.subject.id.identity
                    # TODO: right now we get the FIRST encoded_by result -- this is what the original script did?
                    if "MGI" == gpi_map[full_old_identifier].get("encoded_by")[0].split(":")[0]:
                        source_assoc.subject.id.namespace = gpi_map[full_old_identifier].get("encoded_by")[0].split(":")[0]
                        source_assoc.subject.id.identity = "MGI:" + gpi_map[full_old_identifier].get("encoded_by")[0].split(":")[2]
                    else:
                        source_assoc.subject.id.namespace = \
                        gpi_map[full_old_identifier].get("encoded_by")[0].split(":")[0]
                        source_assoc.subject.id.identity = \
                        gpi_map[full_old_identifier].get("encoded_by")[0].split(":")[1]
                    full_new_identifier = source_assoc.subject.id.namespace + ":" + source_assoc.subject.id.identity
                    source_assoc.subject.full_name = gpi_map[full_new_identifier].get("full_name")
                    source_assoc.subject.label = gpi_map[full_new_identifier].get("label")
                    source_assoc.subject.synonyms = gpi_map[full_new_identifier].get("synonyms")
                    source_assoc.subject.type = gpi_map[full_new_identifier].get("type")

                    # we need to put the isoform currently being swapped, back into "Column 17" which is a
                    # subject_extension member.
                    isoform_term = Curie(namespace=old_namespace, identity=old_identity)
                    isoform_relation = Curie(namespace="RO", identity="0002327")
                    new_subject_extension = ExtensionUnit(relation=isoform_relation, term=isoform_term)
                    source_assoc.subject_extensions.append(new_subject_extension)

                    # count the substitution here for reporting later
                    substitution_count += 1
                else:
                    no_substitution_count += 1

                # Join fields back into a string and write to output file
                fixed_associations.append(source_assoc)

    gafwriter.write(fixed_associations)
    click.echo(f"Substituted {substitution_count} entries in {gaf_file_to_fix} "
               f"and left {no_substitution_count} entries unchanged.")

    return output_file_path

@cli.command()
@click.pass_context
@click.option("--gpad_path", "-g", type=click.Path(), required=True)
@click.option("--gpi_path", "-i", type=click.Path(), required=True)
@click.option("--target", "-t", type=click.Path(), required=True)
@click.option("--ontology", "-o", type=click.Path(exists=True), required=True, multiple=True)
@click.option("--ttl", default=False, is_flag=True)
@click.option("--modelstate", "-s", default=None)
def gpad2gocams(ctx, gpad_path, gpi_path, target, ontology, ttl, modelstate):
    # NOTE: Validation on GPAD not included here since it's currently baked into produce() above.
    # Multi-param to accept multiple ontology files, then merge to one (this will make a much smaller ontology
    #  with only what we need, i.e. GO, RO, GOREL)
    ontology_graph = OntologyFactory().create(ontology[0], ignore_cache=True)
    for ont in ontology[1:]:
        ontology_graph.merge([OntologyFactory().create(ont, ignore_cache=True)])
    parser_config = assocparser.AssocParserConfig(ontology=ontology_graph,
                                                  gpi_authority_path=gpi_path
                                                  )
    extractor = AssocExtractor(gpad_path, parser_config=parser_config)
    assocs_by_gene = extractor.group_assocs()

    absolute_target = os.path.abspath(target)
    gpad_basename = os.path.basename(gpad_path)
    gpad_basename_root, gpad_ext = os.path.splitext(gpad_basename)
    output_basename = "{}.nq".format(gpad_basename_root)
    report_basename = "{}.gocamgen.report".format(gpad_basename_root)
    output_path = os.path.join(absolute_target, output_basename)
    report_path = os.path.join(absolute_target, report_basename)

    builder = GoCamBuilder(parser_config=parser_config, modelstate=modelstate)

    for gene, associations in assocs_by_gene.items():
        if ttl:
            builder.make_model_and_write_out(gene, annotations=associations, output_directory=absolute_target)
        else:
            builder.make_model_and_add_to_store(gene, annotations=associations)
    if not ttl:
        builder.write_out_store_to_nquads(filepath=output_path)

    builder.write_report(report_filepath=report_path)


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
@click.option("--gaferencer-file", "-I", type=click.Path(exists=True), default=None, required=False,
              help="Path to Gaferencer output to be used for inferences")
@click.option("--retracted_pub_set", type=click.Path(exists=True), default=None, required=False,
              help="Path to retracted publications file")
def rule(metadata_dir, out, ontology, gaferencer_file, retracted_pub_set):
    absolute_metadata = os.path.abspath(metadata_dir)

    click.echo("Loading ontology: {}...".format(ontology))
    ontology_graph = OntologyFactory().create(ontology)

    goref_metadata = metadata.yamldown_lookup(os.path.join(absolute_metadata, "gorefs"))
    gorule_metadata = metadata.yamldown_lookup(os.path.join(absolute_metadata, "rules"))
    ref_species_metadata = metadata.yaml_set(absolute_metadata, "go-reference-species.yaml", "taxon_id")
    db_type_name_regex_id_syntax = metadata.database_type_name_regex_id_syntax(absolute_metadata)
    retracted_pubs = None
    if retracted_pub_set:
        retracted_pubs = metadata.retracted_pub_set(retracted_pub_set)
    else:
        retracted_pubs = metadata.retracted_pub_set_from_meta(absolute_metadata)

    click.echo("Found {} GO Rules".format(len(gorule_metadata.keys())))

    db_entities = metadata.database_entities(absolute_metadata)
    group_ids = metadata.groups(absolute_metadata)

    gaferences = None
    if gaferencer_file:
        gaferences = gaference.load_gaferencer_inferences_from_file(gaferencer_file)

    config = assocparser.AssocParserConfig(
        ontology=ontology_graph,
        goref_metadata=goref_metadata,
        ref_species_metadata=ref_species_metadata,
        db_type_name_regex_id_syntax=db_type_name_regex_id_syntax,
        retracted_pub_set=retracted_pubs,
        entity_idspaces=db_entities,
        group_idspace=group_ids,
        annotation_inferences=gaferences,
        rule_set=assocparser.RuleSet.ALL
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
