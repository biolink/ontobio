from ontobio.io.gpadparser import GpadParser
from ontobio.model.association import GoAssociation
from ontobio import ecomap
import click
import logging
import pandas as pd
import numpy as np

logger = logging.getLogger("INFER")
logger.setLevel(logging.WARNING)


@click.command()
@click.option("--gpad1", "-gp1", type=click.Path(), required=True)
@click.option("--gpad2", "-gp2", type=click.Path(), required=True)
@click.option("--output", "-o", type=click.File("a"), required=True)
@click.option("--count_by", "-cb", multiple=True, required=False)
@click.option("--exclude_details", "-ed", type=click.BOOL, default=False, required=False)
def compare_gpad_objects(gpad1, gpad2, output, count_by, exclude_details):
    print("Starting comparison ")
    print("")
    gpad_parser_1 = GpadParser()
    gpad_parser_2 = GpadParser()
    assocs1 = gpad_parser_1.parse(gpad1, skipheader=True)
    assocs2 = gpad_parser_2.parse(gpad2, skipheader=True)

    df_gpad1 = read_csv(gpad1)
    df_gpad2 = read_csv(gpad2)
    processed_lines = 0
    exact_matches = 0
    close_matches = 0
    stats = calculate_file_stats(df_gpad1, count_by, gpad1)
    stats2 = calculate_file_stats(df_gpad2, count_by, gpad2)
    print(gpad1)
    print(stats)
    print(gpad2)
    print(stats2)

    for association in assocs1:
        processed_lines = processed_lines + 1
        if not exclude_details:
            for target in assocs2:
                match_score = 0
                if association.negated != target.negated:
                    continue
                if association.subject.id == target.subject.id and association.object.id == target.object.id:
                    match_score = 1
                    if sorted(str(q).upper() for q in association.qualifiers) == \
                            sorted(str(q).upper() for q in target.qualifiers):
                        match_score = 2
                        if association.evidence.type == target.evidence.type:
                            match_score = 3
                            if sorted(str(w).upper() for w in association.evidence.with_support_from) == \
                                    sorted(str(w).upper() for w in target.evidence.with_support_from):
                                match_score = 4
                                if sorted(
                                        str(r).upper() for r in association.evidence.has_supporting_reference) == \
                                        sorted(str(r).upper() for r in target.evidence.has_supporting_reference):
                                    match_score = 5
                if match_score > 4:
                    exact_matches = exact_matches + 1
                if 1 < match_score < 5:
                    close_matches = close_matches + 1
    print("")
    print("total number of exact matches = %s" % exact_matches)
    print("total number of close matches = %s" % close_matches)
    print("total number of lines processed = %s" % processed_lines)


def read_csv(filename):
    ecomapping = ecomap.EcoMap()
    data_frame = pd.read_csv(filename,
                             comment='!',
                             sep='\t',
                             header=None,
                             na_filter=False,
                             names=["DB",
                                    "DB_Object_ID",
                                    "Relation",
                                    "Ontology_Class_ID",
                                    "Reference",
                                    "Evidence_type",
                                    "With_or_From",
                                    "Interacting_taxon_ID",
                                    "Date",
                                    "Assigned_by",
                                    "Annotation_Extensions",
                                    "Annotation_Properties"]).fillna("")
    for eco_code in ecomapping.mappings():
        for ev in data_frame['Evidence_type']:
            if eco_code[2] == ev:
                data_frame['Evidence_type'] = data_frame['Evidence_type'].replace([eco_code[2]],
                                                                                  ecomapping.ecoclass_to_coderef(eco_code[2])[0])
    return data_frame


def calculate_file_stats(data_frame, count_by, file):
    stats = {}
    grouped_reports = []
    stats['filename'] = file
    stats['total_rows'] = data_frame.shape[0]
    for grouper in count_by:
        stats['grouper'] = grouper
        grouped_reports.append(data_frame.groupby(grouper)[grouper].count())
        # print(data_frame.groupby(grouper)[grouper].count())
    stats['grouped_reports'] = grouped_reports
    return stats


if __name__ == '__main__':
    compare_gpad_objects()
