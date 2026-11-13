"""
Initial sizing with the DBF electric-aircraft method (DBF_Sizing.py).

Drop-in replacement for the framework's Sizing.py: it exports the same names
(inputs, g, Mto, Vmax, Endurance, AR, payload_radius, cruise_mach, Wing_Area,
Wing_span, Eng_pow, compute_cl_cruise, ...), so
`from Sizing import *` keeps working.

Run it on its own (python Sizing.py) to enter the mission and requirements.
The answers are saved to sizing_inputs.json next to this file. When the
framework imports this module it reloads that file instead of asking, so
parallel workers never wait for input. Without the file the defaults below are used.
"""

from operator import index
import joblib
from pyparsing import empty
import math
import numpy as np
import json
import os
import warnings

# from vtkmodules.web.render_window_serializer import linspace
from matplotlib import pyplot as plt
from scipy.interpolate import interp1d
import pandas as pd

import DBF_Sizing as dbf


INPUTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sizing_inputs.json")


#Error checker
def get_input(prompt, default, allow_zero=False):
    while True:
        try:
            value = input(f"{prompt} [{default}] ")
            value = float(value) if value.strip() else float(default)
            if value < 0 or (value == 0 and not allow_zero):
                print(f"Please enter a value greater than {'or equal to ' if allow_zero else ''}0.")
                continue
            return value
        except ValueError:
            print("Invalid. Please enter a valid number.")


def get_choice(prompt, default, options):
    while True:
        value = input(f"{prompt} ({'/'.join(options)}) [{default}] ").strip().lower()
        if not value:
            return default
        if value in options:
            return value
        print(f"Please enter one of: {', '.join(options)}.")


def get_yes_no(prompt, default):
    while True:
        value = input(f"{prompt} [{'y' if default else 'n'}] ").strip().lower()
        if not value:
            return default
        if value in ("y", "n"):
            return value == "y"
        print("Please enter y or n.")


# Mission inputs and performance requirements (framework units: kg, m^3, m/s, km, h, m)
# Defaults follow Integrated Pyhtin/inputs.py: thesis mission without the loiter leg, no landing constraint
inputs = {
    # Mission
    'payload':0.51 , #kg (15.5 N)
    'payload_l': 0.15, # m, placeholder
    'payload_w': 0.1, # m, placeholder
    'payload_h': 0.1, # m, placeholder
    'best_range_distance': 0, #km, flown at the best-range speed (0 to skip)
    'loiter_time': 0.21, #h (0 to skip)
    'loiter_speed': 10.8, #m/s
    'Cruise_distance': 16.1, #km (0 to skip)
    'cruise_speed': 18.0, #m/s
    'turns': 5, #360 deg turns (0 to skip)
    'turn_type': 'bank', #'performance' (full-power sustained turn), 'bank' (set bank angle) or 'radius' (set radius)
    'turn_speed': 10.5, #m/s
    'turn_bank': 4.0, #deg, used when turn_type is 'bank'
    'turn_radius': 0, #m, used when turn_type is 'radius'
    'cruise_ceiling': 120, #m, altitude the mission legs are flown at (0 = sea level, 1.225 kg/m3)
    # Performance requirements
    'takeoff_distance': 1.0, #m, hand launch
    'throw_speed': 7.5, #m/s, wind or hand-throw velocity at take-off
    'max_speed': 18.0, #m/s
    'approach_speed': 9.10, #m/s
    'absolute_ceiling': 120.0, #m
    'rate_of_climb': 300 / 60, #m/s
    'landing': False, #include the Excel landing constraint
    # Design point read off the constraint plot (0 = use the lightest feasible point)
    'design_W_by_S': 51.5, #N/m^2
    'design_P_to_W': 17.0, #W/N
}

