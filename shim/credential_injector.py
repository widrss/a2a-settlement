"""Credential Injector -- resolves secret_id and injects into outbound requests.

Calls the Secret Vault's internal API to resolve a secret_id to the
real credential value, then injects it into the outbound HTTP request
at the position specified by the tool definition.
"""

from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse

from .models import ToolDefinition

logger = logging.getLogger("shim.credential_injector")


class CredentialInjector:
    """Resolves secret IDs and injects credentials into outbound requests.

    In the reference implementation, the injector calls a local vault
    instance directly. In production, it would call the vault's
    ``POST /secrets/resolve`` endpoint via internal API key.
    """

    def __init__(self, vault=None):
        """
        Args:
            vault: A ``SecretVault`` instance (from a2a_settlement_auth.vault).
                   If None, resolve() must be called with the value pre-resolved.
        """
        self._vault = vault

    async def resolve_secret(
        self,
        secret_id: str,
        agent_id: str,
        escrow_id: Optional[str] = None,
        org_id: Optional[str] = None,
    ) -> str:
        """Resolve a secret_id to the real credential value via the vault."""
        if self._vault is None:
            raise RuntimeError("No vault configured on CredentialInjector")
        return await self._vault.resolve(
            secret_id=secret_id,
            resolver_id="shim",
            agent_id=agent_id,
            escrow_id=escrow_id,
            org_id=org_id,
        )

    def inject(
        self,
        credential: str,
        headers: dict[str, str],
        url: str,
        body: Optional[str],
        inject_as: str = "bearer",
        inject_key: str = "Authorization",
    ) -> tuple[dict[str, str], str, Optional[str]]:
        """Inject a credential into the outbound request.

        Args:
            credential: The real credential value.
            headers: Mutable headers dict.
            url: The destination URL (may be modified for query injection).
            body: The request body (may be modified for body injection).
            inject_as: One of 'header', 'bearer', 'query', 'body'.
            inject_key: The header name, query param, or body field.

        Returns:
            Tuple of (headers, url, body) with the credential injected.
        """
        if inject_as == "bearer":
            headers[inject_key] = f"Bearer {credential}"
        elif inject_as == "header":
            headers[inject_key] = credential
        elif inject_as == "query":
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            params[inject_key] = [credential]
            new_query = urlencode(params, doseq=True)
            url = urlunparse(parsed._replace(query=new_query))
        elif inject_as == "body":
            import json

            try:
                body_dict = json.loads(body) if body else {}
            except (json.JSONDecodeError, TypeError):
                body_dict = {}
            body_dict[inject_key] = credential
            body = json.dumps(body_dict)
        else:
            headers[inject_key] = credential

        return headers, url, body

    async def resolve_and_inject(
        self,
        secret_id: str,
        agent_id: str,
        headers: dict[str, str],
        url: str,
        body: Optional[str],
        escrow_id: Optional[str] = None,
        org_id: Optional[str] = None,
        tool_def: Optional[ToolDefinition] = None,
    ) -> tuple[dict[str, str], str, Optional[str]]:
        """Resolve a secret and inject it in one call.

        Uses the tool definition's inject_as/inject_key if provided,
        otherwise defaults to Bearer header injection.
        """
        credential = await self.resolve_secret(
            secret_id=secret_id,
            agent_id=agent_id,
            escrow_id=escrow_id,
            org_id=org_id,
        )

        inject_as = "bearer"
        inject_key = "Authorization"
        if tool_def:
            inject_as = tool_def.inject_as
            inject_key = tool_def.inject_key

        return self.inject(credential, headers, url, body, inject_as, inject_key)
