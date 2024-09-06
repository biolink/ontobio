# DOCS
# See https://github.com/pypa/virtualenv/issues/149
pydoc-%:
	python -m pydoc ontobio.ontol

#PACKAGES = prefixcommons scigraph biogolr
PACKAGES = ontobio prefixcommons
subpackage_tests: $(patsubst %,test-%,$(PACKAGES))

test:
	pytest -m "not slow" tests/*.py tests/unit/

debug_test:
	pytest -m "not slow" -s -vvvv tests/*.py

t-%:
	pytest -m "not slow" tests/test_$*.py

tv-%:
	pytest -m "not slow" -s tests/test_$*.py

foo:
	which pytest

# only run local tests
travis_test:
	@if [ -d ".venv" ] && [ -f "pyproject.toml" ]; then \
		echo "Running tests in Poetry environment..."; \
		poetry run pytest -m "not slow" tests/test_*local*.py tests/test_*parse*.py tests/test*writer*.py tests/test_qc.py \
		tests/test_rdfgen.py tests/test_phenosim_engine.py tests/test_ontol.py \
		tests/test_validation_rules.py tests/unit/test_annotation_scorer.py \
		tests/test_goassociation_model.py tests/test_relations.py \
		tests/unit/test_golr_search_query.py tests/unit/test_owlsim2_api.py \
		tests/test_collections.py \
		tests/test_gocamgen.py \
		tests/test_gpi_isoform_replacement.py \
		tests/test_validate_cli.py; \
	else \
		pytest -m "not slow" tests/test_*local*.py tests/test_*parse*.py tests/test*writer*.py tests/test_qc.py \
		tests/test_rdfgen.py tests/test_phenosim_engine.py tests/test_ontol.py \
		tests/test_validation_rules.py tests/unit/test_annotation_scorer.py \
		tests/test_goassociation_model.py tests/test_relations.py \
		tests/unit/test_golr_search_query.py tests/unit/test_owlsim2_api.py \
		tests/test_collections.py \
		tests/test_gocamgen.py \
		tests/test_gpi_isoform_replacement.py \
		tests/test_validate_cli.py; \
	fi


travis_test_full:
	@if [ -d ".venv" ] && [ -f "pyproject.toml" ]; then \
		echo "Running tests in Poetry environment..."; \
		poetry run pytest tests/test_*local*.py tests/test_*parse*.py tests/test*writer*.py tests/test_qc.py \
		tests/test_rdfgen.py tests/test_phenosim_engine.py tests/test_ontol.py \
		tests/test_validation_rules.py tests/unit/test_annotation_scorer.py \
		tests/test_goassociation_model.py tests/test_relations.py \
		tests/unit/test_golr_search_query.py tests/unit/test_owlsim2_api.py \
		tests/test_collections.py \
		tests/test_gocamgen.py \
		tests/test_gpi_isoform_replacement.py \
		tests/test_validate_cli.py; \
	else \
		pytest tests/test_*local*.py tests/test_*parse*.py tests/test*writer*.py tests/test_qc.py \
		tests/test_rdfgen.py tests/test_phenosim_engine.py tests/test_ontol.py \
		tests/test_validation_rules.py tests/unit/test_annotation_scorer.py \
		tests/test_goassociation_model.py tests/test_relations.py \
		tests/unit/test_golr_search_query.py tests/unit/test_owlsim2_api.py \
		tests/test_collections.py \
		tests/test_gocamgen.py \
		tests/test_gpi_isoform_replacement.py \
		tests/test_validate_cli.py; \
	fi


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

poetry:
	poetry config virtualenvs.in-project true
	rm -f pyproject.toml
	rm -f poetry.lock
	poetry init --name "ontobio" --no-interaction
	sed -i.bak 's/readme = "README\.md"/readme = "README\.rst"/' pyproject.toml
	rm pyproject.toml.bak
	poetry add $$( cat requirements.txt )
	poetry install

poetry-test:
	poetry run make travis_test