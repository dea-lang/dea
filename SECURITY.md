# Security Policy

## Supported versions

This repository is experimental. Security fixes, if any, are provided on a best-effort basis for the latest commit on
the default branch.

## Reporting a vulnerability

Please report security issues privately and do not open a public issue.

Use GitHub's [private vulnerability reporting](https://github.com/googlielmo/dea-lang/security/advisories/new) or send
an email to: googlielmo@gmail.com

Include:

- A description of the issue and its impact
- Steps to reproduce (PoC if available)
- Affected version/commit and platform details
- Any suggested fix or mitigation

You can expect an initial response within a reasonable timeframe. We will coordinate disclosure once a fix or mitigation
is available.

## Scope

Examples of security-relevant issues:

- Memory safety bugs in the L0 C runtime (`l0/compiler/shared/runtime/`)
- Compiler vulnerabilities that enable arbitrary code execution during compilation
- Generated C code that introduces exploitable undefined behavior
- Supply-chain issues in monorepo build scripts or release artifacts

Non-security bugs (crashes without exploitability, miscompilations without a security angle, feature requests) should be
filed as normal [GitHub issues](https://github.com/googlielmo/dea-lang/issues).
