* Note: pandoc must be installed before this works. You can install with
brew or apt-get or yum.

This section is only relevant for project maintainers. In order to release you must have a pypi account and be a "maintainer" on the ontobio project

To create a new release, do the following:

## Release Instructions -- Makefile

1. Ensure you're on master and up to date. Ensure also that twine is installed (`pip install twine`)
  > I always do this in my virtual environment activated
2. Obeying Semantic Versioning (https://semver.org/) bump the version number in `ontobio/ontobio/__init__.py` at the `__version__` variable.
  > At this point you should have one modified file, saved: `ontobio/ontobio/__init__.py`. You can check with `git diff` and/or `git status`.
3. Run the make relase target
   ```
   $ make USER=sauron release
   ```
  where the `USER` should be set to your pypi.org username.

  This will perform all the steps outlined in the below manual release section.

4. pypi will ask for your password. (You may also setup credentials with pypi, but that's now how the author who is writing this documentation has it setup.)

### Failure

If at any point this fails (wrong password, master is not updated, etc) you will have to just perform the steps manually as outlined in the below section.

Likely you will not be able to just rerun the release as the git portion of the release is not idempotent. Just note where you had an error and continue the steps corrected manually. I usually use the the Makefile as a direct reference if a command fails.

## Release instructions -- Manual

1. First check whether the `__version__` in [`ontobio/__init__.py`](ontobio/__init__.py) matches with the latest tag or PyPI release. If the version is the same then you need to bump the version to make a new release. Follow semantic versioning guidelines to decide whether the bump in version is major or minor.

2. If you did bump the version then run the following commands:

```sh
TAG=v`python setup.py --version`
git add ontobio/__init__.py
git commit --message="Upgrade to $TAG"
git push
git tag --annotate $TAG --message="Upgrade to $TAG"
git push --tags
  ```

3. Releasing on PyPI

> To ensure this is successful, make sure you have relevant permissions to Ontobio package on [PyPI](https://pypi.org/project/ontobio/)

Run the following commands (note, you will need a pypi token to do this work, see: https://pypi.org/help/#apitoken
and make a ~/.pypirc file to store your token):

```sh
make cleandist
python setup.py sdist bdist_wheel
twine upload --repository-url https://upload.pypi.org/legacy/ --username __token__ dist/*
```

****************************************************************************************************

#### to use a poetry development environment

1. create the pyproject.toml file and generate the .venv directory
```bash
make poetry
```
this command deletes any existing pyproject.toml and poetry.lock files as well as the .venv virtual environment
if it finds one.  It then creates a new pyproject.toml file out of the requirements.txt file, 
creates a .venv directory, and finally installs the dependencies into it.  This also creates a poetry.lock file.
At the moment, the poetry.lock and pyproject.toml files are both in .gitignore so that the source of truth for
the built environment is still requirements.txt.

2. to recreate the poetry virtual environment, just run the same `make poetry` command again, or if you want to avoid
reinstalling all the dependencies, just `rm -rf .venv` which will remove the local virtual environment and then
run `poetry install` to install via the `poetry.lock` file created in step 1 above. 

helpful poetry commands:
```bash
poetry install # install dependencies from poetry.lock
poetry run <command> # run a command in the poetry virtual environment
poetry env list # list all virtual environments and tags the one currently in use for the project
poetry show --why --tree [pypi_package_name] # show the dependency tree for pypi_package_name
poetry show [pypi_package_name] # show the version of pypi_package_name that is install in the current venv.
```

If we use a pyproject.toml file then we can use poetry to manage the dependencies and the virtual environment.
But for now, managing the dependencies in the requirements.txt file means that we don't want to add/update/remove
dependencies from pyproject.toml directly, nor do we want it to ever be the source of truth for the dependencies.

```bash
poetry add <package> # add a package to the pyproject.toml file and install it in the virtual environment
poetry remove <package> # remove a package from the pyproject.toml file and uninstall it from the virtual environment
poetry update # update all packages in the pyproject.toml file and the poetry.lock file
poetry update <package> # update the specified package in the pyproject.toml file and the poetry.lock file
poetry lock --no-update # update the poetry.lock file without updating the pyproject.toml file -- used when editing the 
# pyproject.toml file directly. 
```