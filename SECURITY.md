# Security Policy

## Supported Versions

ReasonScript is currently in the `0.x` alpha phase (see [VERSION](VERSION)
and [COMPATIBILITY.md](COMPATIBILITY.md)). There is no long-term support
branch yet: security fixes are made against the latest release on the
default branch.

| Version | Supported |
| --- | --- |
| `0.1.x-alpha` (latest) | Yes |
| Older pre-releases | No |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Instead, report privately using one of the following channels, in order of
preference:

1. [GitHub Security Advisories](https://github.com/chigenori053/reasonscript/security/advisories/new)
   for this repository ("Report a vulnerability" under the Security tab).
2. Email the maintainers listed in [GOVERNANCE.md](GOVERNANCE.md) with the
   subject line `[SECURITY] <short description>`.

Please include:

- A description of the vulnerability and its potential impact.
- Steps to reproduce, including affected component (Compiler, Runtime,
  ReasonUnit, WorldModel, SDK, LSP/IDE, Toolchain — see
  [docs/architecture/overview.md](docs/architecture/overview.md)).
- ReasonScript version/commit and environment details.
- A proof-of-concept if available.

## What to Expect

- Acknowledgement of your report within a best-effort window (there is no
  contractual SLA at this project stage; see [SUPPORT.md](SUPPORT.md)).
- An assessment of severity and affected components.
- Coordinated disclosure: we will work with you on a fix and an advisory
  before any public disclosure, and credit reporters who wish to be
  credited.

## Scope

In scope: the ReasonScript language toolchain, compiler, runtimes
(`HybridRuntime`, `RuntimeReal`, `RuntimeComplex`), SDKs, LSP/IDE
integrations, and toolchain commands contained in this repository.

Out of scope: vulnerabilities in third-party dependencies (report those
upstream), and issues that require an already-compromised local machine or
maliciously crafted `.reason`/`.rsn` source that the user knowingly executes
without a trust boundary — treat ReasonScript source execution like running
any other untrusted program.

## Known Limitations

ReasonScript is pre-1.0 software (`0.1.0-alpha`). Sandboxing,
capability-scoped execution, and hardened untrusted-input handling are not
yet part of the guarantees offered by the Runtime; do not run untrusted
ReasonScript programs in a security-sensitive context. See
[CHANGELOG.md](CHANGELOG.md) for the current list of known limitations.
