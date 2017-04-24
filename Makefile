# DOCS
# See https://github.com/pypa/virtualenv/issues/149
pydoc-%:
	python -m pydoc ontobio.ontol

#PACKAGES = prefixcommons scigraph biogolr
PACKAGES = ontobio prefixcommons
subpackage_tests: $(patsubst %,test-%,$(PACKAGES))

test:
	pytest tests/*.py

cleandist:
	rm dist/*

# TODO: bump.sh
release: cleandist
	python setup.py sdist bdist_wheel bdist_egg
	twine upload dist/*
