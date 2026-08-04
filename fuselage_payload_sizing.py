from __future__ import annotations

from typing import Dict, Tuple

K_PACK = 1.15
SIGMA_HI = 2.5
SIGMA_LO = 0.5
ALPHA_HI = 1.30
ALPHA_LO = 0.77
REG_SLOPE = 0.472
CN = {"UNIFORM": 1.25, "BULGE": 1.85, "POD": 1.85}
CT = {"UNIFORM": 2.25, "BULGE": 3.00, "POD": 3.00}
STR_ELLIPSE = 1.00
STR_BOXY = 1.60


def _classify_archetype(sigma: float) -> str:
    if sigma >= SIGMA_HI:
        return "UNIFORM"
    if SIGMA_LO <= sigma < SIGMA_HI:
        return "BULGE"
    return "POD"


def _classify_section(alpha: float) -> str:
    if alpha > ALPHA_HI:
        return "TALL"
    if ALPHA_LO <= alpha <= ALPHA_HI:
        return "NEAR_CIRCULAR"
    return "WIDE"


def compute_section_locations(payload_length: float, payload_cg_x: float, fuselage_length: float) -> Dict[int, float | None]:
    """Return longitudinal station targets for the fuselage sections.
    Sections 0 and 4 are None (optimization variables, default positions).
    Sections 1, 2, 3 are payload-driven.
    """
    return {
        0: None,
        1: payload_cg_x - 0.5 * payload_length,
        2: payload_cg_x + 0.5 * payload_length,
        3: payload_cg_x+0.25 * fuselage_length,
        4: None,
    }


def size_payload_fuselage(l_p: float, w_p: float, h_p: float, b: float, 
                         mult_0: float | None = None, mult_3: float | None = None, mult_4: float | None = None) -> Dict[str, float | str]:
    """Size a fuselage from a payload box and wingspan using the requested archetype workflow.
    
    Args:
        l_p, w_p, h_p: Payload dimensions (m)
        b: Wingspan (m)
        mult_0: Width/height multiplier for section 0 (optional, defaults to not applying)
        mult_3: Width/height multiplier for section 3 (optional, defaults to not applying)
        mult_4: Width/height multiplier for section 4 (optional, defaults to not applying)
    
    Returns dict with archetype, dimensions, and section-specific W/H values.
    """
    if l_p <= 0 or w_p <= 0 or h_p <= 0 or b <= 0:
        raise ValueError("Payload dimensions and wingspan must be positive")

    w_bay = K_PACK * w_p
    h_bay = K_PACK * h_p
    d_c = (w_p * h_p) ** 0.5
    sigma = l_p / d_c
    alpha = h_p / w_p

    archetype = _classify_archetype(sigma)
    section_class = _classify_section(alpha)

    L_f = max(CN[archetype] * d_c + l_p + CT[archetype] * d_c, REG_SLOPE * b)
    payload_cg_x = 0.33 * L_f
    H_max = h_bay
    W_max = w_bay

    if section_class == "NEAR_CIRCULAR":
        s = STR_ELLIPSE
    else:
        s = STR_BOXY

    # Section-specific dimensions
    # Sections 0: apply multipliers if provided
    w_0 = (mult_0 * w_p) if mult_0 is not None else w_p
    h_0 = (mult_0 * h_p) if mult_0 is not None else h_p
    
    # Sections 1 and 2: always payload-driven
    w_1 = w_bay
    h_1 = h_bay
    w_2 = w_bay
    h_2 = h_bay
    
    # Section 3: payload-driven unless archetype is UNIFORM
    if archetype == "UNIFORM":
        w_3 = w_bay
        h_3 = h_bay
    elif  archetype == "BULGE": # BULGE  apply payload-driven sizing
        #w_3 = (mult_3 * w_bay) if mult_3 is not None else w_p
        w_3 = w_bay 
        h_3 = (mult_3 * h_bay) if mult_3 is not None else h_p
        z_3 = -1*((0.5*(h_2-h_3)))/L_f
    else: #POD  apply uniform sizing
        w_3 = w_bay
        h_3 = h_bay
    
    # Section 4: apply multiplier if provided
    w_4 = (mult_4 * w_p) if mult_4 is not None else w_p
    h_4 = (mult_4 * h_p) if mult_4 is not None else h_p

    return {
        "archetype": archetype,
        "section_class": section_class,
        "sigma": sigma,
        "alpha": alpha,
        "d_c": d_c,
        "H_max": H_max,
        "W_max": W_max,
        "L_f": L_f,
        "payload_cg_x": payload_cg_x,
        "top_strength": s,
        "bot_strength": s,
        "w_0": w_0,
        "h_0": h_0,
        "w_1": w_1,
        "h_1": h_1,
        "w_2": w_2,
        "h_2": h_2,
        "w_3": w_3,
        "h_3": h_3,
        "z_3": z_3,
        "w_4": w_4,
        "h_4": h_4,
    }
