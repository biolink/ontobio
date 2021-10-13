from ontobio.io.gpadparser import GpadParser
from ontobio.model.association import GoAssociation
from ontobio.io import assocparser
from ontobio import ecomap
import click
import logging
import pandas as pd
from pandasql import sqldf
import numpy as np

logger = logging.getLogger("INFER")
logger.setLevel(logging.WARNING)


@click.command()
@click.option("--gpad1", "-gp1", type=click.Path(), required=True)
@click.option("--gpad2", "-gp2", type=click.Path(), required=True)
@click.option("--output", "-o", type=click.File("a"), required=True)
@click.option("--count_by", "-cb", multiple=True, required=False)
@click.option("--exclude_details", "-ed", type=click.BOOL, default=True, required=False)
def compare_gpad_objects(gpad1, gpad2, output, count_by, exclude_details):
    print("Starting comparison ")
    print("")
    gpad_parser_1 = GpadParser()
    gpad_parser_2 = GpadParser()
    assocs1 = gpad_parser_1.parse(gpad1, skipheader=True)
    assocs2 = gpad_parser_2.parse(gpad2, skipheader=True)

    df_gpad1 = read_csv(gpad1)
    df_gpad2 = read_csv(gpad2)

    input_lines = 0
    output_lines = 0
    exact_matches = 0
    close_matches = 0
    no_matches = 0

    stats = calculate_file_stats(df_gpad1, count_by, gpad1)
    print(stats)
    print("")
    stats = calculate_file_stats(df_gpad2, count_by, gpad2)
    print(stats)

    missing_rows = []
    for association in assocs1:
        if association in assocs2:
            continue
        else:
            print(association.source_line)
            missing_rows.append(association)
            if not exclude_details:
                match = is_assoc_in_list(association, assocs2)
                print(match)
                if match.__eq__("exact match"):
                    exact_matches = exact_matches + 1
                elif match.__eq__("close match"):
                    close_matches = close_matches + 1
                elif match.__eq__("no match"):
                    no_matches = no_matches + 1
                # print(match + "\t" + item["source_line"])
                input_lines = input_lines + 1
                print('\n gpads', input_lines, ' exact ', exact_matches, ' close ', close_matches, ' none ', no_matches)


def read_csv(filename):
    ecomapping = ecomap.EcoMap()
    data_frame = pd.read_csv(filename,
                             # comment='!',
                             sep='\t',
                             header=0,
                             na_filter=False,
                             names=["DB",
                                    "DB_Object_ID",
                                    "Negation",
                                    "Relation",
                                    "Ontology_Class_ID",
                                    "Reference",
                                    "Evidence_type",
                                    "With_or_From",
                                    "Interacting_taxon_ID",
                                    "Date",
                                    "Assigned_by",
                                    "Annotation_Extensions"  # , "Annotation_Properties"
                                    ]).fillna("")
    for eco_code in ecomapping.mappings():
        data_frame['Evidence_type'] = np.where(data_frame['Evidence_type'] == eco_code[2],
                                               eco_code[2],
                                               ecomapping.ecoclass_to_coderef(eco_code[2])[0])
    return data_frame


def calculate_file_stats(data_frame, count_by, file):
    stats = {}
    grouped_reports = []
    stats['filename'] = file
    stats['total_rows'] = data_frame.shape[0]
    for grouper in count_by:
        grouped_reports.append(data_frame.groupby(grouper)[grouper].count())
        print(data_frame.groupby(grouper)[grouper].count())
    stats['grouped_reports'] = grouped_reports
    return stats


def is_assoc_in_list(source, target_list):
    best_result = 0
    result = ""
    #note that this sometimes does not work though the data in the objects looks the same
    #if source.__eq__(target):
    #if source in target_list:
    #    result = best_result = 4
    #else:
    for target in target_list:
        match_score = compare_gpad_objects2(source, target)
        if match_score.__eq__(3):
            best_result = match_score
            break
        if match_score.__gt__(best_result):
            best_result = match_score
    if best_result.__eq__(0):
        result = "no match"
    elif best_result.__eq__(1):
        result = "ont match"
    elif best_result.__eq__(2):
        result = "ont qualifier match"
    elif best_result.__eq__(3):
        result = "ont qualifier eco match"
    elif best_result.__eq__(4):
        result = "ont qualifier eco with match"
    elif best_result.__eq__(5):
        result = "ont qualifier eco with ref match"
    return result


def compare_gpad_objects2(source, target):
    match_score = 0
    if source.negated != target.negated:
        match_score = -1
        return match_score
    if source.subject.id == target.subject.id and source.object.id == target.object.id:
            match_score = 1
            if sorted(str(q).upper() for q in source.qualifiers) == sorted(str(q).upper() for q in target.qualifiers):
                match_score = 2
                if source.evidence.type == target.evidence.type:
                    match_score = 3
                    if sorted(str(w).upper() for w in source.evidence.with_support_from) == \
                            sorted(str(w).upper() for w in target.evidence.with_support_from):
                        match_score = 4
                        if sorted(str(r).upper() for r in source.evidence.has_supporting_reference) == \
                                sorted(str(r).upper() for r in target.evidence.has_supporting_reference):
                            match_score = 5
    return match_score


if __name__ == '__main__':
    compare_gpad_objects()
