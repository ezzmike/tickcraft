# Contributing to Tickcraft

Thank you for helping improve Tickcraft. This is an experimental,
paper-first workbench: contributions must preserve the fact that the shipped
CLI is read-only or paper-only and must not imply that a strategy is profitable
or appropriate for live use.

## Before opening a change

- Discuss substantial behavior changes in an issue first, especially anything
  related to exchange APIs, credentials, order handling, risk limits, or
  settlement.
- Do not add live order submission, cancellation, account funding, or
  credential collection to this project.
- Never commit API tokens, private keys, local SQLite ledgers, or real account
  and trading data. See [SECURITY.md](SECURITY.md) for private reporting.
- Keep claims about fees, fills, market data, and strategy performance specific
  and testable. An illustrative paper baseline is not investment advice.

## Local setup

Tickcraft supports Python 3.11 and newer. Create a virtual environment, install
the project, and run the offline test suite:

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
```

The tests must run without exchange credentials and must not make network calls
or start a trader. Use `python -m tickcraft --help` to inspect CLI options
without fetching market data.

## Pull requests

Keep each pull request focused. Explain the user-visible change, its safety
implications, and the validation you ran. Update documentation when a command,
default, limitation, or compatibility promise changes.

Before requesting review:

1. Rebase or otherwise resolve conflicts with the target branch as appropriate.
2. Run the offline unit-test command above.
3. Confirm `git diff --check` reports no whitespace errors.
4. Confirm no local ledger, credential, private key, generated distribution, or
   other sensitive artifact is included.

The maintainers may decline changes that expand the project beyond its
paper-only scope or make unsupported claims about trading performance.

## Reporting conduct concerns

Use the repository owner's private contact path for conduct or security
concerns that should not be discussed in public.
