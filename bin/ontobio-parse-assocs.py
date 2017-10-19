#!/usr/bin/env python

"""
Command line wrapper to gafparser.py

Type:

    ogr-parse-assocs -h

For instructions

Examples:

```
```

"""

import argparse
import networkx as nx
from networkx.algorithms.dag import ancestors, descendants
from ontobio.assoc_factory import AssociationSetFactory
from ontobio.ontol_factory import OntologyFactory
from ontobio.io import entityparser
from ontobio.io.gafparser import GafParser
from ontobio.io.gpadparser import GpadParser
from ontobio.io.hpoaparser import HpoaParser
from ontobio.io.assocwriter import GafWriter, GpadWriter
from ontobio.io import assocparser
from ontobio.slimmer import get_minimal_subgraph
import json
import logging

def main():
    """
    Wrapper for Assoc Parsing
    """
    parser = argparse.ArgumentParser(description='Wrapper for obographs assocmodel library'
                                                 """
                                                 By default, ontologies and assocs are cached locally and synced from a remote sparql endpoint
                                                 """,
                                     formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('-r', '--resource', type=str, required=False,
                        help='Name of ontology')
    parser.add_argument('-f', '--file', type=str, required=False,
                        help='Name of input file for associations - currently GAF is assumed')
    parser.add_argument('-F', '--format', type=str, required=False,
                        help='Format of assoc file. One of GAF, GPAD or HPOA')
    parser.add_argument('-o', '--outfile', type=str, required=False,
                        help='Path to output file')
    parser.add_argument("--report-md", type=str, required=False, dest="report_md",
                        help="Path to report markdown file")
    parser.add_argument("--report-json", type=str, required=False, dest="report_json",
                        help="Path to report JSON file")
    parser.add_argument('-t', '--to', type=str, required=False,
                        help='Output to (tree, dot, ...)')
    parser.add_argument("--filter-out", nargs="+", required=False, default=[], metavar="EVIDENCE",
                        help="List of any evidence codes to filter out of the GAF. E.G. --filter-out IEA IMP")
    parser.add_argument("--filtered-file", required=False, default=None, metavar="FILTERED_FILE",
                        help="File to write the filtered out evidence GAF to")
    parser.add_argument('-T', '--taxon', nargs='*', required=False,
                        help='valid taxon (NCBITaxon ID) - validate against this')
    parser.add_argument('--subject_prefix', nargs='*', required=False,
                        help='E.g PomBase - validate against this')
    parser.add_argument('--object_prefix', nargs='*', required=False,
                        help='E.g GO - validate against this')
    parser.add_argument('-v', '--verbosity', default=0, action='count',
                        help='Increase output verbosity')


    subparsers = parser.add_subparsers(dest='subcommand', help='sub-command help')

    parser_n = subparsers.add_parser('validate', help='Validate associations')
    parser_n.set_defaults(function=validate_assocs)

    parser_n = subparsers.add_parser('filter', help='Filter associations')
    parser_n.set_defaults(function=filter_assocs)

    parser_n = subparsers.add_parser('convert', help='Convert associations')
    parser_n.set_defaults(function=convert_assocs)
    parser_n.add_argument('-t', '--to', type=str, required=True,
                          help='Format to convert to')

    parser_n = subparsers.add_parser('map2slim', help='Map to a subset/slim')
    parser_n.set_defaults(function=map2slim)
    parser_n.add_argument('-p', '--properties', nargs='*', type=str, default=['subClassOf', 'BFO:0000050'],
                          help='Properties')
    parser_n.add_argument('-s', '--subset', type=str, required=True,
                          help='subset (e.g. map2slim)')

    args = parser.parse_args()

    if args.verbosity >= 2:
        logging.basicConfig(level=logging.DEBUG)
    elif args.verbosity == 1:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)

    logging.info("Welcome!")

    handle = args.resource

    # Ontology Factory
    ofactory = OntologyFactory()
    logging.info("Creating ont object from: {} {}".format(handle, ofactory))
    ont = ofactory.create(handle)
    logging.info("ont: {}".format(ont))

    func = args.function

    # Upper case all evidence codes
    args.filter_out = [code.upper() for code in args.filter_out]

    # set configuration
    filtered_evidence_file = open(args.filtered_file, "w") if args.filtered_file else None
    config = assocparser.AssocParserConfig(
        valid_taxa=args.taxon,
        ontology=ont,
        class_idspaces=args.object_prefix,
        entity_idspaces=args.subject_prefix,
        filter_out_evidence=args.filter_out,
        filtered_evidence_file=filtered_evidence_file
    )
    p = None
    fmt = None
    if args.format is None:
        fmt = 'gaf'
    else:
        fmt = args.format.lower()

    # TODO: use a factory
    if fmt == 'gaf':
        p = GafParser()
    elif fmt == 'gpad':
        p = GpadParser()
    elif fmt == 'hpoa':
        p = HpoaParser()
    elif fmt == "gpi":
        p = entityparser.GpiParser()
        func = validate_entity

    p.config = config

    outfh = None
    if args.outfile is not None:
        two_mb = 2097152
        outfh = open(args.outfile, "w", buffering=two_mb)
    func(ont, args.file, outfh, p, args)
    if filtered_evidence_file:
        filtered_evidence_file.close()

    if outfh is not None:
        outfh.close()

    if args.report_md is not None:
        report_md = open(args.report_md, "w")
        report_md.write(p.report.to_markdown())
        report_md.close()
    if args.report_json is not None:
        report_json = open(args.report_json, "w")
        report_json.write(json.dumps(p.report.to_report_json(), indent=4))
        report_json.close()
    if not (args.report_md or args.report_json):
        print(p.report.to_markdown())

def filter_assocs(ont, file, outfile, p, args):
    p.generate_associations(open(file, "r"), outfile)

def validate_assocs(ont, file, outfile, p, args):
    gafwriter = GafWriter(file=outfile)

    with open(file) as gafsource:
        associations = p.association_generator(file=gafsource)
        for assoc in associations:
            gafwriter.write_assoc(assoc)

def validate_entity(ont, file, outfile, p, args):
    p.parse(open(file, "r"), outfile)

def convert_assocs(ont, file, outfile, p, args):
    assocs = p.parse(open(file, "r"), None)
    write_assocs(assocs, outfile, args)

def write_assocs(assocs, outfile, args):
    w = GpadWriter()
    fmt = args.to
    if fmt is None or fmt == 'gaf':
        w = GafWriter()
    elif fmt == 'gpad':
        w = GpadWriter()
    else:
        raise ValueError("Not supported: {}".format(fmt))
    w.file = outfile
    w.write(assocs)

def map2slim(ont, file, outfile, p, args):
    logging.info("Mapping to {}".format(args.subset))
    assocs = p.map_to_subset(open(file, "r"),
                             ontology=ont, outfile=outfile, subset=args.subset, relations=args.properties)
    #write_assocs(assocs, outfile, args)

def _default(something, default):
    if something is None:
        return default
    else:
        return something


if __name__ == "__main__":
    main()
