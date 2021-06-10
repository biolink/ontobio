from ontobio.io import assocparser
from ontobio.io import parser_version_regex

from ontobio.model import association

from typing import Dict, List

import logging
import json

logger = logging.getLogger(__name__)


# TODO - use abstract parent for both entity and assoc
class EntityParser(assocparser.AssocParser):

    def parse(self, file, outfile=None):
        """Parse a line-oriented entity file into a list of entity dict objects

        Note the returned list is of dict objects. TODO: These will
        later be specified using marshmallow and it should be possible
        to generate objects

        Arguments
        ---------
        file : file or string
            The file is parsed into entity objects. Can be a http URL, filename or `file-like-object`, for input assoc file
        outfile : file
            Optional output file in which processed lines are written. This a file or `file-like-object`

        Return
        ------
        list
            Entities generated from the file
        """
        file = self._ensure_file(file)
        ents = []
        skipped = []
        n_lines = 0
        for line in file:
            n_lines += 1
            # if line.startswith("!"):
            #     if outfile is not None:
            #         outfile.write(line)
            #     continue
            line = line.strip("\n")
            if line == "":
                logger.warning("EMPTY LINE")
                continue

            parsed_line, new_ents = self.parse_line(line)
            if self._skipping_line(new_ents):  # Skip if there were no ents
                logger.warning("SKIPPING: {}".format(line))
                skipped.append(line)
            else:
                for entity in new_ents:
                    if not entity.get("header", False):
                        # If this line is not a header (False if no "header" or if it's directly False) then add entity
                        ents += new_ents

                    # Always write out, so we'll copy the headers through
                    if outfile is not None:
                        outfile.write(parsed_line + "\n")

        self.report.skipped += len(skipped)
        self.report.n_lines += n_lines
        #self.report.n_associations += len(ents)
        logger.info("Parsed {} ents from {} lines. Skipped: {}".
                     format(len(ents),
                            n_lines,
                            len(skipped)))
        file.close()
        return ents

    def list_field(self, field: str) -> List:
        """
        Transforms a string field into a pipe separated list.
        Empty list if the input is the empty string.
        """
        return [] if field == "" else field.split("|")

# def load_gpi(self, gpi_path):
#     """
#     Loads a GPI as a file from the `config.gpi_authority_path`
#     """
#     if self.config.gpi_authority_path is not None:
#         gpis = dict()
#         parser = GpiParser()
#         with open(self.config.gpi_authority_path) as gpi_f:
#             entities = parser.parse(file=gpi_f)
#             for entity in entities:
#                 gpis[entity["id"]] = {
#                     "symbol": entity["label"],
#                     "name": entity["full_name"],
#                     "synonyms": entitywriter.stringify(entity["synonyms"]),
#                     "type": entity["type"]
#                 }
#         return gpis

    # If there is no config file path, return None
    # return None