# def get_interactive_inputs():
#     """Ask for the mission first, then the performance requirements. Enter keeps the value shown."""
#     global inputs
#     d = inputs
#     print("\n--- Mission ---")
#     inputs = {
#         'payload': get_input("Enter payload (kg):", d['payload']),
#         'payload_l': get_input("Enter payload length l_p (m):", d['payload_l']),
#         'payload_w': get_input("Enter payload width w_p (m):", d['payload_w']),
#         'payload_h': get_input("Enter payload height h_p (m):", d['payload_h']),
#         'best_range_distance': get_input("Enter best-range cruise distance (km, 0 to skip):", d['best_range_distance'], allow_zero=True),
#         'loiter_time': get_input("Enter loiter time (h, 0 to skip):", d['loiter_time'], allow_zero=True),
#         'loiter_speed': get_input("Enter loiter speed (m/s):", d['loiter_speed']),
#         'Cruise_distance': get_input("Enter cruise distance (km, 0 to skip):", d['Cruise_distance'], allow_zero=True),
#         'cruise_speed': get_input("Enter cruise speed (m/s):", d['cruise_speed']),
#         'turns': get_input("Enter number of turns (0 to skip):", d['turns'], allow_zero=True),
#         'turn_type': get_choice("Turn type", d['turn_type'], ('performance', 'bank', 'radius')),
#         'turn_speed': get_input("Enter turn speed (m/s):", d['turn_speed']),
#         'turn_bank': get_input("Enter turn bank angle (deg, for bank turns):", d['turn_bank']),
#         'turn_radius': get_input("Enter turn radius (m, for radius turns):", d['turn_radius']),
#         'cruise_ceiling': get_input("Enter mission altitude (m, 0 = sea level):", d['cruise_ceiling'], allow_zero=True),
#     }
#     print("\n--- Performance requirements ---")
#     inputs.update({
#         'takeoff_distance': get_input("Enter take-off distance (m):", d['takeoff_distance']),
#         'throw_speed': get_input("Enter hand-throw / wind speed at take-off (m/s):", d['throw_speed'], allow_zero=True),
#         'max_speed': get_input("Enter maximum speed (m/s):", d['max_speed']),
#         'approach_speed': get_input("Enter approach speed (m/s):", d['approach_speed']),
#         'absolute_ceiling': get_input("Enter Absolute ceiling (m):", d['absolute_ceiling']),
#         'rate_of_climb': get_input("Enter rate of climb (m/s):", d['rate_of_climb']),
#         'landing': get_yes_no("Include the landing constraint (y/n)?", d['landing']),
#     })
#     print("\n--- Design point (0 = use the lightest feasible point) ---")
#     inputs.update({
#         'design_W_by_S': get_input("Enter design W/S (N/m^2):", d['design_W_by_S'], allow_zero=True),
#         'design_P_to_W': get_input("Enter design P/W (W/N):", d['design_P_to_W'], allow_zero=True),
#     })
#     return inputs


# if __name__ == "__main__":
#     if os.path.exists(INPUTS_FILE):
#         with open(INPUTS_FILE) as f:
#             inputs.update(json.load(f))  # Offer the last saved answers as defaults
#     get_interactive_inputs()
#     with open(INPUTS_FILE, "w") as f:
#         json.dump(inputs, f, indent=4)
#     print(f"Saved to {INPUTS_FILE}")
# elif os.path.exists(INPUTS_FILE):
#     with open(INPUTS_FILE) as f:
#         inputs.update(json.load(f))



#Assumptions (airplane, propulsion and battery)
assumptions = dbf.Assumptions(
    g = 9.81, #m/s2
    Cdo = 0.035, #Zero-lift drag coefficient
    e = 0.868, #Oswald efficiency factor
    np = 0.735, #Propeller efficiency
    nm = 0.768, #Motor efficiency
    AR = 7.3, #Aspect ratio
    Cl_max = 1.6, #max lift coefficient
    e_battery = dbf.specific_energy(18.5, 5.137, 0.506, usable=0.9), #J/kg, Thunderpower 5S 5000 mAh
    We_to_Wto = 0.6, #Empty weight to take-off weight ratio
)

#Search window for feasible points: typical DBF initial-sizing ranges
W_by_S_min = 40 #N/m^2 (0.8 lb/ft^2)
W_by_S_max = 85 #N/m^2 (1.8 lb/ft^2); the approach constraint may cap it lower
P_to_W_min = 6 #W/N (12 W/lb)
P_to_W_max = 20 #W/N (40 W/lb)

#Requirements not asked for keep the DBF workbook values (see dbf.Requirements)
requirements = dbf.Requirements(
    Xto = inputs['takeoff_distance'],
    Vthrow = inputs['throw_speed'],
    V_ms = inputs['max_speed'],
    Vapp = inputs['approach_speed'],
    Cl_app = assumptions.Cl_max,
    h_ceil = inputs['absolute_ceiling'],
    ROC = inputs['rate_of_climb'],
    landing = inputs['landing'],
)

