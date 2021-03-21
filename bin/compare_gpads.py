import pandas as pd
import click
import logging

logger = logging.getLogger("INFER")
logger.setLevel(logging.WARNING)


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
@click.option("--gpad1", "-gp1", type=click.File("r"), required=True)
@click.option("--gpad2", "-gp2", type=click.File("r"), required=True)
@click.option("--output", "-o", type=click.File("a"), required=True)
def compare_gpad(gpad1, gpad2, output):
    line_count = 1
    # click.echo("Processed {} lines".format(line_count))
    df1 = pd.read_csv(gpad1, comment='!', sep='\t', header=0, na_filter=False, names=["DB_Object_ID",
                                                                                      "Negation",
                                                                                      "Relation",
                                                                                      "Ontology_Class_ID",
                                                                                      "Reference",
                                                                                      "Evidence_type",
                                                                                      "With_or_From",
                                                                                      "Interacting_taxon_ID",
                                                                                      "Date",
                                                                                      "Assigned_by",
                                                                                      "Annotation_Extensions",
                                                                                      "Annotation_Properties"])
    df2 = pd.read_csv(gpad2,
                      comment='!',
                      sep='\t',
                      header=0,
                      na_filter=False,
                      names=["DB_Object_ID",
                             "Negation",
                             "Relation",
                             "Ontology_Class_ID",
                             "Reference",
                             "Evidence_type",
                             "With_or_From",
                             "Interacting_taxon_ID",
                             "Date",
                             "Assigned_by",
                             "Annotation_Extensions",
                             "Annotation_Properties"])

    df_diff = pd.concat([df1, df2]).drop_duplicates(keep=False)
    print(df_diff)


if __name__ == "__main__":
    compare_gpad()
