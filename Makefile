# DOCS
# See https://github.com/pypa/virtualenv/issues/149
pydoc-%:
	python -m pydoc ontobio.ontol

#PACKAGES = prefixcommons scigraph biogolr
PACKAGES = ontobio prefixcommons
subpackage_tests: $(patsubst %,test-%,$(PACKAGES))

test:
	pytest tests/*.py

debug_test:
	pytest -s -vvvv tests/*.py

t-%:
	pytest tests/test_$*.py

foo:
	which pytest

# only run local tests
travis_test:
	pytest tests/test_*local*.py tests/test_*parser*.py

cleandist:
	rm dist/* || true

# TODO: manually increment version in ontobio/__init__.sh, run . bump.sh, then this
release: cleandist
	python setup.py sdist bdist_wheel bdist_egg
	twine upload dist/*

nb:
	PYTHONPATH=.. jupyter notebook

# Hack: generate marshmallow schema from flaskrest serializers
# used to make assoc_schema.py
mm:
	./bin/flask2marshmallow.pl ../biolink-api/biolink/datamodel/serializers.py

VERSION = "v0.0.1" 
IM = cmungall/ontobio
build-docker:
	@docker build -t $(IM):$(VERSION) . \
	&& docker tag $(IM):$(VERSION) $(IM):latest
