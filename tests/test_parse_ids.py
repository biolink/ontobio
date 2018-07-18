from ontobio.io import assocparser
from ontobio.io import gafparser

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