#Mission legs in SI units; take-off is always flown, the others are skipped when 0
leg_altitude = {"h": inputs['cruise_ceiling']} if inputs['cruise_ceiling'] > 0 else {}
mission = [("takeoff", {})]
if inputs['best_range_distance'] > 0:
    mission.append(("best_cruise", {"X": inputs['best_range_distance'] * 1000, **leg_altitude}))
if inputs['loiter_time'] > 0:
    mission.append(("loiter", {"T": inputs['loiter_time'] * 3600, "V": inputs['loiter_speed'], **leg_altitude}))
if inputs['Cruise_distance'] > 0:
    mission.append(("cruise", {"X": inputs['Cruise_distance'] * 1000, "V": inputs['cruise_speed'], **leg_altitude}))
if inputs['turns'] > 0:
    turn_leg = {"turns": inputs['turns'], "V": inputs['turn_speed'], **leg_altitude}
    if inputs['turn_type'] == 'performance':
        mission.append(("turn", turn_leg))
    elif inputs['turn_type'] == 'bank':
        mission.append(("turn_bank", {**turn_leg, "bank": inputs['turn_bank']}))
    elif inputs['turn_type'] == 'radius':
        mission.append(("turn_radius", {**turn_leg, "radius": inputs['turn_radius']}))
    else:
        raise ValueError(f"turn_type must be 'performance', 'bank' or 'radius', not {inputs['turn_type']!r}")


#Size the airplane at every feasible (W/S, P/W) point
region = dbf.feasible_region(assumptions, requirements, mission, inputs['payload'], P_to_W_max,
                             W_by_S_min=W_by_S_min, W_by_S_max=W_by_S_max, P_to_W_min=P_to_W_min)

#Design: the chosen point if one is given, otherwise the lightest feasible airplane
if inputs['design_W_by_S'] > 0 and inputs['design_P_to_W'] > 0:
    design = dbf.size_point(assumptions, mission, inputs['payload'], inputs['design_W_by_S'], inputs['design_P_to_W'])
    for problem in dbf.check_point(assumptions, requirements, design.W_by_S, design.P_to_W):
        warnings.warn(f"design point: {problem}")
else:
    design = region.lightest


#Names the framework imports (from Sizing import *)
g = assumptions.g
AR = assumptions.AR
Cdo = assumptions.Cdo
K = assumptions.k_lift #Induced factor
LDmax = assumptions.L_by_D_max

Mto = design.Wto #Maximum takeoff weight, N
Vmax = requirements.V_ms
rho_sl = dbf.RHO_SL #kg/m3
Vs = float(dbf.stall_velocity(design.W_by_S, rho_sl, assumptions.Cl_max)) #Stall speed of the design, m/s
Vto = dbf.takeoff_velocity(Vs)
Endurance = design.endurance / 3600 #h, from the mission legs

inputs['Range'] = design.range / 1000 #km, from the mission legs
inputs['Stall_Speed'] = Vs
inputs['cl_max'] = assumptions.Cl_max
inputs['service_ceiling'] = inputs['absolute_ceiling']

#Payload volume from the cuboid dimensions; payload_radius is kept for branches that still use it
inputs['payload_vol'] = inputs['payload_l'] * inputs['payload_w'] * inputs['payload_h'] #m3
payload_radius = 2*np.cbrt((3*inputs['payload_vol'])/(4*np.pi)) #This is diameter rather


#Fuselage and tail buildup assumptions (red in the workflow sketch)
fuselage_assumptions = {
    'K_PACK': 1.15, #payload packing factor (bay = 1.15 x payload box)
    'C_NOSE': 1.25, #nose length / bay diameter
    'K_c': 1.0, #Sadraey tail-arm correction (1.0-1.4); 1.0 matches APPA
    'AR_h': 4.0, #horizontal tail aspect ratio (b_h^2/S_h)
    'TR_h': 0.5, #horizontal tail taper ratio
    'AR_v': 1.5, #vertical tail aspect ratio (h_v^2/S_v)
    'TR_v': 0.6, #vertical tail taper ratio
    'L_by_b_max': 0.87, #longest fuselage in the DBF database, L_f/b
    'taper_angle_max': 15.0, #deg, aft-body half-angle before the flow separates
    'D_aft_min': 0.02, #m, thinnest boom (APPA used a 19.8 mm tube)
}

