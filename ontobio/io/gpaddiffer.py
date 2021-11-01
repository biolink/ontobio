from ontobio.io.gpadparser import GpadParser
from ontobio.io.gafparser import GafParser
from ontobio import ecomap
from pprint import pprint
import click
import pandas as pd
import datetime
from ontobio.io import qc
from ontobio.io.assocparser import Report


@click.command()
@click.option("--file1", "-file1", type=click.Path(), required=True)
@click.option("--file2", "-file2", type=click.Path(), required=True)
@click.option("--output", "-o", type=click.File("a"), required=True)
@click.option("--count_by", "-cb", multiple=True, required=False)
@click.option("--file_type", "-file_type", required=True)
@click.option("--exclude_details", "-ed", type=click.BOOL, default=True, required=False)
def compare_files(file1, file2, output, count_by, exclude_details, file_type):
    print("Starting comparison ")
    print("")
    df_file1, df_file2, assocs1, assocs2 = get_parser(file1, file2, file_type)
    processed_lines = 0
    exact_matches = 0
    close_matches = 0
    stats1 = calculate_file_stats(df_file1, count_by, file1)
    stats2 = calculate_file_stats(df_file2, count_by, file2)
    print(stats1)
    print(stats2)
    report = Report()

    for association in assocs1:
        max_match_score = 0
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
                if match_score > max_match_score:
                    max_match_score = match_score
            if max_match_score > 4:
                exact_matches = exact_matches + 1
            elif 1 > max_match_score < 5:
                close_matches = close_matches + 1
                report.add_association(association)
                report.n_lines = report.n_lines + 1
                report.warning(association.source_line, qc.ResultType.WARNING,
                               "line from file1 only has CLOSE match in file2", "")
            else:
                report.add_association(association)
                report.n_lines = report.n_lines + 1
                report.error(association.source_line, qc.ResultType.ERROR,
                             "line from file1 has NO match in file2", "")

    print("")

    mdr = markdown_report(report, exact_matches, close_matches, processed_lines)
    print(mdr)


def markdown_report(report, exact_matches, close_matches, processed_lines):

    json = report.to_report_json()

    s = "\n\n## SUMMARY\n\n"
    s += "This report generated on {}\n\n".format(datetime.date.today())
    s += "  * Total Unmatched Associations: {}\n".format(json["associations"])
    s += "  * Total Lines Compared: " + str(processed_lines) + "\n"
    s += "  * Total Exact matches: " + str(exact_matches) + "\n"
    s += "\n\n## Contents\n\n"

    for (rule, messages) in sorted(json["messages"].items(), key=lambda t: t[0]):
        s += "### {rule}\n\n".format(rule=rule)
        s += "* total: {amount}\n".format(amount=len(messages))
        if len(messages) > 0:
            s += "#### Messages\n"
        for message in messages:
            obj = " ({})".format(message["obj"]) if message["obj"] else ""
            s += "* {level} - {type}: {message}{obj} -- `{line}`\n".format(level=message["level"],
                                                                           type=message["type"],
                                                                           message=message["message"],
                                                                           line=message["line"],
                                                                           obj=obj)

            return s


def get_parser(file1, file2, file_type):
    if file_type == 'gpad':
        gpad_parser_1 = GpadParser()
        gpad_parser_2 = GpadParser()
        assocs1 = gpad_parser_1.parse(file1, skipheader=True)
        assocs2 = gpad_parser_2.parse(file2, skipheader=True)
        df_file1 = read_gpad_csv(file1)
        df_file2 = read_gpad_csv(file2)
    else:
        gaf_parser_1 = GafParser()
        gaf_parser_2 = GafParser()
        assocs1 = gaf_parser_1.parse(file1, skipheader=True)
        assocs2 = gaf_parser_2.parse(file2, skipheader=True)

        df_file1 = read_gaf_csv(file1)
        df_file2 = read_gaf_csv(file2)
    return df_file1, df_file2, assocs1, assocs2


def read_gaf_csv(filename):
    ecomapping = ecomap.EcoMap()
    data_frame = pd.read_csv(filename,
                             comment='!',
                             sep='\t',
                             header=None,
                             na_filter=False,
                             names=["DB",
                                    "DB_Object_ID",
                                    "DB_Object_Symbol",
                                    "Qualifier",
                                    "GO_ID",
                                    "DB_Reference",
                                    "Evidence_code",
                                    "With_or_From",
                                    "Aspect",
                                    "DB_Object_Name",
                                    "DB_Object_Synonym",
                                    "DB_Object_Type,"
                                    "Taxon",
                                    "Date",
                                    "Assigned_By",
                                    "Annotation_Extension",
                                    "Gene_Product_Form_ID"]).fillna("")
    for eco_code in ecomapping.mappings():
        for ev in data_frame['Evidence_code']:
            if eco_code[2] == ev:
                data_frame['Evidence_code'] = data_frame['Evidence_code'].replace([eco_code[2]],
                                                                                  ecomapping.ecoclass_to_coderef(
                                                                                      eco_code[2])[0])
    return data_frame


def read_gpad_csv(filename):
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
    if len(count_by) > 0:
        for grouper in count_by:
            stats['grouper'] = grouper
            grouped_reports.append(data_frame.groupby(grouper)[grouper].count())
        stats['grouped_reports'] = grouped_reports
    return stats


if __name__ == '__main__':
    compare_files()
