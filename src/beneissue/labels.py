"""Label definitions for beneissue workflow."""

from dataclasses import dataclass


@dataclass
class LabelDef:
    """Label definition with color and description."""

    color: str
    description: str


# All labels used by beneissue workflow
LABELS: dict[str, LabelDef] = {
    # Triage results
    "triage/valid": LabelDef("0E8A16", "Valid issue, ready for analysis"),
    "triage/invalid": LabelDef("ffffff", "Invalid issue, will not be worked on"),
    "triage/duplicate": LabelDef("cfd3d7", "Duplicate of another issue"),
    "triage/needs-info": LabelDef("d876e3", "Needs more information"),
    # Fix decision
    "fix/auto-eligible": LabelDef("0E8A16", "AI auto-fix eligible"),
    "fix/manual-required": LabelDef("FBCA04", "Requires human implementation"),
    "fix/comment-only": LabelDef("C5DEF5", "No code change needed"),
    "fix/completed": LabelDef("6f42c1", "AI resolved without human intervention"),
    "fix/failed": LabelDef("d73a4a", "Auto-fix failed"),
}


def get_label_names() -> list[str]:
    """Get all label names."""
    return list(LABELS.keys())


def get_triage_labels() -> dict[str, list[str]]:
    """Get triage decision to label mapping."""
    return {
        "valid": ["triage/valid"],
        "invalid": ["triage/invalid"],
        "duplicate": ["triage/duplicate"],
        "needs_info": ["triage/needs-info"],
    }
