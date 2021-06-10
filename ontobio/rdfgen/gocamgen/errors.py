class GocamgenException(Exception):
    def __init__(self, message: str):
        self.message = message

    def __str__(self):
        return self.message


class ModelRdfWriteException(GocamgenException):
    pass


class ShexException(GocamgenException):
    pass


class GeneErrorSet:
    def __init__(self):
        self.errors = {}

    def add_error(self, gene, error):
        if gene not in self.errors:
            self.errors[gene] = []
        self.errors[gene].append(error)
