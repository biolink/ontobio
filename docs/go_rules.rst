.. _go_rules:

GO Rules Engine
===============

GO Rules are data quality validation checks for Gene Ontology annotation data. All GO Rules are `defined here <https://github.com/geneontology/go-site/tree/master/metadata/rules>`_ and represent what valid Annotation Data should look like.

In Ontobio, when we parse GPAD or GAF annotations using :class:`ontobio.io.gafparser.GafParser` or :class:`ontobio.io.gpadparser.GpadParser` we can validate each annotation line on each rule defined in :mod:`ontobio.io.qc`.

Any line that fails a rule will have a message made in :class:`ontobio.io.assocparser.Report`.

The GO Rules engine is defined in :mod:`ontobio.io.qc` and is where new rules should be implemented.

Rules Definition
----------------

A GO Rule implementation works by implementing a function that encodes the logic of the defined GO Rule defined in a rule markdown in the `rule definitions <https://github.com/geneontology/go-site/tree/master/metadata/rules>`_

In code, a Rule consists of an ID, title, fail_mode, and optionally rule tags.

* The ID is the Curie style rule ID, like ``GORULE:0000013`` (referring to `GORULE:0000013 <https://github.com/geneontology/go-site/blob/master/metadata/rules/gorule-0000013.md>`_)
* The title should be more or less direct from the rule definition in go-site. For example in `GORULE:0000006 <https://github.com/geneontology/go-site/blob/master/metadata/rules/gorule-0000006.md>`_ the title is "IEP and HEP usage is restricted to terms from the Biological Process ontology" and that should be used here.
* ``fail_mode`` comes from the rule's `SOP.md <https://github.com/geneontology/go-site/blob/master/metadata/rules/SOP.md>`_. Annotations that fail a GO Rule that have a ``HARD`` ``fail_mode`` will be filtered and ``SOFT`` will be kept, but with a warning message.
* Tags should be copied over from the rule definition as well. For example `GORULE:0000058 <https://github.com/geneontology/go-site/blob/master/metadata/rules/gorule-0000058.md>`_ has a tag "context-import". This is used to signal extra information about rules and how they should be run. In the GoRule definition, there is a `_is_run_from_context` which detects if a rule should be run given the context in the :class:`ontobio.io.assocparser.AssocParserConfig` ``rule_contexts``.

A rule class will provide its own definition of ``test()`` which should perform the logic of the rule, returning a TestResult. In the majority of cases, the helper method ``_result(passes: bool)`` should be used which will perform some default behavior given ``True`` for passing and ``False`` for failing the given rule.

How to Write a New Rule Implementation
--------------------------------------

1. Create a new class subclassing ``GoRule``, typically named after the rule ID number.

::

    class GoRule02(GoRule):

        def __init__(self):
            pass

2. Write an ``__init__`` calling the super ``GoRule`` init, defining the relavent values for your new rule.

::

    class GoRule02
        def __init__(self):
            super().__init__("GORULE:0000002", "No 'NOT' annotations to 'protein binding ; GO:0005515'", FailMode.SOFT)
            # Note title in second argument copied from gorule-0000002 definition

3. Override ``test()`` implementing the logic of your rule. The ``annotation`` is the incoming annotation as a GoAssociation, the config holds important metadata about the current running instance and has resources like the ontology. Note that all identifiers that can be are proper CURIEs, defined by the :class:`ontobio.model.association.Curie`, so must be wrapped in ``str`` to compare against a string.

::

    def test(self, annotation: association.GoAssociation, config: assocparser.AssocParserConfig, group=None) -> TestResult:
        """
        Fake rule that passes only annotations to the GO Term GO:0003674 molecular function
        """
        return self._result(str(annotation.object.id) == "GO:0003674")

4. Add new Rule Instance to the ``GoRules`` enum. This is how you register a rule with the runner system, so it gets run automatically by ontobio.

5. Write Tests for your rule in tests/test_qc.py

Implmentation Notes
^^^^^^^^^^^^^^^^^^^

Rules can generally use the ``self._result(bool)`` helper function instead of producing a TestResult manually. True for Passing, False for Failing. This method will take care of the fail mode, messages, etc, automatically.

For slightly more control, use the ``result(bool, FailMode)`` function to create the correct ``ResultType``.

Rules that perform repairs on incoming ``GoAssociations`` can be done by instead subclassing ``RepairRule``.

In general, when testing an annotation, the GoAssociation instance is passed along to each rule implementation. In a RepairRule the result will contain the updated annotation. So the runner will grab this updated annotation, passing it along to the next rule down the line. In this way annotations under test may accumulate repairs across the length of the rules.

As a matter of policy, if a rule requires a resource, the ``test`` implmentation should test that the ``AssocParserConfig`` has that resource defined, and automatically pass the rule if it is not preseent. In the future, we could instead have a "skip" state that encapsulates this.

Also, each rule implementation should complete as fast as possible, and not delay. Any long computation should be cached - so at least only the first run of a rule will be slow. See rules where we compute sublcass closures, like :class:`ontobio.io.qc.GoRule07`.

