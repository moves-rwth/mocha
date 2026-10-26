# Contributing to MoChA

Bug reports, documentation improvements, and code contributions are welcome.
Use the [issue tracker](https://github.com/moves-rwth/mocha/issues) for bugs
and feature requests. For a bug report, include a small reproducing example,
the expected result, the actual result, and your Python and MoChA versions.

## Set up a development environment

Use Python 3.11 or later. CI is configured to test Python 3.11 through 3.15
on Ubuntu. Run these commands from the repository root.

On Linux or macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows, using PowerShell:

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
```

Install an editable checkout with visualisation support and the development
tools:

```bash
python -m pip install -e '.[visualization,typecheck]'
python -m pip install build twine
```

An editable installation makes source changes available without reinstalling
the package. The development tools are separate from MoChA's runtime
dependencies.

Install the [Graphviz executables](https://graphviz.org/download/) separately
and make sure `dot` is on your `PATH`:

```bash
dot -V
```

The Python `graphviz` dependency does not install these executables.

## Run the tests

```bash
python -m unittest discover -s tests -v
```

Inspect any skipped tests: rendering tests require `dot`. Add focused
regression tests when fixing a behavioral bug. For algorithm changes,
include the model assumptions and an example that exercises the change.

## Check library types

```bash
python -m mypy
```

The configuration in `pyproject.toml` checks all of `src/mocha` in strict mode,
targeting Python 3.11. The `typecheck` extra supplies mypy and the JSON Schema
stubs. A Graphviz-only override lets mypy read that dependency's partial
source annotations; checking calls to Graphviz is limited by those annotations.
CI runs the same library check.

## Check the typing example

```bash
python examples/typed_usage.py
python -m mypy --strict examples/typed_usage.py
```

The example uses the public API to build an integer-state transition system.
`typing.assert_type` checks that type inference preserves integer states in
the reachability result. The ordinary `assert` checks the reachable values
at runtime. Expected output is `Reachable states: [0, 1, 2]`, and mypy should
report no issues.

This checks the consumer example, rather than type-checking the entire
library. To verify the type information in a distribution, repeat it against
the installed wheel as described below.

## Validate the release artifacts

These Linux/macOS shell commands use a new temporary directory so older
builds and development installations cannot supply the package being tested.
Run them from the repository root, with the development environment active.
Keep the same terminal open throughout this section.

```bash
artifact_check_dir=$(mktemp -d)
python -m build --outdir "$artifact_check_dir/dist"
python -m twine check --strict "$artifact_check_dir"/dist/*
python -m venv "$artifact_check_dir/venv"
```

The default build creates a source archive and then builds the wheel from
that archive. First install the base wheel and check that the core API works
without the optional Graphviz package:

```bash
"$artifact_check_dir/venv/bin/python" -m pip install "$artifact_check_dir"/dist/*.whl
"$artifact_check_dir/venv/bin/python" -I .github/scripts/smoke_base_install.py
```

Next check the typing example against the wheel:

```bash
"$artifact_check_dir/venv/bin/python" -m pip install mypy
"$artifact_check_dir/venv/bin/python" -I examples/typed_usage.py
"$artifact_check_dir/venv/bin/python" -I -m mypy --strict examples/typed_usage.py
```

Finally, install the visualisation extra and run the full test suite:

```bash
for wheel in "$artifact_check_dir"/dist/*.whl; do
    "$artifact_check_dir/venv/bin/python" -m pip install "${wheel}[visualization]"
done
"$artifact_check_dir/venv/bin/python" -I -m unittest discover -s tests -v
```

`-I` ignores `PYTHONPATH` and excludes the script directory from Python's
import path. The fresh environment therefore exercises the installed wheel.
The Graphviz executables must still be available to run the rendering tests.

## Publish a release

The `Publish Python package` workflow publishes the wheel and source archive
to PyPI when a GitHub release is published. It first runs the full CI workflow,
checks that the release tag matches the version in `pyproject.toml`, builds
the distributions, and validates their metadata. Publishing uses
[PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/)
with the GitHub environment `pypi`.

Before the first release:

1. Create a GitHub environment named `pypi` in `moves-rwth/mocha`.
2. On PyPI, configure a GitHub Trusted Publisher for `mocha-model-checking`
   with owner `moves-rwth`, repository `mocha`, workflow filename
   `pypi-publish.yml`, and environment `pypi`. If the project does not exist
   yet, use a
   [pending publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).
   This setup uses no PyPI API token.

For each release:

1. Update the version in `pyproject.toml` and the entry in `CHANGELOG.md`.
2. Complete the release-artifact checks above and merge the release changes
   into `main`. Confirm that CI passes for the intended release commit.
3. Create a GitHub release for that commit, using a tag such as `v0.1.0`
   (a bare `0.1.0` is also accepted). Use the changelog entry as the release
   notes, then publish the release to start the publication workflows.
4. Check that both `Publish Python package` and `Publish container` succeed.
   Confirm that the new version can be installed from PyPI and that the
   release tag is available at `ghcr.io/moves-rwth/mocha`.

Container releases use the GitHub release tag verbatim. A release marked as a
prerelease does not update the container's `latest` tag; it still triggers
Python package publication using the version declared in `pyproject.toml`.

For a trial release before `0.1.0`, use version `0.1.0rc1` in
`pyproject.toml`, tag the GitHub release `v0.1.0rc1`, and select **Set as a
pre-release**. After publication, install that candidate with
`python -m pip install 'mocha-model-checking==0.1.0rc1'`.

## Submit a pull request

Keep the change focused and explain the resulting behavior and how you
checked it. Update the README, relevant guides in `docs/`, and changelog when
the public behavior changes.
Include examples or counterexamples where they help explain an algorithm
change. CI runs on pull requests and on pushes to `main`.