#Tail leading-edge sweep (H, V) per tail type, deg; Master_Controller_2 builds the tails with these
TAIL_SWEEP = {
    "Conventional": (11.8, 0.0), "T-Tail": (11.8, 0.0), "Cruciform": (11.8, 0.0),
    "Y-Tail": (21.8, 21.8), "Inverted_Y-Tail": (21.8, 21.8), "Dual-Tail": (15.0, 21.8),
    "V-Tail": (21.8, None), "Inverted_V-Tail": (21.8, None), #V-tails have no separate fin
}


def wing_mac(b, S, taper):
    """Root chord, mean aerodynamic chord and its spanwise station of a trapezoidal wing (b is the full span)."""
    c_r = 2 * S / (b * (1 + taper))
    c_bar = (2 / 3) * c_r * (1 + taper + taper**2) / (1 + taper)
    y_bar = (b / 6) * (1 + 2 * taper) / (1 + taper)
    return c_r, c_bar, y_bar


def _surface_le(x_ac, span, S_surf, taper, sweep_deg, half=False):
    """Root leading edge that puts a trapezoidal surface's quarter-MAC at x_ac.

    span is the full (mirrored) span, or the panel height when half=True (single fin).
    """
    b_eff = 2 * span if half else span
    c_r, c_bar, y_bar = wing_mac(b_eff, 2 * S_surf if half else S_surf, taper)
    x_le = x_ac - 0.25 * c_bar - y_bar * math.tan(math.radians(sweep_deg))
    return x_le, c_r, c_bar


def fuselage_tail_buildup(l_p, w_p, h_p, b, S, taper, sweep, V_h, V_v,
                          r_aft=1.0, f_taper=0.9, r_nose=0.4, tail_type="Conventional",
                          K_c=None, assumptions=None):
    """Single fuselage body and tail sized from the payload, the wing and the tail volume coefficients.

    Body stations (OpenVSP XSecs 0-4): nose tip -> bay start -> bay end -> taper end -> tail end.
      Bay diameter D encloses the packed payload; the body tapers to D_aft = r_aft*D over
      f_taper of the length behind the bay (r_aft 1 = tube, small = boom).
    Wing: quarter-MAC over the payload-bay centre (the CG sits there).
    Tail arm: Sadraey optimum l_opt = K_c*sqrt(4*c*S*V_h/(pi*D_f)), D_f = mean body diameter over the arm
      (iterated, since the arm sets how much of the thin aft body it spans).
    Tails: S_h = V_h*S*c/l_opt, S_v = V_v*S*b/l_opt; the body ends at the last tail root trailing edge.
    Lengths in m, areas in m^2, angles in deg.
    """
    p = dict(fuselage_assumptions, **(assumptions or {}))
    K_c = p['K_c'] if K_c is None else K_c
    H_sweep, V_sweep = TAIL_SWEEP.get(tail_type, (0.0, 0.0))

    #1. Payload bay and nose
    D = math.sqrt((p['K_PACK'] * w_p) ** 2 + (p['K_PACK'] * h_p) ** 2)
    D_aft = r_aft * D
    l_nose = p['C_NOSE'] * D
    x_bay_end = l_nose + p['K_PACK'] * l_p

    #2. Wing: MAC quarter-chord over the bay centre
    c_r, c_bar, y_bar = wing_mac(b, S, taper)
    x_ac = l_nose + p['K_PACK'] * l_p / 2
    x_wing_LE = x_ac - 0.25 * c_bar - y_bar * math.tan(math.radians(sweep))

    def tails(l_t):
        S_h = V_h * S * c_bar / l_t
        b_h = math.sqrt(p['AR_h'] * S_h)
        x_h_LE, c_h_root, c_h_bar = _surface_le(x_ac + l_t, b_h, S_h, p['TR_h'], H_sweep)
        ends = [x_h_LE + c_h_root]
        S_v = V_v * S * b / l_t
        h_v = math.sqrt(p['AR_v'] * S_v)
        x_v_LE, c_v_root, _ = _surface_le(x_ac + l_t, h_v, S_v, p['TR_v'], V_sweep or 0.0, half=True)
        if V_sweep is not None:
            ends.append(x_v_LE + c_v_root)
        return dict(S_h=S_h, b_h=b_h, c_h_root=c_h_root, c_h_tip=p['TR_h'] * c_h_root, c_h_bar=c_h_bar,
                    x_h_LE=x_h_LE, S_v=S_v, h_v=h_v, c_v_root=c_v_root, c_v_tip=p['TR_v'] * c_v_root,
                    x_v_LE=x_v_LE, L_f=max(ends))

    def stations(L_f):
        x_taper_end = x_bay_end + f_taper * (L_f - x_bay_end)
        return [0.0, l_nose, x_bay_end, x_taper_end, L_f], [r_nose * D, D, D, D_aft, D_aft]

    #3. Optimum tail arm with the mean body diameter over the arm (damped fixed-point iteration)
    l_t = K_c * math.sqrt(4 * c_bar * S * V_h / (math.pi * D))
    for _ in range(200):
        xs, ds = stations(tails(l_t)['L_f'])
        D_f = float(np.mean(np.interp(np.linspace(x_ac, x_ac + l_t, 200), xs, ds)))
        l_new = K_c * math.sqrt(4 * c_bar * S * V_h / (math.pi * D_f))
        if abs(l_new - l_t) < 1e-6:
            l_t = l_new
            break
        l_t = 0.5 * (l_t + l_new)

    #4-5. Tails and body stations for the converged arm
    t = tails(l_t)
    L_f = t['L_f']
    xs, ds = stations(L_f)
    taper_len = xs[3] - xs[2]
    if D_aft >= D:
        half_angle = 0.0
    elif taper_len > 0:
        half_angle = math.degrees(math.atan((D - D_aft) / 2 / taper_len))
    else:
        half_angle = 90.0

    return {
        'D': D, 'D_aft': D_aft, 'D_f': D_f, 'L_f': L_f, 'L_f_by_b': L_f / b,
        'l_t': l_t, 'l_t_by_c': l_t / c_bar, 'x_ac': x_ac,
        'wing_root': c_r, 'wing_tip': taper * c_r, 'c_bar': c_bar, 'x_wing_LE': x_wing_LE,
        'x_tail_ac': x_ac + l_t, 'D_at_tail': float(np.interp(x_ac + l_t, xs, ds)),
        'x_bay_end': x_bay_end, 'taper_half_angle': half_angle,
        'XLocPercent': [x / L_f for x in xs], 'diameters': ds,
        **{k: v for k, v in t.items() if k != 'L_f'},
    }


