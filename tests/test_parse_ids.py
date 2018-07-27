import io
import json

from ontobio.io import assocparser
from ontobio.io import gafparser

from ontobio.io import assocwriter

def test_no_colon_in_id():
    parser = gafparser.GafParser()
    valid = parser._validate_id("FOOBAR", "")

    assert not valid
    assert len(parser.report.messages) == 1
    assert parser.report.messages[0]["level"] == assocparser.Report.ERROR

def test_pipe_in_id():
    parser = gafparser.GafParser()
    valid = parser._validate_id("F|OO:123", "")

    assert valid
    assert len(parser.report.messages) == 1
    assert parser.report.messages[0]["level"] == assocparser.Report.WARNING

def test_bad_character_in_id():
    parser = gafparser.GafParser()
    valid = parser._validate_id("FOO:1&23", "")

    assert not valid
    assert len(parser.report.messages) == 1
    assert parser.report.messages[0]["level"] == assocparser.Report.ERROR

def test_empty_post_colon():
    parser = gafparser.GafParser()
    valid = parser._validate_id("FOO:", "")

    assert not valid
    assert len(parser.report.messages) == 1
    assert parser.report.messages[0]["level"] == assocparser.Report.ERROR

def test_empty_pre_colon():
    parser = gafparser.GafParser()
    valid = parser._validate_id(":123", "")

    assert not valid
    assert len(parser.report.messages) == 1
    assert parser.report.messages[0]["level"] == assocparser.Report.ERROR

def test_validate_pipe_separated():
    parser = gafparser.GafParser()
    ids = parser.validate_pipe_separated_ids("PMID:12345", "")
    assert set(ids) == set(["PMID:12345"])

    ids = parser.validate_pipe_separated_ids("PMID:12345|PMID:11111", "")
    assert set(ids) == set(["PMID:12345", "PMID:11111"])

def test_validate_pipe_separated_with_bad_ids():
    parser = gafparser.GafParser()
    ids = parser.validate_pipe_separated_ids("PMID:123[2]|PMID:11111", "")

    assert ids == None

    ids = parser.validate_pipe_separated_ids("PMID:123[2]", "")
    assert ids == None

def test_validate_pipe_separated_empty_allowed():
    parser = gafparser.GafParser()
    ids = parser.validate_pipe_separated_ids("", "", empty_allowed=True)

    assert ids == []
