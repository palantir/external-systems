# `external-systems` dev README

[![Autorelease](https://img.shields.io/badge/Perform%20an-Autorelease-success.svg)](https://autorelease.general.dmz.palantir.tech/palantir/external-systems)

## Requirements

* python >= 3.9
* [poetry](https://python-poetry.org/docs/)

## Commands

### Install packages + scripts

This command will install all deps specified in `pyproject.toml` and make the scripts specified in `pyproject.toml` available in your python environment.

```sh
poetry install
```

### Run tests
```sh
poetry run poe test
```

### Run `mypy` checks
```sh
poetry run poe check_mypy
```

### Run linter checks (black, ruff, isort)
This will run the same checks as those that are run during CI checks - meaning it will raise any issues found, but not fix them.

```sh
poetry run poe check_format
```

### Run formatter (black, ruff, isort)
This will actually modify source files to fix any issues identified
```sh
poetry run poe format
```

### Build the library locally

```sh
poetry build
```

This will produce a `tar.gz` and a `whl` file in the `./dist` directory.
