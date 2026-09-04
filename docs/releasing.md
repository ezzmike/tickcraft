# Releasing Tickcraft

This checklist is for maintainers preparing a source or wheel distribution. A
release must preserve Tickcraft's paper-only positioning; publishing a package
does not validate strategy performance or authorize live trading.

1. Confirm that the version and public metadata in `pyproject.toml` are correct.
2. Review the README and security guidance for accurate descriptions of current
   behavior and limitations.
3. Run the offline test suite:

   ```sh
   python -m unittest discover -s tests -v
   ```

4. Build the distribution in a clean environment with a PEP 517 frontend such
   as `python -m build`, then inspect the generated source and wheel contents.
   Do not publish local ledgers, credentials, private keys, or generated test
   data.
5. Install the wheel in a fresh environment and run
   `python -m tickcraft --help` as a basic entry-point check.
6. Tag and publish only after the prior checks pass and the release notes state
   the relevant limitations or safety changes.

The project has no release automation or publication credential configuration in
this repository. Keep any publishing credentials outside the checkout and
follow the package index's current security guidance.
