"""
Classes for exporting associations.

"""
import re
import datetime
import json
import logging

from typing import List, Union

from ontobio import ecomap
from ontobio.io import parser_version_regex
from ontobio.model import association

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

    def as_tsv(self, assoc: Union[association.GoAssociation, dict]) -> List[str]:
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


GPAD_2_0 = "2.0"
GPAD_1_2 = "1.2"

class GpadWriter(AssocWriter):
    """
    Writes Associations in GPAD format
    """
    def __init__(self, file=None, version=GPAD_1_2):
        self.file = file
        if version in [GPAD_1_2, GPAD_2_0]:
            self.version = version
        else:
            self.version = GPAD_1_2

        self._write("!gpa-version: {}\n".format(self.version))
        self.ecomap = ecomap.EcoMap()

    def as_tsv(self, assoc: Union[association.GoAssociation, dict]):
        """
        Write a single association to a line in the output file
        """
        if isinstance(assoc, dict):
            return []

        if self.version == GPAD_2_0:
            return assoc.to_gpad_2_0_tsv()
        else:
            # Default output to gpad 1.2
            return assoc.to_gpad_1_2_tsv()



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
        if version in ["2.1", "2.2"]:
            self.version = version
        else:
            self.version = "2.1"

        self._write("!gaf-version: {}\n".format(self.version))
        self._write("!\n")
        self._write("!generated-by: GOC\n")
        self._write("!\n")
        self._write("!date-generated: {}\n".format(str(datetime.datetime.now().strftime("%Y-%m-%dT%H:%M"))))
        self._write("!\n")
        # Just uses the word `source` if source is none. Otherwise uses the name of the source in the header
        self._write("!Header from {source}source association file:\n".format(source=source+" " if source else ""))
        self._write("!=================================\n")

    def _full_taxon_field(self, taxon, interacting_taxon):
        full_taxon = taxon
        if interacting_taxon not in [None, ""]:
            full_taxon = "{taxon}|{interacting_taxon}".format(taxon=taxon, interacting_taxon=interacting_taxon)

        return full_taxon

    def as_tsv(self, assoc: Union[association.GoAssociation, dict]):
        """
        Write a single association to a line in the output file
        """
        # Handle comment 'associations'
        if isinstance(assoc, dict):

            # Skip incoming gaf-version headers, as we created the version above already
            if parser_version_regex.match(assoc["line"]):
                return []

            self._write(assoc["line"] + "\n")
            return []

        if self.version == "2.2":
            return assoc.to_gaf_2_2_tsv()
        else:
            # Default to GAF 2.1
            return assoc.to_gaf_2_1_tsv()
