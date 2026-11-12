"""
Initial sizing with the DBF electric-aircraft method (DBF_Sizing.py).

Drop-in replacement for the framework's Sizing.py: it exports the same names
(inputs, g, Mto, Vmax, Endurance, AR, payload_radius, cruise_mach, Wing_Area,
Wing_span, Eng_pow, compute_fuselage_from_payload, compute_cl_cruise, ...), so
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


def compute_fuselage_from_payload(l_p, w_p, h_p, b, m_p=None,
                                  K_PACK=1.15, REG_SLOPE=0.472,
                                  LAMBDA_MIN=5.0, LAMBDA_MAX=14.0,
                                  C_NOSE=1, C_TAIL=1):
    """Compute circular fuselage length and diameter driven by a cuboid payload.

    Follows fuselage_circular_v1_spec.md. Inputs in metres (m).
    Returns dict with keys: L_f, D, lambda_ach, fit_xsec, fit_len, D_req, D_floor, D_ceiling
    """
    # 1. Package the box
    w_bay = K_PACK * w_p
    h_bay = K_PACK * h_p

    # 2. Length from regression
    L_f = REG_SLOPE * b

    # 3. Required diameter to enclose boxed (diagonal)
    D_req = math.sqrt(w_bay ** 2 + h_bay ** 2)

    # 4. Slenderness band on diameter for this length
    D_floor = L_f / LAMBDA_MAX
    D_ceiling = L_f / LAMBDA_MIN

    # 5. Diameter (deterministic — drag drives to the floor, but must enclose payload)
    D = max(D_floor, D_req)

    # 6. Feasibility flags
    fit_xsec = (D_req <= D_ceiling)
    fit_len = (l_p <= L_f - (C_NOSE + C_TAIL) * D)

    # 7. Achieved slenderness
    lambda_ach = L_f / D if D > 0 else float('inf')

    return {
        'L_f': L_f,
        'D': D,
        'lambda_ach': lambda_ach,
        'fit_xsec': fit_xsec,
        'fit_len': fit_len,
        'D_req': D_req,
        'D_floor': D_floor,
        'D_ceiling': D_ceiling,
    }


#Fuselage for the design's wingspan
fuselage = compute_fuselage_from_payload(l_p=inputs['payload_l'], w_p=inputs['payload_w'],
                                         h_p=inputs['payload_h'], b=design.b)

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
    print(f"\nFuselage for b = {design.b:.3f} m: L_f = {fuselage['L_f']:.3f} m, D = {fuselage['D']:.3f} m "
          f"(D_req = {fuselage['D_req']:.3f}, allowed {fuselage['D_floor']:.3f}-{fuselage['D_ceiling']:.3f}), "
          f"slenderness {fuselage['lambda_ach']:.2f}")
    print(f"Payload fits: cross-section {fuselage['fit_xsec']}, length {fuselage['fit_len']}")

    df = pd.DataFrame(feasible_points, columns=['wing_loading', 'Power_loading'])
    df.to_csv("feasible_points.csv", index=False)

    #plotting
    curves = dbf.compute_constraints(assumptions, requirements)
    W_by_S_app = dbf.approach_constraint(assumptions, requirements)
    ax = dbf.plot_constraints(curves, region=region, design_point=(design.W_by_S, design.P_to_W),
                              axis=(0, 1.3 * W_by_S_app, 0, P_to_W_max))
    ax.set_title("Constraint Plot")
    plt.show()
