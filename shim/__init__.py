"""
Security Shim -- Economic Air Gap proxy for AI agents.

The shim is a fully optional forward proxy that sits between agents and
external APIs. It enforces escrow-gated access, injects real credentials
at the last moment (so agents never possess them), and logs every proxied
request for SEC 17a-4 compliance.

This module is part of the a2a-settlement core repo but runs as a
separate service. Operators who don't need credential isolation can
skip it entirely; the existing A2A-SE escrow lifecycle works without it.
"""
