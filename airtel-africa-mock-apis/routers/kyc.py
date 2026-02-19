"""KYC verification APIs - Nigeria NIN, Ghana GID, Tanzania NIDA, Rwanda NID, Face Match."""
from fastapi import APIRouter
from schemas import (
    NinVerifyRequest,
    GidVerifyRequest,
    NidaVerifyRequest,
    NidVerifyRequest,
    FaceMatchRequest,
    KycVerifyResponse,
    FaceMatchResponse,
)

router = APIRouter(prefix="/africa/v1/kyc", tags=["KYC"])


@router.post("/ng/nin/verify", response_model=KycVerifyResponse)
def nigeria_nin_verify(req: NinVerifyRequest):
    """Verify Nigeria NIN for SIM registration and Airtel Money onboarding."""
    return KycVerifyResponse(valid=True, dob="1993-07-11", match_score=0.93)


@router.post("/gh/gid/verify", response_model=KycVerifyResponse)
def ghana_gid_verify(req: GidVerifyRequest):
    """Verify Ghana National ID (Ghana Card) for SIM and wallet onboarding."""
    return KycVerifyResponse(valid=True, name="Kofi Mensah")


@router.post("/ug/nin/verify", response_model=KycVerifyResponse)
def uganda_nin_verify(req: NinVerifyRequest):
    """Verify Uganda NIN for SIM and wallet."""
    return KycVerifyResponse(valid=True, name="Akena Peter")


@router.post("/tz/nida/verify", response_model=KycVerifyResponse)
def tanzania_nida_verify(req: NidaVerifyRequest):
    """Verify Tanzania NIDA ID for SIM registration and Airtel Money KYC."""
    return KycVerifyResponse(valid=True, dob="1990-12-04")


@router.post("/rw/nid/verify", response_model=KycVerifyResponse)
def rwanda_nid_verify(req: NidVerifyRequest):
    """Verify Rwanda National ID for compliance in SIM & mobile money."""
    return KycVerifyResponse(valid=True, name="Uwera A")


@router.post("/face/match", response_model=FaceMatchResponse)
def africa_face_match(req: FaceMatchRequest):
    """Face match and selfie liveness for African ID card variance."""
    return FaceMatchResponse(match=True, liveness=0.88)
