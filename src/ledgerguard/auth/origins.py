"""Trusted origin parsing, normalization, and validation for CORS and CSRF."""

from urllib.parse import urlparse


def parse_origin_tuple(origin_str: str) -> tuple[str, str, int] | None:
    """Parse complete origin into (scheme, host, effective_port).

    Returns None if malformed, missing scheme/host, or containing path/query/fragment.
    """
    if not origin_str or not isinstance(origin_str, str):
        return None
    raw = origin_str.strip()
    if not raw or "://" not in raw:
        return None

    try:
        parsed = urlparse(raw)
        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            return None
        if not parsed.hostname:
            return None
        # Origins must not contain paths, queries, fragments, or user credentials
        if parsed.path not in ("", "/") or parsed.query or parsed.fragment or parsed.username or parsed.password:
            return None

        effective_port = parsed.port if parsed.port is not None else (443 if scheme == "https" else 80)
        return scheme, parsed.hostname.lower(), effective_port
    except Exception:
        return None


def normalize_origin(origin_str: str) -> str:
    """Return canonical origin representation string or raise ValueError if invalid."""
    res = parse_origin_tuple(origin_str)
    if not res:
        raise ValueError(f"Invalid origin format: {origin_str!r}. Expected complete origin like 'https://host[:port]'")
    scheme, host, port = res
    is_standard_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    if is_standard_port:
        return f"{scheme}://{host}"
    return f"{scheme}://{host}:{port}"


def is_origin_allowed(candidate_origin: str, trusted_origins: list[str]) -> bool:
    """Compare candidate origin against trusted origins by scheme, host, and effective port."""
    parsed_cand = parse_origin_tuple(candidate_origin)
    if not parsed_cand:
        return False

    cand_scheme, cand_host, cand_port = parsed_cand
    for trusted in trusted_origins:
        parsed_trust = parse_origin_tuple(trusted)
        if not parsed_trust:
            continue
        trust_scheme, trust_host, trust_port = parsed_trust
        if cand_scheme == trust_scheme and cand_host == trust_host and cand_port == trust_port:
            return True
    return False
