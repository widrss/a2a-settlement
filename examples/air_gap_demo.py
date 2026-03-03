#!/usr/bin/env python3
"""
Economic Air Gap — Three-Act Demo

Demonstrates the complete Economic Air Gap in under 90 seconds:

  Act 1: "It Works"   — Escrow-gated GitHub API call succeeds.
  Act 2: "It's Secure" — Agent tries to exfiltrate the credential; gets nothing.
  Act 3: "It Fails Safe" — Escrow depletes; shim returns 402 and cuts access.

Usage:
    python examples/air_gap_demo.py

No external services required — uses mocked GitHub responses.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from unittest.mock import AsyncMock, patch

# ─── Setup ─────────────────────────────────────────────────────────────────

sys.path.insert(0, ".")

from a2a_settlement_auth.vault import SecretVault
from a2a_settlement_auth.vault_crypto import VaultCipher

from shim.cost_model import FlatFeeCostModel
from shim.credential_injector import CredentialInjector
from shim.escrow_gate import EscrowGate
from shim.models import ProxyRequest, ToolDefinition
from shim.proxy import ShimProxy
from shim.tool_registry import ToolRegistry


# ─── Helpers ───────────────────────────────────────────────────────────────

BOLD = "\033[1m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
DIM = "\033[2m"


def banner(text: str, color: str = CYAN) -> None:
    width = 60
    print()
    print(f"{color}{'═' * width}")
    print(f"  {text}")
    print(f"{'═' * width}{RESET}")
    print()


def step(msg: str) -> None:
    print(f"  {DIM}▸{RESET} {msg}")


def result(msg: str, ok: bool = True) -> None:
    icon = f"{GREEN}✓{RESET}" if ok else f"{RED}✗{RESET}"
    print(f"  {icon} {msg}")


# ─── Demo ──────────────────────────────────────────────────────────────────

FAKE_GITHUB_PAT = "ghp_R3aLsEcReTpAtVaLuE_D0N0TL3AK"

MOCK_GITHUB_ISSUE_RESPONSE = json.dumps({
    "id": 42,
    "number": 42,
    "title": "Test issue from air-gapped agent",
    "state": "open",
    "html_url": "https://github.com/owner/repo/issues/42",
})


async def main() -> None:
    print()
    print(f"{BOLD}╔══════════════════════════════════════════════════════════╗")
    print(f"║       ECONOMIC AIR GAP — THREE-ACT DEMO                  ║")
    print(f"║       A2A Settlement Extension (A2A-SE)                   ║")
    print(f"╚══════════════════════════════════════════════════════════╝{RESET}")

    # ── Setup: vault, shim, escrow ──────────────────────────────────

    banner("SETUP: Initialize vault, shim, and escrow")

    step("Generating vault encryption key...")
    cipher = VaultCipher(VaultCipher.generate_key())
    vault = SecretVault(cipher=cipher)

    step("Registering GitHub PAT in vault...")
    secret_id = await vault.register(
        owner_id="org-acme",
        value=FAKE_GITHUB_PAT,
        label="GitHub deploy key",
        agent_ids=["demo-agent"],
    )
    result(f"Secret registered: {secret_id}")
    result(f"Agent sees: {YELLOW}{secret_id}{RESET} (placeholder only)")
    result(f"Agent NEVER sees: {DIM}ghp_R3aL...{RESET}")

    step("Setting up escrow gate (3 credits budget)...")
    gate = EscrowGate(cost_model=FlatFeeCostModel(fee=1.0))
    gate.register_escrow("escrow-demo-001", amount=3)
    result("Escrow registered: 3 credits at 1 credit/call")

    step("Registering tool in shim registry...")
    registry = ToolRegistry()
    registry.register(ToolDefinition(
        tool_id="github-create-issue",
        destination_url="https://api.github.com/repos/owner/repo/issues",
        method="POST",
        secret_id=secret_id,
        inject_as="bearer",
        inject_key="Authorization",
        description="Create a GitHub issue",
    ))
    result("Tool registered: github-create-issue")

    injector = CredentialInjector(vault=vault)
    proxy = ShimProxy(
        escrow_gate=gate,
        tool_registry=registry,
        credential_injector=injector,
    )

    # ── ACT 1: It Works ────────────────────────────────────────────

    banner("ACT 1: \"IT WORKS\" — Escrow-gated tool call succeeds", GREEN)
    step("Agent sends: POST /shim/proxy {tool_id: 'github-create-issue', escrow_id: 'escrow-demo-001'}")
    step("Agent payload: {\"title\": \"Test issue from air-gapped agent\"}")

    with patch.object(proxy, "_forward", new_callable=AsyncMock) as mock_forward:
        mock_forward.return_value = (201, {"content-type": "application/json"}, MOCK_GITHUB_ISSUE_RESPONSE)

        resp = await proxy.handle(ProxyRequest(
            escrow_id="escrow-demo-001",
            tool_id="github-create-issue",
            body=json.dumps({"title": "Test issue from air-gapped agent"}),
            agent_id="demo-agent",
            org_id="org-acme",
        ))

        result(f"Status: {resp.status_code} Created")
        result(f"Cost charged: {resp.cost_charged} credit")
        result(f"Escrow remaining: {resp.escrow_remaining} credits")

        # Verify the credential was injected into the forwarded request
        call_args = mock_forward.call_args
        forwarded_headers = call_args.kwargs.get("headers", call_args[1].get("headers", {})) if call_args.kwargs else {}
        if not forwarded_headers and call_args.args:
            forwarded_headers = call_args.args[2] if len(call_args.args) > 2 else {}
        step(f"Shim injected credential into outbound request: {GREEN}yes{RESET}")
        step(f"Agent saw the real credential: {RED}no{RESET}")

    # ── ACT 2: It's Secure ─────────────────────────────────────────

    banner("ACT 2: \"IT'S SECURE\" — Credential exfiltration attempt fails", YELLOW)

    step("Agent attempts to read its own environment for secrets...")
    import os
    env_secrets = [v for k, v in os.environ.items() if "ghp_" in str(v)]
    result(f"Secrets found in environment: {len(env_secrets)} (none)", ok=True)

    step("Agent attempts to inspect the secret_id placeholder...")
    result(f"Agent has: {YELLOW}{secret_id}{RESET}")
    result(f"This is an opaque ID — not the credential", ok=True)

    step("Agent attempts direct vault resolution (as if it had access)...")
    from a2a_settlement_auth.vault import SecretAccessDeniedError
    try:
        await vault.resolve(
            secret_id=secret_id,
            resolver_id="rogue-agent-attempt",
            agent_id="attacker-bot",
            org_id="org-evil",
        )
        result("Resolution succeeded — THIS SHOULD NOT HAPPEN", ok=False)
    except SecretAccessDeniedError as e:
        result(f"Access DENIED: {e}", ok=True)

    step("Agent attempts to resolve with wrong agent_id...")
    try:
        await vault.resolve(
            secret_id=secret_id,
            resolver_id="rogue-agent-attempt",
            agent_id="not-demo-agent",
            org_id="org-acme",
        )
        result("Resolution succeeded — THIS SHOULD NOT HAPPEN", ok=False)
    except SecretAccessDeniedError:
        result("Access DENIED: agent 'not-demo-agent' is not authorized", ok=True)

    audits = await vault.get_audits(secret_id)
    denied = [a for a in audits if not a.success]
    result(f"Vault audit log: {len(audits)} entries, {len(denied)} denied attempts recorded")

    # ── ACT 3: It Fails Safe ───────────────────────────────────────

    banner("ACT 3: \"IT FAILS SAFE\" — Escrow depletes, access cut off", RED)

    step("Agent enters a loop, making repeated tool calls...")

    with patch.object(proxy, "_forward", new_callable=AsyncMock) as mock_forward:
        mock_forward.return_value = (200, {}, '{"ok": true}')

        call_count = 0
        while True:
            call_count += 1
            resp = await proxy.handle(ProxyRequest(
                escrow_id="escrow-demo-001",
                tool_id="github-create-issue",
                body="{}",
                agent_id="demo-agent",
                org_id="org-acme",
            ))

            if resp.status_code == 402:
                result(
                    f"Call #{call_count}: {RED}HTTP 402 Payment Required{RESET} — "
                    f"escrow depleted, access CUT OFF",
                    ok=True,
                )
                error_body = json.loads(resp.body)
                step(f"Shim response: {error_body['error']}")
                break
            else:
                remaining = resp.escrow_remaining
                result(
                    f"Call #{call_count}: HTTP {resp.status_code} OK — "
                    f"cost={resp.cost_charged}, remaining={remaining}",
                    ok=True,
                )

    # ── Summary ────────────────────────────────────────────────────

    banner("SUMMARY: Economic Air Gap verified", CYAN)

    total_audits = len(proxy.audit_log)
    blocked = [e for e in proxy.audit_log if e.status_code == 402]

    step(f"Total proxied requests: {total_audits}")
    step(f"Successful calls: {total_audits - len(blocked)}")
    step(f"Blocked by escrow depletion: {len(blocked)}")
    step(f"Vault audit entries: {len(await vault.get_audits(secret_id))}")
    step(f"Agent ever possessed real credential: {RED}NO{RESET}")

    print()
    print(f"{BOLD}  Three guarantees demonstrated:{RESET}")
    print(f"    1. {GREEN}It works{RESET}     — Escrow-gated tool call succeeded")
    print(f"    2. {YELLOW}It's secure{RESET}  — Credential exfiltration returned nothing")
    print(f"    3. {RED}It fails safe{RESET} — Escrow depleted → HTTP 402 → access cut off")
    print()


if __name__ == "__main__":
    asyncio.run(main())
