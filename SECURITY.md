# Security Policy

This repository holds the Vek-Snap ComfyUI custom nodes (`veksnap_bridge` and
`veksnap_utils`). Thank you for helping keep the project and its users safe.

## Supported versions

These nodes track the current Vek-Snap release. Security fixes are applied to the most
recent published version only. Please reproduce any issue on the latest version before
reporting it.

## Reporting a vulnerability

Please report security issues privately. Do not open a public issue, pull request, or
discussion for a suspected vulnerability, and please do not disclose it publicly until a
fix is available.

Preferred: use GitHub's private vulnerability reporting on this repository
(the **Security** tab, then **Report a vulnerability**).

Alternative: email **contact@squishycode.ai** with a subject line beginning with
`SECURITY:`.

Please include, where you can:

- A clear description of the issue and its impact.
- The affected node, the ComfyUI version, and your operating system.
- Step-by-step reproduction, including any workflow, prompt, or input needed.
- A proof of concept, logs, or screenshots if available.

## What to expect

We are a small team and respond on a best-effort basis.

- Acknowledgement of your report within 5 business days.
- An initial assessment and severity triage within 10 business days.
- Coordinated disclosure once a fix is available. With your permission we will credit
  you in the release notes and the advisory.

## Scope

These nodes run inside ComfyUI on the user's own machine. The `veksnap_bridge` Python
side is a zero-import shim that declares a web directory only; the browser-side glue
loads a workflow into the local ComfyUI instance.

In scope:

- Code execution, command injection, or path traversal introduced by these nodes.
- Any unintended outbound network connection made by these nodes.
- Exposure of local files, secrets, or user content caused by these nodes.

Generally out of scope:

- Vulnerabilities in ComfyUI itself or in other third-party custom nodes. Please report
  those to their maintainers.
- Issues that require the user to load untrusted models or workflows. Treat downloaded
  models and workflows as untrusted content.
- Findings that require physical access to an already-compromised machine.

## Safe harbor

We will not pursue or support legal action against researchers who act in good faith,
avoid privacy violations and data destruction, and give us a reasonable chance to
address an issue before any public disclosure. If in doubt, ask first.
