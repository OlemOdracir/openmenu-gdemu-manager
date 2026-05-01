from ..core.models import BulkProposal


def valid_cover_proposals(proposals: dict[int, BulkProposal]) -> list[BulkProposal]:
    return [
        proposal
        for proposal in proposals.values()
        if proposal.status == "seleccionada"
        and proposal.candidate is not None
        and proposal.image is not None
    ]


def has_saveable_proposal(proposals: dict[int, BulkProposal]) -> bool:
    return any(proposal.status == "seleccionada" for proposal in proposals.values())
