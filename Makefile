# DOCS
# See https://github.com/pypa/virtualenv/issues/149
pydoc-%:
	python -m pydoc ontobio.ontol

#PACKAGES = prefixcommons scigraph biogolr
PACKAGES = ontobio prefixcommons
subpackage_tests: $(patsubst %,test-%,$(PACKAGES))

test:
	pytest tests/*.py tests/unit/

debug_test:
	pytest -s -vvvv tests/*.py

t-%:
	pytest tests/test_$*.py

tv-%:
	pytest -s tests/test_$*.py

foo:
	which pytest

# only run local tests
travis_test:
	pytest tests/test_*local*.py tests/test_*parse*.py tests/test*writer*.py tests/test_qc.py \
	       tests/test_rdfgen.py tests/test_phenosim_engine.py tests/test_ontol.py \
		   tests/test_validation_rules.py tests/unit/test_annotation_scorer.py tests/unit/test_golr_search_query.py tests/unit/test_owlsim2_api.py

cleandist:
	rm dist/* || true

TAG = v$(shell python setup.py --version)
versioning:
	git checkout master
	git add ontobio/__init__.py
	git commit --message="Upgrade to $(TAG)"
	git push origin master
	git tag --annotate $(TAG) -f --message="Upgrade to $(TAG)"
	git push --tags

# TODO: manually increment version in ontobio/__init__.sh, run . bump.sh, then this
USER ?= $(LOGNAME)
release: cleandist versioning
	python setup.py sdist bdist_wheel bdist_egg
	twine upload --repository-url https://upload.pypi.org/legacy/ --username $(USER) dist/*

test_release: cleandist
	python setup.py sdist bdist_wheel bdist_egg
	twine upload --repository-url https://test.pypi.org/legacy/ --username $(USER) dist/*

nb:
	PYTHONPATH=.. jupyter notebook

# Hack: generate marshmallow schema from flaskrest serializers
# used to make assoc_schema.py
mm:
	./bin/flask2marshmallow.pl ../biolink-api/biolink/datamodel/serializers.py
