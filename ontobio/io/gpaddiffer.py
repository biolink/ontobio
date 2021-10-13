from ontobio.io.gpadparser import GpadParser
from ontobio.model.association import GoAssociation
from ontobio.io import assocparser
from ontobio import ecomap
import click
import logging
import pandas as pd
from pandasql import sqldf
import numpy as np

input_lines = 0
output_lines = 0
exact_matches = 0
close_matches = 0
no_matches = 0

logger = logging.getLogger("INFER")
logger.setLevel(logging.WARNING)

ecomapping = ecomap.EcoMap()

@click.command()
@click.option("--gpad1", "-gp1", type=click.Path(), required=True)
@click.option("--gpad2", "-gp2", type=click.Path(), required=True)
@click.option("--output", "-o", type=click.File("a"), required=True)
@click.option('--count_by', '-cb', multiple=True, required=False)
def compare_gpad_objects(gpad1, gpad2, output, count_by):
    print("Starting comparison ")
    print("")
    gpad_parser_1 = GpadParser()
    gpad_parser_2 = GpadParser()
    assocs1 = gpad_parser_1.parse(gpad1, skipheader=True)
    assocs2 = gpad_parser_2.parse(gpad2, skipheader=True)

    df_gpad1 = read_csv(gpad1)
    df_gpad2 = read_csv(gpad2)

    stats = calculate_file_stats(df_gpad1, count_by, gpad1)
    print("")
    stats = calculate_file_stats(df_gpad2, count_by, gpad2)

    missing_rows = []
    for association in assocs1:
        if association in assocs2:
            continue
        else:
            missing_rows.append(association.source_line)

    print("present in %s, missing from %s" % (gpad1, gpad2))
    for item in missing_rows:
        print(item)


def read_csv(filename):
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
                                    "Annotation_Extensions" # ,
                                    # "Annotation_Properties"
                                    ]).fillna("")
    for eco_code in ecomapping.mappings():
        data_frame['Evidence_type'] = np.where(data_frame['Evidence_type'] == eco_code[2],
                                               eco_code[2],
                                               ecomapping.ecoclass_to_coderef(eco_code[2])[0])
    return data_frame


def calculate_file_stats(data_frame, count_by, file):
    stats = []
    print("Filename: %s" % file)
    print("Total rows: %s" % data_frame.shape[0])
    for grouper in count_by:
        print(type(data_frame.groupby(grouper)[grouper].count()))

    return stats


if __name__ == '__main__':
    compare_gpad_objects()

# def is_assoc_in_list(source, target_list):
#     best_result = 0
#     result = ""
#     #note that this sometimes does not work though the data in the objects looks the same
#     #if source.__eq__(target):
#     #if source in target_list:
#     #    result = best_result = 4
#     #else:
#     for target in target_list:
#         match_score = compare_gpad_objects(source, target)
#         if match_score.__eq__(3):
#             best_result = match_score
#             break
#         if match_score.__gt__(best_result):
#             best_result = match_score
#     if best_result.__eq__(0):
#         result = "no match"
#     elif best_result.__eq__(1):
#         result = "ont match"
#     elif best_result.__eq__(2):
#         result = "ont qualifier match"
#     elif best_result.__eq__(3):
#         result = "ont qualifier eco match"
#     elif best_result.__eq__(4):
#         result = "ont qualifier eco with match"
#     elif best_result.__eq__(5):
#         result = "ont qualifier eco with ref match"
#     return result
#
#
# def compare_gpad_objects(source, target):
#     match_score = 0
#     if source["negated"] != target["negated"]:
#         match_score = -1
#         return match_score
#     if source["subject"]["id"] == target["subject"]["id"] \
#             and source["object"]["id"] == target["object"]["id"]:
#             match_score = 1
#             if sorted(q.upper() for q in source['qualifiers']) == sorted(q.upper() for q in target['qualifiers']):
#                 match_score = 2
#                 if source['evidence']['type'] == target['evidence']['type']:
#                     match_score = 3
#                     if sorted(w.upper() for w in source['evidence']['with_support_from']) == \
#                             sorted(w.upper() for w in target['evidence']['with_support_from']):
#                         match_score = 4
#                         if sorted(r.upper() for r in source['evidence']['has_supporting_reference']) == \
#                                 sorted(r.upper() for r in target['evidence']['has_supporting_reference']):
#                             match_score = 5
#     return match_score
#



# if __name__ == '__main__':
#     f = open("compare.txt", "w")
#     print("Starting comparison ")
#     parser = argparse.ArgumentParser()
#     parser.add_argument('-g1', '--gpad_file1', help="Filepath of GPAD file 1", required=True)
#     parser.add_argument('-g2', '--gpad_file2', help="Filepath of GPAD file 2", required=True)
#     args = parser.parse_args()
#
#     gpad_parser = GpadParser()
#     assocs1 = gpad_parser.parse(args.gpad_file1, skipheader=True)
#     assocs2 = gpad_parser.parse(args.gpad_file2, skipheader=True)
#     for a in assocs1:
#         #gene_id_a = a["subject"]["id"]
#         #ont_id_a = a["object"]["id"]
#         #print("a" + gene_id_a + " "+ont_id_a)
#         match = is_assoc_in_list(a, assocs2)
#         if match.__eq__("exact match"):
#             exact_matches = exact_matches + 1
#         elif match.__eq__("close match"):
#             close_matches = close_matches + 1
#         elif match.__eq__("no match"):
#             no_matches = no_matches + 1
#         f.write(match + "\t" + a["source_line"])
#         input_lines = input_lines + 1
#     f.close()
#     print('\n gpads', input_lines, ' exact ', exact_matches, ' close ', close_matches, ' none ', no_matches)

