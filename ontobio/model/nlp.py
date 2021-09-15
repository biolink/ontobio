"""
Classes for handling data coming back from scigraph/annotations

Because the results do not include the original text the content
is added back into these objects based on the input, which is
why these are not standard dataclasses
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Token:
    """
    A token or entity extracted from a marked-up span
    """
    id: str
    category: List[str] = field(default_factory=list)
    terms: List[str] = field(default_factory=list)


class Span:
    """
    A marked-up span of text
    """

    def __init__(self, start: int, end: int, token: Token, content=None):
        self.start = start
        self.end = end
        self.text = content[self.start:self.end]
        self.token = token
        return


@dataclass
class SciGraphAnnotation:
    token: Token
    start: int
    end: int


class EntityAnnotationResults:
    """
    The results of a SciGraph annotations/entities call
    """

    def __init__(self, results: List[SciGraphAnnotation], content=None):
        self.content = content
        self.spans = []
        for result in results:
            self.spans.append(Span(result.start, result.end, result.token, content))
