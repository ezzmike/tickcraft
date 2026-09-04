# Security

Tickcraft is experimental, paper-first software. The included CLI has no live
trading executor and does not require credentials for its public-data mode.
That does not remove the need to protect sensitive local data in downstream
experiments.

## Report a vulnerability

Use GitHub private vulnerability reporting when it is enabled for this
repository. Otherwise, contact the repository owner privately before public
disclosure. Do not report vulnerabilities, suspected secrets, or security
questions in a public issue.

Include the affected revision or release, a concise reproduction, the security
impact, and any suggested mitigation. Remove credentials, private keys, tokens,
SQLite ledgers, and personal data from the report. The project makes no
response-time or remediation SLA commitment.

## In scope

Examples include a defect that exposes local data, bypasses a documented safety
control, introduces an unsafe dependency or GitHub Actions configuration, or
causes the included code to submit live orders despite its paper-only design.

Questions about market outcomes, strategy performance, exchange availability,
or third-party account access are not security reports. This project does not
operate an exchange, custody funds, or provide trading or financial advice.

## Handling local data

Never commit credentials, RSA private keys, API tokens, logs containing them,
or `data/paper.sqlite`. Keep the paper ledger private: it may reveal strategy
parameters, market activity, and timing. If a secret is exposed, revoke or
rotate it with the issuer and remove it from every location under your control;
then make a private report with the minimum information needed to assess the
exposure.
