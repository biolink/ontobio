"""
Classes for exporting associations.

"""
import re
import datetime
import json
import logging

from typing import List

from ontobio import ecomap
from ontobio.io import assocparser

logger = logging.getLogger(__name__)

external_taxon = re.compile("taxon:([0-9]+)")
internal_taxon = re.compile("NCBITaxon:([0-9]+)")

def _str(v):
    if v is None:
        return ""
    else:
        return str(v)

class AssocWriterConfig():
    """
    Placeholder class for configuration object for all writers
    """
    pass

class AssocWriter():
    """
    Abstract superclass of all association writer objects (Gpad, GAF)
    """
    def _split_prefix(self, ref):
        id = ref['id']
        [prefix, local_id] = id.split(':', maxsplit=1)
        return prefix, local_id

    def _write_row(self, vals):
        line = self.tsv_as_string(vals)
        if self.file:
            self.file.write(line+"\n")
        else:
            print(line)

    def tsv_as_string(self, vals) -> str:
        return "\t".join([_str(v) for v in vals])

    def _write(self, line):
        if self.file:
            self.file.write(line)
        else:
            print(line)

    def _extension_expression(self, object_extensions):
        unions = []
        for union_key, union_value in object_extensions.items():
            if union_key == "union_of":
                # union_value is list of { "intersection_of" ...}
                for union_item in union_value:
                    for intersect_key, intersect_value in union_item.items():
                        if intersect_key == "intersection_of":
                            intersections = []
                            for intersect_item in intersect_value:
                                prop = intersect_item["property"]
                                filler = intersect_item["filler"]
                                full_property = "{property}({filler})".format(property=prop, filler=filler)
                                intersections.append(full_property)
                            joined_intersections = ",".join(intersections)
                            unions.append(joined_intersections)

        return "|".join(unions)

    def normalize_taxon(self, taxon):
        global internal_taxon
        global external_taxon

        if taxon == None:
            return ""

        if external_taxon.match(taxon):
            # If we match here, then the internal view already exists and we're good
            return internal_taxon

        match = internal_taxon.match(taxon)
        if match:
            taxon_id = match.group(1)
            return "taxon:{num}".format(num=taxon_id)

        return taxon

    def as_tsv(self, assoc) -> List[str]:
        """
        Transform a single association to a string line.
        """
        pass

    def write_assoc(self, assoc):
        """
        Write a single association to a line in the output file
        """
        vals = self.as_tsv(assoc)
        if vals != []:
            # Write it if we found content
            self._write_row(vals)

    def write(self, assocs, meta=None):
        """
        Write a complete set of associations to a file

        Arguments
        ---------
        assocs: list[dict]
            A list of association dict objects
        meta: Meta
            metadata about association set (not yet implemented)

        """
        for a in assocs:
            self.write_assoc(a)

class GpadWriter(AssocWriter):
    """
    Writes Associations in GPAD format
    """
    def __init__(self, file=None):
        self.file = file
        self._write("!gpa-version: 1.1\n")
        self.ecomap = ecomap.EcoMap()

    def as_tsv(self, assoc):
        """
        Write a single association to a line in the output file
        """
        if assoc.get("header", False):
            return []

        subj = assoc['subject']

        db, db_object_id = self._split_prefix(subj)

        rel = assoc['relation']
        qualifier = rel['id']
        if assoc['negated']:
            qualifier = 'NOT|' + qualifier

        goid = assoc['object']['id']

        ev = assoc['evidence']

        evidence = self.ecomap.coderef_to_ecoclass(ev['type'])
        withfrom = "|".join(ev['with_support_from'])
        reference = "|".join(ev['has_supporting_reference'])

        date = assoc['date']
        assigned_by = assoc['provided_by']

        annotation_properties = '' # TODO
        interacting_taxon_id = assoc['interacting_taxon']
        vals = [db,
                db_object_id,
                qualifier,
                goid,
                reference,
                evidence,
                withfrom,
                interacting_taxon_id, # TODO
                date,
                assigned_by,
                self._extension_expression(assoc['object_extensions']),
                annotation_properties]

        return vals