def check_fuselage(geo, b, assumptions=None):
    """Reasons the fuselage/tail buildup is infeasible (empty list if it is fine)."""
    p = dict(fuselage_assumptions, **(assumptions or {}))
    problems = []
    if geo['L_f'] / b > p['L_by_b_max']:
        problems.append(f"L_f/b = {geo['L_f'] / b:.2f} > {p['L_by_b_max']}")
    if geo['taper_half_angle'] > p['taper_angle_max']:
        problems.append(f"aft taper {geo['taper_half_angle']:.1f} deg > {p['taper_angle_max']} deg")
    if geo['D_aft'] < p['D_aft_min'] - 1e-9:
        problems.append(f"D_aft = {geo['D_aft']:.3f} m < {p['D_aft_min']} m")
    if geo['x_wing_LE'] < 0:
        problems.append("wing leading edge ahead of the nose")
    if geo['x_h_LE'] < geo['x_bay_end']:
        problems.append("tail overlaps the payload bay")
    return problems


def payload_bay_diameter(l_p=None, w_p=None, h_p=None, assumptions=None):
    """Bay diameter D that encloses the packed payload box."""
    p = dict(fuselage_assumptions, **(assumptions or {}))
    w_p = inputs['payload_w'] if w_p is None else w_p
    h_p = inputs['payload_h'] if h_p is None else h_p
    return math.sqrt((p['K_PACK'] * w_p) ** 2 + (p['K_PACK'] * h_p) ** 2)


def design_geometry(row):
    """Fuselage/tail buildup for one optimizer candidate (a population row); S = b^2/AR as in the framework."""
    b = float(row['Wing_Span'])
    return fuselage_tail_buildup(
        l_p=inputs['payload_l'], w_p=inputs['payload_w'], h_p=inputs['payload_h'],
        b=b, S=b**2 / AR, taper=float(row['Taper']), sweep=float(row['Sweep']),
        V_h=float(row['Vol_Hor']), V_v=float(row['Vol_Vert']),
        r_aft=float(row['r_aft']), f_taper=float(row['f_taper']), r_nose=float(row['r_nose']),
        tail_type=row['Tail_Type'])


