from ontobio.io import assocparser

import logging
import json

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
            if line.startswith("!"):
                if outfile is not None:
                    outfile.write(line)
                continue
            line = line.strip("\n")
            if line == "":
                logging.warning("EMPTY LINE")
                continue

            parsed_line, new_ents  = self.parse_line(line)
            if self._skipping_line(new_ents): # Skip if there were no ents
                logging.warning("SKIPPING: {}".format(line))
                skipped.append(line)
            else:
                ents += new_ents
                if outfile is not None:
                    outfile.write(parsed_line + "\n")

        self.report.skipped += len(skipped)
        self.report.n_lines += n_lines
        #self.report.n_associations += len(ents)
        logging.info("Parsed {} ents from {} lines. Skipped: {}".
                     format(len(ents),
                            n_lines,
                            len(skipped)))
        file.close()
        return ents

def load_gpi(self, gpi_path):
    """
    Loads a GPI as a file from the `config.gpi_authority_path`
    """
    if self.config.gpi_authority_path is not None:
        gpis = dict()
        parser = entityparser.GpiParser()
        with open(self.config.gpi_authority_path) as gpi_f:
            entities = parser.parse(file=gpi_f)
            for entity in entities:
                gpis[entity["id"]] = {
                    "symbol": entity["label"],
                    "name": entity["full_name"],
                    "synonyms": entitywriter.stringify(entity["synonyms"]),
                    "type": entity["type"]
                }
        return gpis

    # If there is no config file path, return None
    return None

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
        vals = line.split("\t")

        if len(vals) < 7:
            self.report.error(line, assocparser.Report.WRONG_NUMBER_OF_COLUMNS, "")
            return line, []

        if len(vals) < 10 and len(vals) >= 7:
            missing_columns = 10 - len(vals)
            vals += ["" for i in range(missing_columns)]

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
        ] = vals

        split_line = assocparser.SplitLine(line=line, values=vals, taxon=taxon)

        ## --
        ## db + db_object_id. CARD=1
        ## --
        id = self._pair_to_id(db, db_object_id)
        if not self._validate_id(id, split_line, context=assocparser.Report):
            return line, []

        ## --
        ## db_object_synonym CARD=0..*
        ## --
        synonyms = db_object_synonym.split("|")
        if db_object_synonym == "":
            synonyms = []

        # TODO: DRY
        parents = parent_object_id.split("|")
        if parent_object_id == "":
            parents = []
        else:
            parents = [self._normalize_id(x) for x in parents]
            for p in parents:
                self._validate_id(p, split_line, context=assocparser.Report)

        xref_ids = xrefs.split("|")
        if xrefs == "":
            xref_ids = []

        obj = {
            'id': id,
            'label': db_object_symbol,
            'full_name': db_object_name,
            'synonyms': synonyms,
            'type': db_object_type,
            'parents': parents,
            'xrefs': xref_ids,
            'taxon': {
                'id': self._taxon_id(taxon, split_line)
            }
        }
        return line, [obj]

class BgiParser(EntityParser):
    """
    BGI (basic gene info)
    """

    def __init__(self,config=None):
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