class GafWriter(AssocWriter):
    """
    Writes Associations in GAF format.

    This converts an association dictionary object as produced in GafParser or
    GpadParser into a GAF line.

    The GAF Writer now assumes that it is writing out GAF version 2.1 style
    annotations. The version can be set when creating a new GafWriter to 2.2
    with `version=2.2`. If any version other than 2.1 or 2.2, GafWriter will
    default to 2.1.

    The only difference in 2.1 and 2.2 are how qualifiers (column 4) are handled.
    GAF 2.1 allows empty or only `NOT` qualifier values, and only allows
    `colocalizes_with` and `contributes_to` as qualifer values. However in 2.2
    qualifier must *not* be empty and cannot have only `NOT` as it's a modifier
    on existing qualifers. The set of allowed qualifiers in 2.2 is also expanded.

    So if there's a mismatch between converting from an annotation and a GAF
    version then that annotation is just skipped and not written out with an
    error message displayed. Mismatch occurances of this kind would appear if
    the incoming annotation has a qualifier in the 2.2 set, but 2.1 is being
    written out, or if the qualifier is empty and 2.2 is being written.
    """
    def __init__(self, file=None, source=None, version="2.1"):
        self.file = file
        if version not in ["2.1", "2.2"]:
            self.version = "2.1"
        else:
            self.version = version

        self._write("!gaf-version: {}\n".format(version))
        self._write("!\n")
        self._write("!Generated by GO Central\n")
        self._write("!\n")
        self._write("!Date Generated by GOC: {}\n".format(str(datetime.date.today())))
        self._write("!\n")
        # Just uses the word `source` if source is none. Otherwise uses the name of the source in the header
        self._write("!Header from {source}source association file:\n".format(source=source+" " if source else ""))
        self._write("!=================================\n")

    def _full_taxon_field(self, taxon, interacting_taxon):
        full_taxon = taxon
        if interacting_taxon not in [None, ""]:
            full_taxon = "{taxon}|{interacting_taxon}".format(taxon=taxon, interacting_taxon=interacting_taxon)

        return full_taxon

    def as_tsv(self, assoc):
        """
        Write a single association to a line in the output file
        """
        # Handle comment 'associations'
        if assoc.get("header", False):

            # Skip incoming gaf-version headers, as we created the version above already
            if assocparser.parser_version_regex.match(assoc["line"]):
                return []

            self._write(assoc["line"] + "\n")
            return []

        # print("Writing assoc {}".format(assoc))
        subj = assoc['subject']

        db, db_object_id = self._split_prefix(subj)

        qual_negated = ["NOT"] if assoc["negated"] else []
        qualifier = ""
        if self.version == "2.1":
            allowed_qualifiers = {"contributes_to", "colocalizes_with"}
            # Detect if the qualifier is wrong
            if len(assoc["qualifiers"]) == 1 and assoc["qualifiers"][0] not in allowed_qualifiers:
                logger.warning("Cannot write qualifier `{}` in GAF version 2.1 since only {} are allowed".format(assoc["qualifiers"][0], ", ".join(allowed_qualifiers)))
                assoc["qualifiers"] = []  # Blank out qualifer

        else:
            # Then we're 2.2
            if len(assoc["qualifiers"]) == 0:
                logger.error("Qualifier must not be empty for GAF version 2.2")
                return []

        # assoc["qualifiers"] is appropriately set up for whatever version this is
        quals = qual_negated + assoc["qualifiers"]
        qualifier = "|".join(quals)

        goid = assoc['object']['id']

        ev = assoc['evidence']
        evidence = ev['type']
        withfrom = "|".join(ev['with_support_from'])
        reference = "|".join(ev['has_supporting_reference'])

        date = assoc['date']
        assigned_by = assoc['provided_by']

        annotation_properties = '' # TODO
        # if we have any subject extensions, list each one that has a "property" equal to "isoform", take the first one, and grab the "filler"
        gene_product_isoform = [e for e in assoc["subject_extensions"] if e["property"] == "isoform"][0]["filler"] if len(assoc["subject_extensions"]) > 0 else ""

        aspect = assoc['aspect']
        interacting_taxon_id = assoc["interacting_taxon"]
        taxon = self._full_taxon_field(self.normalize_taxon(subj['taxon']['id']), self.normalize_taxon(interacting_taxon_id))

        extension_expression = self._extension_expression(assoc['object_extensions'])

        vals = [db,
                db_object_id,
                subj.get('label'),
                qualifier,
                goid,
                reference,
                evidence,
                withfrom,
                aspect,
                subj["fullname"],
                "|".join(subj.get('synonyms',[])),
                subj.get('type'),
                taxon,
                date,
                assigned_by,
                extension_expression,
                gene_product_isoform]

        return vals