#Fuselage and tail for the sizing design point (straight tube, V_h 0.45, V_v 0.03, untapered wing), for reference
fuselage = fuselage_tail_buildup(l_p=inputs['payload_l'], w_p=inputs['payload_w'], h_p=inputs['payload_h'],
                                 b=design.b, S=design.S, taper=1.0, sweep=0.0, V_h=0.45, V_v=0.03)

rho_c = dbf.density(inputs['cruise_ceiling']) if inputs['cruise_ceiling'] > 0 else rho_sl
rho_ac = dbf.density(inputs['absolute_ceiling'])

#cruise speed to Mach number conversion
c = dbf.speed_of_sound(inputs['cruise_ceiling']) #speed of sound at cruise
cruise_mach = inputs['cruise_speed']/c #Mach number at cruise

#Design-variable bounds from the feasible region
feasible_points = np.column_stack((region.W_by_S, region.P_to_W)) #W/S (N/m^2), P/W (W/N)
Wing_Area = list(region.bounds('S')) #m^2
Wing_span = np.sqrt(AR*np.array(Wing_Area)) #Design Variable
Eng_pow = list(region.bounds('Power')) #W, battery power


def compute_cl_cruise(wing_area=None):
    """Compute CL required for steady level cruise.

    If `wing_area` is None, use the design's wing area (design.S), which goes
    with Mto. (The framework's version used Wing_Area[0], the smallest wing in
    the feasible region, which belongs to a different airplane here.)
    """
    S = float(design.S) if wing_area is None else float(wing_area)

    W = float(Mto)  # Mto already in Newtons in this module
    rho = float(rho_c)
    V = float(inputs.get('cruise_speed', 0.0))
    if S <= 0 or V <= 0 or rho <= 0:
        raise ValueError("Invalid parameters for CL cruise calculation")
    cl_cruise = (2.0 * W) / (rho * V**2 * S)
    return cl_cruise


if __name__ == "__main__":
    print(f"\nrho_c = {rho_c}")
    print(f"rho_ac = {rho_ac}")
    lightest = region.lightest
    if design is lightest:
        print(f"\nLightest feasible design:\n{design}")
    else:
        print(f"\nChosen design point:\n{design}")
        print(f"\nLightest feasible point: W/S = {lightest.W_by_S:.3f} N/m^2, P/W = {lightest.P_to_W:.3f} W/N, "
              f"Wto = {lightest.Wto:.4f} N")
    print(f"\nTake-off weight range: {region.bounds('Wto')} N")
    print(f"Wing_Area: {Wing_Area}")
    print(f"Wing_span: {Wing_span}")
    print(f"Eng_pow: {Eng_pow}")
    print(f"Endurance: {Endurance:.3f} h, Range: {inputs['Range']:.3f} km, cruise Mach: {cruise_mach:.4f}")
    print(f"CL at cruise: {compute_cl_cruise():.4f}")
    print(f"\nFuselage for b = {design.b:.3f} m (tube, V_h 0.45, V_v 0.03): L_f = {fuselage['L_f']:.3f} m "
          f"(L_f/b {fuselage['L_f_by_b']:.2f}), D = {fuselage['D']:.3f} m, tail arm {fuselage['l_t']:.3f} m "
          f"(l_t/c {fuselage['l_t_by_c']:.2f}), S_h {fuselage['S_h']:.4f} m^2, S_v {fuselage['S_v']:.4f} m^2")
    print(f"Fuselage problems: {check_fuselage(fuselage, design.b) or 'none'}")

    df = pd.DataFrame(feasible_points, columns=['wing_loading', 'Power_loading'])
    df.to_csv("feasible_points.csv", index=False)

    #plotting
    curves = dbf.compute_constraints(assumptions, requirements)
    W_by_S_app = dbf.approach_constraint(assumptions, requirements)
    ax = dbf.plot_constraints(curves, region=region, design_point=(design.W_by_S, design.P_to_W),
                              axis=(0, 1.3 * W_by_S_app, 0, P_to_W_max))
    ax.set_title("Constraint Plot")
    plt.show()