class GpiParser(EntityParser):

    def __init__(self, config=None):
        """
        Arguments:
        ---------

        config : a assocparser.AssocParserConfig object
        """
        if config is None:
            config = assocparser.AssocParserConfig()
        self.config = config
        self.report = assocparser.Report()
        self.default_version = "1.2"
        self.version = None

    def gpi_version(self) -> str:
        if self.version:
            return self.version
        else:
            return self.default_version

    def parse_line(self, line):
        """Parses a single line of a GPI.

        Return a tuple `(processed_line, entities)`. Typically
        there will be a single entity, but in some cases there
        may be none (invalid line) or multiple (disjunctive clause in
        annotation extensions)

        Note: most applications will only need to call this directly if they require fine-grained control of parsing. For most purposes,
        :method:`parse_file` can be used over the whole file

        Arguments
        ---------
        line : str
            A single tab-seperated line from a GPAD file

        """

        if self.is_header(line):
            if self.version is None:
                parsed = parser_version_regex.findall(line)
                if len(parsed) == 1:
                    filetype, version, _ = parsed[0]
                    if version == "2.0":
                        logger.info("Detected GPI version 2.0")
                        self.version = version
                    else:
                        logger.info("Detected version {}, so using 1.2".format(version))
                        self.version = self.default_version

            return (line, [{ "header": True, "line": line.strip() }])

        if self.version is None:
            logger.warning("No version number found for this file so we will assum GPI version: {}".format(self.default_version))
            self.version = self.default_version

        vals = line.split("\t")

        if len(vals) < 7:
            self.report.error(line, assocparser.Report.WRONG_NUMBER_OF_COLUMNS, "")
            return line, []

        # If we are 1.2, then we can upconvert into a 2.0 "line", and validate from there
        if self.gpi_version() == "1.2":

            if len(vals) < 10 and len(vals) >= 7:
                missing_columns = 10 - len(vals)
                vals += ["" for i in range(missing_columns)]
            # Convert a 1.2 set of values to a 2.0 set of values
            vals = self.line_as_2_0(vals)
        else:
            # We are gpi 2.0
            if len(vals) < 11 and len(vals) >= 7:
                missing_columns = 11 - len(vals)
                vals += ["" for i in range(missing_columns)]

        vals = [el.strip() for el in vals]

        # End Housekeeping
        #=================================================================

        [
            object_id,
            db_object_symbol,
            db_object_name,
            synonyms,
            entity_types,
            taxon,
            encoded_by,
            parents,
            contained_complex_members,
            xrefs,
            properties
        ] = vals

        split_line = assocparser.SplitLine(line=line, values=vals, taxon=taxon)

        ## --
        ## db + db_object_id. CARD=1
        ## --
        if not self._validate_id(object_id, split_line):
            return line, []

        fullnames = self.list_field(db_object_name)

        ## --
        ## db_object_synonym CARD=0..*
        ## --
        synonyms = self.list_field(synonyms)

        types = self.list_field(entity_types)

        encoded_by = self.list_field(encoded_by)
        for encoded in encoded_by:
            self._validate_id(encoded, split_line)

        parents = [self._normalize_id(x) for x in self.list_field(parents)]
        for p in parents:
            self._validate_id(p, split_line)

        contained_complex_members = self.list_field(contained_complex_members)
        for members in contained_complex_members:
            self._validate_id(members, split_line)

        xref_ids = self.list_field(xrefs)

        obj = {
            'id': object_id,
            'label': db_object_symbol,
            'full_name': fullnames,
            'synonyms': synonyms,
            'type': types,
            'parents': parents,
            'encoded_by': encoded_by,
            'contained_complex_members': contained_complex_members,
            'xrefs': xref_ids,
            'taxon': {
                'id': self._taxon_id(taxon, split_line)
            },
            'properties': properties
        }
        return line, [obj]

    def line_as_2_0(self, columns) -> List[str]:
        """
        Convert a 1.2 line into a 2.0 line. Joins the db and object_id to form the
        final ID, uses empty string for unknown values in 2.0 spec (contained_complex_members
        and encoded_by) and otherwise forwards values onwards to the correct position in the
        2.0 line.
        """
        [
            db,
            db_object_id,
            db_object_symbol,
            db_object_name,
            db_object_synonym,
            db_object_type,
            taxon,
            parent_object_id,
            xrefs,
            properties
        ] = columns

        id = self._pair_to_id(db, db_object_id)

        as_2_0 = [
            id,
            db_object_symbol,
            db_object_name,
            db_object_synonym,
            db_object_type,
            taxon,
            "",
            parent_object_id,
            "",
            xrefs,
            properties
        ]
        return as_2_0

    def line_as_entity_subject(self, line: str):
        """
        This uses `parse_line` to produce the old-style dictionary for an Entity and
        then converts it to an `association.Subject` instance. This is essentially a
        shim for the newer `ontobio.model.collections` and `ontobio.model.association`
        modules to produce a `BioEntities` object from a GPI Parser.
        """
        # Parse the line first thing. This lets us parse header info and set the GPI
        # version state before we move on to the regular conversions.
        # If it's a header (starts with `!`) we'll just skip by returning None.
        _, entity_dicts = self.parse_line(line)

        if line.startswith("!"):
            return None

        subjects = []
        for entity in entity_dicts:
            entity_types = []
            if self.gpi_version() == "2.0":
                entity_types = [association.Curie.from_str(t) for t in entity["type"]]
                if any(c.is_error() for c in entity_types):
                    logger.error("Skipping `{}` due to malformed CURIE in entity type: `{}`".format(line, entity["type"]))
                    return None
            else:
                entity_types = entity["type"]

            parents = [association.Curie.from_str(p) for p in entity["parents"]]
            if any(p.is_error() for p in parents):
                logger.error("Skipping `{}` due to malformed CURIE in parents: `{}`".format(line, entity["parents"]))
                return None

            db_xrefs = [association.Curie.from_str(x) for x in entity["xrefs"]]
            if any(x.is_error() for x in db_xrefs):
                logger.error("Skipping `{}` due to malformed CURIE in db-xrefs: `{}`".format(line, entity["xrefs"]))
                return None

            complexes = [association.Curie.from_str(c) for c in entity["contained_complex_members"]]
            if any(c.is_error() for c in complexes):
                logger.error("Skipping `{}` due to malformed CURIE in contained complexes: `{}`".format(line, entity["contained_complex_members"]))
                return None

            s = association.Subject(
                id=association.Curie.from_str(entity["id"]), label=entity["label"], fullname=entity["full_name"],
                synonyms=entity["synonyms"], type=entity_types, taxon=association.Curie.from_str(entity["taxon"]["id"]),
                parents=parents, contained_complex_members=complexes, db_xrefs=db_xrefs, properties=entity["properties"])

            subjects.append(s)

        return subjects

class BgiParser(EntityParser):
    """
    BGI (basic gene info)
    """

    def __init__(self, config=None):
        """
        Arguments:
        ---------

        config : a assocparser.AssocParserConfig object
        """
        if config is None:
            config = assocparser.AssocParserConfig()
        self.config = config
        self.report = assocparser.Report()

    def parse(self, file, outfile=None):
        """Parse a BGI (basic gene info) JSON file
        """
        file = self._ensure_file(file)
        obj = json.load(file)
        items = obj['data']
        return [self.transform_item(item) for item in items]

    def transform_item(self, item):
        """
        Transforms JSON object
        """
        obj = {
            'id': item['primaryId'],
            'label': item['symbol'],
            'full_name': item['name'],
            'type': item['soTermId'],
            'taxon': {'id': item['taxonId']},
        }
        if 'synonyms' in item:
            obj['synonyms'] = item['synonyms']
        if 'crossReferenceIds' in item:
            obj['xrefs'] = [self._normalize_id(x) for x in item['crossReferenceIds']]

        # TODO: synonyms
        # TODO: genomeLocations
        # TODO: geneLiteratureUrl
        return obj
