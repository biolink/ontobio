from ontobio.rdfgen.gocamgen import collapsed_assoc


class GocamgenException(Exception):
    def __init__(self, message: str):
        self.message = message

    def __str__(self):
        return self.message


class ModelRdfWriteException(GocamgenException):
    pass


class ShexException(GocamgenException):
    pass


class CollapsedAssocGocamgenException(GocamgenException):
    def __init__(self, message: str, assoc: collapsed_assoc.CollapsedAssociation):
        self.message = message
        self.assoc = assoc

    def __str__(self):
        return "{}\n{}".format(self.message, "\n".join([l.source_line for l in self.assoc.lines]))


class GeneErrorSet:
    def __init__(self):
        self.errors = {}

    def add_error(self, gene, error):
        if gene not in self.errors:
            self.errors[gene] = []
        self.errors[gene].append(error)
