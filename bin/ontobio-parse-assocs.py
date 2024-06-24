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
from ontobio.io import gaference
from ontobio.slimmer import get_minimal_subgraph
from ontobio.validation import metadata
import os
import sys
import json
import logging
from typing import Dict, List

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
    parser.add_argument("-I", "--gaferencer-file", type=argparse.FileType('r'), required=False,
                        help="Output from Gaferencer run on a set of GAF annotations")
    parser.add_argument('-v', '--verbosity', default=0, action='count',
                        help='Increase output verbosity')
    parser.add_argument("--allow_paint", required=False, action="store_const", const=True,
                        help="Allow IBAs in parser")
    parser.add_argument("--allow_unmapped_eco", required=False, action="store_const", const=True, default=False,
                        help="When parsing GPAD, allow ECO class IDs that do not map to an ECO GAF code")
    parser.add_argument("-g", "--gpi", type=str, required=False, default=None,
                        help="GPI file")
    parser.add_argument("-m", "--metadata_dir", type=dir_path, required=False,
                        help="Path to metadata directory") 
    parser.add_argument("--retracted_pub_set", type=argparse.FileType('r'), required=False,
                        help="Path to retracted publications file") 
    parser.add_argument("-l", "--rule", action="append", required=None, default=[], dest="rule_set",
                        help="Set of rules to be run. Default is no rules to be run, with the exception \
                            of gorule-0000027 and gorule-0000020. See command line documentation in the \
                                ontobio project or readthedocs for more information")


    subparsers = parser.add_subparsers(dest='subcommand', help='sub-command help')

    parser_n = subparsers.add_parser('validate', help='Validate associations')
    parser_n.set_defaults(function=validate_assocs)

    parser_n = subparsers.add_parser('filter', help='Filter associations')
    parser_n.set_defaults(function=filter_assocs)

    parser_n = subparsers.add_parser('convert', help='Convert associations')
    parser_n.set_defaults(function=convert_assocs)
    parser_n.add_argument('-t', '--to', type=str, required=True, choices=["GAF", "GPAD", "gaf", "gpad"],
                          help='Format to convert to')
    parser_n.add_argument("-n", "--format-version", dest="version", type=str, required=False, default=None,
                          help="Version for the file format. GAF default is 2.1, GPAD default is 1.2")

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

    # Ontology Factory
    ont = None
    if args.resource is not None:
        ofactory = OntologyFactory()
        logging.info("Creating ont object from: {} {}".format(args.resource, ofactory))
        ont = ofactory.create(args.resource)
        logging.info("ont: {}".format(ont))


    func = args.function

    # Upper case all evidence codes
    args.filter_out = [code.upper() for code in args.filter_out]

    gaferences = None
    if args.gaferencer_file:
        gaferences = gaference.build_annotation_inferences(json.load(args.gaferencer_file))

    rule_set = args.rule_set
    if rule_set == ["all"]:
        rule_set = assocparser.RuleSet.ALL
    
    goref_metadata = None
    ref_species_metadata = None
    db_type_name_regex_id_syntax = None      
    if args.metadata_dir:
        absolute_metadata = os.path.abspath(args.metadata_dir)
        goref_metadata = metadata.yamldown_lookup(os.path.join(absolute_metadata, "gorefs"))
        ref_species_metadata = metadata.yaml_set(absolute_metadata, "go-reference-species.yaml", "taxon_id")
        db_type_name_regex_id_syntax = metadata.database_type_name_regex_id_syntax(absolute_metadata)        
        
    retracted_pub_set = None
    if args.retracted_pub_set:
        retracted_pub_set = metadata.retracted_pub_set(args.retracted_pub_set.name)
    elif args.metadata_dir:
       retracted_pub_set = metadata.retracted_pub_set_from_meta(absolute_metadata)     

    # set configuration
    filtered_evidence_file = open(args.filtered_file, "w") if args.filtered_file else None
    config = assocparser.AssocParserConfig(
        valid_taxa=args.taxon,
        ontology=ont,
        class_idspaces=args.object_prefix,
        entity_idspaces=args.subject_prefix,
        filter_out_evidence=args.filter_out,
        filtered_evidence_file=filtered_evidence_file,
        annotation_inferences=gaferences,
        paint=args.allow_paint,
        allow_unmapped_eco=args.allow_unmapped_eco,
        gpi_authority_path=args.gpi,
        goref_metadata=goref_metadata,
        ref_species_metadata=ref_species_metadata,
        db_type_name_regex_id_syntax=db_type_name_regex_id_syntax,
        retracted_pub_set=retracted_pub_set,
        rule_set=rule_set
    )
    p = None
    fmt = None
    if args.format is None:
        fmt = 'gaf'
    else:
        fmt = args.format.lower()

    # TODO: use a factory
    if fmt == 'gaf':
        p = GafParser(config=config, dataset=args.file)
    elif fmt == 'gpad':
        p = GpadParser(config=config)
    elif fmt == 'hpoa':
        p = HpoaParser(config=config)
    elif fmt == "gpi":
        p = entityparser.GpiParser()
        func = validate_entity

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
    w = None
    fmt = args.to.lower()
    version = args.version
    if fmt is None or fmt == 'gaf':
        if version:
            w = GafWriter(file=outfile, version=args.version)
        else:
            w = GafWriter(file=outfile)
    elif fmt == 'gpad':
        if version:
            w = GpadWriter(file=outfile, version=args.version)
        else:
            w = GpadWriter(file=outfile)
    else:
        raise ValueError("Not supported: {}".format(fmt))

    w.write(assocs)

def map2slim(ont, file, outfile, p, args):
    logging.info("Mapping to {}".format(args.subset))
    assocs = p.map_to_subset(open(file, "r"),
                             ontology=ont, outfile=outfile, subset=args.subset, relations=args.properties)
    #write_assocs(assocs, outfile, args)
    
def dir_path(path):
    if os.path.isdir(path):
        return path
    else:
        raise argparse.ArgumentTypeError(f"readable_dir:{path} is not a valid path")
    

def _default(something, default):
    if something is None:
        return default
    else:
        return something


if __name__ == "__main__":
    main()
