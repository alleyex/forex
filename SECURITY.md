# Security Policy

## Supported Use

This repository contains trading and broker-integration code. Treat credentials, tokens, broker identifiers, and local runtime data as sensitive.

## Reporting A Vulnerability

Do not open public issues for security-sensitive findings.

Report vulnerabilities privately to the repository owner with:

- a short description of the issue
- impact assessment
- reproduction steps or proof of concept
- any suggested remediation

Until a private reporting channel is formalized, contact the maintainer directly through the GitHub account associated with this repository.

## Sensitive Data Handling

- Never commit `.env`, `token.json`, broker tokens, or machine-local config.
- Sanitize logs before sharing them outside the team.
- Use test or demo accounts when validating live-trading flows whenever possible.
