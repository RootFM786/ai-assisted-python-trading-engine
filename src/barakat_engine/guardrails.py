"""
RuntimeError guardrails with standardized message format.
Standard library only; no contract-specific logic.
"""

from typing import Any, Optional

SEAM_ALLOWED = frozenset({"CALLABLE", "INPUTS", "OUTPUTS", "CADENCE", "OWNERSHIP"})


def _fmt_idx_time(idx: Optional[Any], time: Optional[Any]) -> tuple[str, str]:
    idx_str = "NA" if idx is None else str(idx)
    time_str = "NA" if time is None else str(time)
    return idx_str, time_str


def _format_message(
    contract: str,
    section: str,
    edge: str,
    seam: str,
    message: str,
    idx: Optional[Any] = None,
    time: Optional[Any] = None,
) -> str:
    if seam not in SEAM_ALLOWED:
        raise ValueError(f"Invalid SEAM: {seam!r}. Allowed: {sorted(SEAM_ALLOWED)}")
    idx_str, time_str = _fmt_idx_time(idx, time)
    return (
        f"GUARDRAIL FAIL | CONTRACT={contract} | SECTION={section} | "
        f"EDGE={edge} | SEAM={seam} | idx={idx_str} | time={time_str} | {message}"
    )


def gr_fail(
    contract: str,
    section: str,
    edge: str,
    seam: str,
    message: str,
    *,
    idx: Optional[Any] = None,
    time: Optional[Any] = None,
) -> None:
    """Raise RuntimeError with the guardrail message format."""
    raise RuntimeError(
        _format_message(contract, section, edge, seam, message, idx=idx, time=time)
    )


def gr_require(
    condition: bool,
    contract: str,
    section: str,
    edge: str,
    seam: str,
    message: str,
    *,
    idx: Optional[Any] = None,
    time: Optional[Any] = None,
) -> None:
    """If condition is false, raise RuntimeError via gr_fail."""
    if not condition:
        gr_fail(contract, section, edge, seam, message, idx=idx, time=time)


def require_callable(
    condition: bool,
    contract: str,
    section: str,
    edge: str,
    message: str,
    *,
    idx: Optional[Any] = None,
    time: Optional[Any] = None,
) -> None:
    """gr_require with SEAM=CALLABLE."""
    gr_require(
        condition, contract, section, edge, "CALLABLE", message, idx=idx, time=time
    )


def require_inputs(
    condition: bool,
    contract: str,
    section: str,
    edge: str,
    message: str,
    *,
    idx: Optional[Any] = None,
    time: Optional[Any] = None,
) -> None:
    """gr_require with SEAM=INPUTS."""
    gr_require(
        condition, contract, section, edge, "INPUTS", message, idx=idx, time=time
    )


def require_outputs(
    condition: bool,
    contract: str,
    section: str,
    edge: str,
    message: str,
    *,
    idx: Optional[Any] = None,
    time: Optional[Any] = None,
) -> None:
    """gr_require with SEAM=OUTPUTS."""
    gr_require(
        condition, contract, section, edge, "OUTPUTS", message, idx=idx, time=time
    )


def require_cadence(
    condition: bool,
    contract: str,
    section: str,
    edge: str,
    message: str,
    *,
    idx: Optional[Any] = None,
    time: Optional[Any] = None,
) -> None:
    """gr_require with SEAM=CADENCE."""
    gr_require(
        condition, contract, section, edge, "CADENCE", message, idx=idx, time=time
    )


def require_ownership(
    condition: bool,
    contract: str,
    section: str,
    edge: str,
    message: str,
    *,
    idx: Optional[Any] = None,
    time: Optional[Any] = None,
) -> None:
    """gr_require with SEAM=OWNERSHIP."""
    gr_require(
        condition, contract, section, edge, "OWNERSHIP", message, idx=idx, time=time
    )
