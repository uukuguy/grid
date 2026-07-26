from pathlib import Path


ALIGNMENT_DIR = Path(__file__).resolve().parents[1]


def test_alignment_documents_cover_locked_platform_skeleton() -> None:
    matrix = (ALIGNMENT_DIR / "ALIGNMENT_MATRIX.md").read_text(encoding="utf-8")
    memory = (ALIGNMENT_DIR / "memory_manifest.md").read_text(encoding="utf-8")
    pipes = (ALIGNMENT_DIR / "pipe_topology.md").read_text(encoding="utf-8")
    certifier = (ALIGNMENT_DIR / "certifier_surface.md").read_text(encoding="utf-8")

    for layer in ("L0 Protocol", "L1 Execution", "L2 Assets", "L3 Governance", "L4 Orchestration", "L5 Cowork"):
        assert layer in matrix
    for pipeline in ("Hook pipeline", "Data-flow pipeline", "Session-control pipeline"):
        assert pipeline in matrix or pipeline in pipes
    for card in ("Event card", "Evidence pack", "Action card", "Approval card"):
        assert card in matrix
    for tool in (
        "memory_search",
        "memory_read",
        "memory_write_anchor",
        "memory_write_file",
        "memory_list",
        "memory_archive",
        "memory_confirm",
    ):
        assert tool in memory
    for boundary in ("L4 → L1", "L2 MCP", "OPA", "Sandbox"):
        assert boundary in matrix or boundary in pipes or boundary in certifier


def test_cross_index_has_status_phase_and_owner_for_every_row() -> None:
    matrix = (ALIGNMENT_DIR / "ALIGNMENT_MATRIX.md").read_text(encoding="utf-8")
    cross_index = matrix.split("## Spec section cross-index", maxsplit=1)[1]
    rows = [line for line in cross_index.splitlines() if line.startswith("| §")]

    assert len(rows) >= 30
    allowed = {"aligned", "partial", "missing", "deferred_to_v3.11+", "not_certified"}
    for row in rows:
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        assert len(cells) == 4
        assert cells[1] in allowed
        assert cells[2]
        assert cells[3]
