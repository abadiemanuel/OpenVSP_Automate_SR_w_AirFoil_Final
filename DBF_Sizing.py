"""DBF electric-aircraft sizing engine, in SI units.

One-file version of the `sizing` package in Integrated Pyhtin (thesis Models 1-40
plus the Excel constraint and weight-fraction sheets), written for Sizing.py.

Units throughout: m, s, kg, N, W, J.
    Wing loading  W/S in N/m^2
    Power loading P/W in W/N (battery power per newton of take-off weight)
    Battery specific energy in J/kg

Nothing runs at import. matplotlib is imported only when a plot is drawn.

Sections:
    1. Atmosphere            (Model 2)
    2. Aircraft aerodynamics (Models 1, 3-7, 9)
    3. Battery               (Model 20)
    4. Assumptions and requirements
    5. Constraint analysis   (P/W against W/S)
    6. Mission legs          (Models 21-33, 36-40, Excel bank and radius turns)
    7. Sizing at a point and over the feasible region
    8. Plot
"""

import itertools
import math
import warnings
from dataclasses import dataclass, field

import numpy


# =============================================================================
# 1. Atmosphere (Model 2)
# =============================================================================
RHO_SL = 1.225  # Sea-level density used throughout the Excel sheets, kg/m^3
GAMMA_AIR = 1.4  # Ratio of specific heats, dry air
R_AIR = 287.05  # Gas constant for air, J/(kg*K)


def _temperature_pressure(h):
    # NASA Earth atmosphere model: temperature in C, pressure in kPa, h in m
    # Reference: https://www.grc.nasa.gov/WWW/K-12/rocket/atmos.html
    if h <= 11000:
        T = 15.04 - 0.00649 * h
        P = 101.29 * ((T + 273.1) / 288.08) ** 5.256
    elif h <= 25000:
        T = -56.46
        P = 22.65 * math.exp(1.73 - 0.000157 * h)
    else:
        T = -131.21 + 0.00299 * h
        P = 2.488 * ((T + 273.1) / 216.6) ** -11.388
    return T, P


def density(h):
    """Air density in kg/m^3 at altitude h in m.

    The troposphere uses the Excel sheets' 273.11 K offset, so results match them.
    """
    T, P = _temperature_pressure(h)
    if h <= 11000:
        T += 0.01
    return P / (0.2869 * (T + 273.1))


def speed_of_sound(h):
    """Speed of sound in m/s at altitude h in m."""
    T, _ = _temperature_pressure(h)
    return math.sqrt(GAMMA_AIR * R_AIR * (T + 273.1))


def _rho(h):
    # h = None means the sea-level 1.225 kg/m^3 that the Excel sheets use directly
    return RHO_SL if h is None else density(h)


# =============================================================================
# 2. Aircraft aerodynamics (Models 1, 3-7, 9)
# =============================================================================
def aspect_ratio(b, S):
    """Model 1, aspect ratio."""
    return b**2 / S


def k_lift(e, AR):
    """Model 3, drag-due-to-lift factor k = 1/(pi*e*AR)."""
    return 1 / (math.pi * e * AR)


def L_by_D_max(e, AR, Cdo):
    """Model 4, maximum lift-to-drag ratio."""
    return 0.5 * math.sqrt((math.pi * e * AR) / Cdo)


def stall_velocity(W_by_S, rho, Cl_max):
    """Model 5, stall velocity in m/s."""
    return numpy.sqrt((2 * W_by_S) / (rho * Cl_max))


def takeoff_velocity(Vs):
    """Model 6, take-off velocity = 1.2 * stall velocity."""
    return 1.2 * Vs


def takeoff_distance(Vto, g, nm, np, P_to_W):
    """Model 7, take-off distance in m (thesis form; Excel uses V^3/3)."""
    return ((0.7 * Vto) ** 3) / (g * nm * np * P_to_W)


def dynamic_pressure(rho, V):
    """Model 9, dynamic pressure in N/m^2."""
    return 0.5 * rho * V**2


def L_by_D_at_speed(W_by_S, Cdo, q, k):
    """Model 24, lift-to-drag ratio in level flight at dynamic pressure q."""
    return W_by_S / (Cdo * q + (k * W_by_S**2 / q))


# =============================================================================
# 3. Battery (Model 20)
# =============================================================================
def specific_energy(volt, capacity_Ah, mass_N, usable=1.0):
    """Model 20, battery specific energy in J/kg.

    usable is the fraction of capacity that can be drawn (Excel uses 0.9).
    """
    return volt * capacity_Ah * 3600 * usable / (mass_N)


# =============================================================================
# 4. Assumptions and requirements
# =============================================================================
@dataclass
class Assumptions:
    """Airplane, propulsion and battery assumptions."""
    g: float = 9.81  # Acceleration due to gravity, m/s^2
    Cdo: float = 0.035  # Zero-lift drag coefficient
    e: float = 0.868  # Span efficiency / Oswald efficiency
    np: float = 0.735  # Propeller efficiency
    nm: float = 0.768  # Motor efficiency
    AR: float = 7.3  # Aspect ratio
    Cl_max: float = 1.6  # Maximum lift coefficient
    e_battery: float = specific_energy(18.5, 5, 0.506, usable=0.9)  # J/kg, Thunderpower 5S 5000 mAh
    We_to_Wto: float = 0.6  # Empty weight to take-off weight ratio

    @property
    def k_lift(self):
        return k_lift(self.e, self.AR)

    @property
    def L_by_D_max(self):
        return L_by_D_max(self.e, self.AR, self.Cdo)


@dataclass
class Requirements:
    """Performance requirements for the constraint diagram.

    Altitudes are in m. An altitude of None means sea-level 1.225 kg/m^3, as the
    Excel sheets use. The defaults reproduce Constraint_sizing_electric_2017.xlsx.
    """
    # Take-off (hand launch)
    h_to: float | None = 0
    Xto: float = 1  # Take-off distance, m
    Vthrow: float = 7.5  # Wind or hand-throw velocity at take-off, m/s
    # Maximum speed
    h_ms: float | None = 120
    V_ms: float = 18  # m/s
    # Approach
    h_app: float | None = 120
    Vapp: float = 9.1  # m/s
    Cl_app: float = 1.4
    # Ceiling
    h_ceil: float = 120
    ceiling_model: str = "excel"  # "excel" or "thesis"
    # Rate of climb
    h_roc: float | None = 120  # 1300 ft
    h_roc_velocity: float | None = None  # Density for the climb speed: Excel uses sea level
    ROC: float = 300 / 60  # m/s
    # Turns
    h_tu: float | None = None  # Excel's turn altitude is 100 m, but its q uses sea-level density
    V_tu: float = 10.5  # m/s
    n_tu: float = 1  # Load factor (60 deg bank)
    # Landing (Excel only)
    landing: bool = True
    h_land: float | None = 100
    Cl_land: float = 1.0
    X_land: float = 10  # Landing distance, m
    # W/S grid for the constraint curves, N/m^2
    W_by_S: numpy.ndarray = field(default_factory=lambda: numpy.arange(0, 250.5, 0.5))


# =============================================================================
# 5. Constraint analysis: P/W required (W/N) against W/S (N/m^2)
# =============================================================================
def takeoff_constraint(a, r, W_by_S):
    """Take-off within Xto metres, helped by a throw/wind velocity Vthrow."""
    Vto = takeoff_velocity(stall_velocity(W_by_S, _rho(r.h_to), a.Cl_max)) - r.Vthrow
    return Vto**3 / (2 * a.g * a.nm * a.np * r.Xto)


def max_speed_constraint(a, r, W_by_S):
    """Level flight at V_ms."""
    q_ms = dynamic_pressure(_rho(r.h_ms), r.V_ms)
    T_by_W = q_ms * a.Cdo / W_by_S + a.k_lift * W_by_S / q_ms
    return r.V_ms * T_by_W / (a.nm * a.np)


def approach_constraint(a, r):
    """Approach at Vapp: the highest W/S allowed (a vertical line)."""
    return 0.5 * _rho(r.h_app) * r.Vapp**2 * r.Cl_app


def ceiling_constraint(a, r, W_by_S):
    """Flight at the ceiling altitude at the minimum-power lift coefficient.

    ceiling_model "excel":  P/W = V / (np*nm*(L/D)max*sqrt(rho))
    ceiling_model "thesis": P/W = V / (0.886*np*nm*g), as in the thesis MATLAB
    """
    rho = _rho(r.h_ceil)
    Cl = numpy.sqrt(3 * a.Cdo / a.k_lift)
    Vceil = numpy.sqrt(2 * W_by_S / (rho * Cl))
    if r.ceiling_model == "excel":
        return Vceil / (a.np * a.nm * a.L_by_D_max * numpy.sqrt(rho))
    if r.ceiling_model == "thesis":
        return Vceil / (0.886 * a.np * a.nm * a.g)
    raise ValueError(f"ceiling_model must be 'excel' or 'thesis', not {r.ceiling_model!r}")


def rate_of_climb_constraint(a, r, W_by_S):
    """Climb at ROC m/s at the minimum-power lift coefficient."""
    rho = _rho(r.h_roc)
    Cl = numpy.sqrt(3 * a.Cdo / a.k_lift)
    Vroc = numpy.sqrt(2 * W_by_S / (_rho(r.h_roc_velocity) * Cl))
    return (1 / (a.nm * a.np)) * (r.ROC + Vroc / (0.866 * a.L_by_D_max * numpy.sqrt(rho)))


def turns_constraint(a, r, W_by_S):
    """Sustained level turn at V_tu with load factor n_tu."""
    q_tu = dynamic_pressure(_rho(r.h_tu), r.V_tu)
    T_by_W = q_tu * a.Cdo / W_by_S + r.n_tu**2 * a.k_lift * W_by_S / q_tu
    return r.V_tu * T_by_W / (a.nm * a.np)


def landing_constraint(a, r, W_by_S):
    """Landing within X_land metres (Excel 'Landing' sheet)."""
    V = 1.2 * numpy.sqrt(2 * W_by_S / (_rho(r.h_land) * r.Cl_land))
    return 0.5 * V**3 / (r.X_land * a.np * a.nm * a.g)


def power_constraints(r):
    """The P/W constraint functions in use, as {name: function}."""
    constraints = {
        "Take off": takeoff_constraint,
        "Max Speed": max_speed_constraint,
        "Ceiling": ceiling_constraint,
        "Rate of Climb": rate_of_climb_constraint,
        "Turns": turns_constraint,
    }
    if r.landing:
        constraints["Landing"] = landing_constraint
    return constraints


def required_power(a, r, W_by_S):
    """Highest P/W any constraint needs at each W/S."""
    W_by_S = numpy.asarray(W_by_S, dtype=float)
    with numpy.errstate(divide="ignore", invalid="ignore"):
        return numpy.max([f(a, r, W_by_S) for f in power_constraints(r).values()], axis=0)


def check_point(a, r, W_by_S, P_to_W):
    """Constraints a (W/S, P/W) point violates, as a list of messages (empty if it meets them all)."""
    problems = []
    W_by_S_app = approach_constraint(a, r)
    if W_by_S > W_by_S_app:
        problems.append(f"W/S = {W_by_S:g} is above the approach limit of {W_by_S_app:.2f} N/m^2")
    for name, f in power_constraints(r).items():
        P_req = float(f(a, r, numpy.float64(W_by_S)))
        if P_to_W < P_req:
            problems.append(f"P/W = {P_to_W:g} is below the {name} requirement of {P_req:.2f} W/N")
    return problems


def compute_constraints(a, r):
    """All constraint curves over r.W_by_S as {name: (W/S array, P/W array)}."""
    with numpy.errstate(divide="ignore", invalid="ignore"):  # W/S = 0 gives inf
        curves = {name: (r.W_by_S, f(a, r, r.W_by_S)) for name, f in power_constraints(r).items()}
    P_to_W_app = numpy.arange(0, 250.5, 0.5)
    curves["Approach Velocity"] = (numpy.full(len(P_to_W_app), approach_constraint(a, r)), P_to_W_app)
    return curves


def polyxpoly(x1, y1, x2, y2):
    """Intersection points of two polylines (stand-in for MATLAB's polyxpoly)."""
    x1, y1, x2, y2 = (numpy.asarray(v, dtype=float).ravel() for v in (x1, y1, x2, y2))
    p = numpy.stack([x1[:-1], y1[:-1]], 1)[:, None, :]
    r = numpy.stack([numpy.diff(x1), numpy.diff(y1)], 1)[:, None, :]
    q = numpy.stack([x2[:-1], y2[:-1]], 1)[None, :, :]
    s = numpy.stack([numpy.diff(x2), numpy.diff(y2)], 1)[None, :, :]

    def cross(u, v):
        return u[..., 0] * v[..., 1] - u[..., 1] * v[..., 0]

    with numpy.errstate(divide="ignore", invalid="ignore"):
        denom = cross(r, s)
        qp = q - p
        t = cross(qp, s) / denom
        u = cross(qp, r) / denom
        hit = (denom != 0) & (t >= 0) & (t <= 1) & (u >= 0) & (u <= 1)
    i, j = numpy.nonzero(hit)
    pts = p[i, 0] + t[i, j][:, None] * r[i, 0]
    pts = numpy.unique(numpy.round(pts, 10), axis=0)
    return pts[:, 0], pts[:, 1]


def intersections(curves):
    """Every crossing between two constraint curves, as (name 1, name 2, W/S, P/W).

    Crossings at W/S = 0, where every curve starts, are left out.
    """
    points = []
    for (name1, (x1, y1)), (name2, (x2, y2)) in itertools.combinations(curves.items(), 2):
        for x, y in zip(*polyxpoly(x1, y1, x2, y2)):
            if x > 0:
                points.append((name1, name2, x, y))
    return points


# =============================================================================
# 6. Mission legs
#
# Each leg takes the assumptions, the air density and the point (W/S, P/W),
# plus its own parameters in SI units, and returns (Wb/Wto, time s, distance m).
# =============================================================================
def takeoff(a, rho, W_by_S, P_to_W):
    """Model 36 (Models 21-22), take-off to 1.2 * stall velocity."""
    Vto = takeoff_velocity(stall_velocity(W_by_S, rho, a.Cl_max))
    Tto = (0.5 * Vto**2) / (a.g * P_to_W * a.np * a.nm)
    return Tto * P_to_W * a.g / a.e_battery, Tto, 0.0


def _level_leg(a, rho, W_by_S, X, V):
    # Battery fraction to fly X metres level at V m/s (Models 24-25, 29)
    L_by_D = L_by_D_at_speed(W_by_S, a.Cdo, dynamic_pressure(rho, V), a.k_lift)
    return X * a.g / (a.nm * a.np * L_by_D * a.e_battery), X / V, X


def cruise(a, rho, W_by_S, P_to_W, X, V):
    """Model 37 (Models 23-25), cruise of X metres at a chosen velocity V."""
    return _level_leg(a, rho, W_by_S, X, V)


def best_cruise(a, rho, W_by_S, P_to_W, X):
    """Model 40 (Model 33), cruise of X metres at the best-range (maximum L/D) velocity."""
    Vbc = numpy.sqrt((2 * W_by_S) / (rho * numpy.sqrt(a.Cdo / a.k_lift)))
    return _level_leg(a, rho, W_by_S, X, Vbc)


def loiter(a, rho, W_by_S, P_to_W, T, V):
    """Model 38 (Models 27-29), loiter for T seconds at V m/s."""
    return _level_leg(a, rho, W_by_S, T * V, V)


def _turns_leg(a, P_to_W, V, n, turns):
    # Model 32: full-power turns; radius V^2/(g*sqrt(n^2-1)) gives the time
    if not n > 1:
        raise ValueError(f"turn not possible: load factor n = {n:.3f} must be above 1")
    root = math.sqrt(n**2 - 1)
    Wb = (2 * math.pi * P_to_W * V * turns) / (a.e_battery * root)
    time = 2 * math.pi * V * turns / (a.g * root)
    return Wb, time, V * time


def turn(a, rho, W_by_S, P_to_W, turns, V=None):
    """Model 39 (Models 30-32), full-power sustained ("performance") turns.

    V=None flies them at 1.2 * stall velocity, as the thesis MATLAB does.
    Give V (m/s) to fly them at a set speed, as the Excel sheet does (18 m/s).
    """
    Vt = 1.2 * stall_velocity(W_by_S, rho, a.Cl_max) if V is None else V
    q_t = dynamic_pressure(rho, Vt)
    arg = q_t / (a.k_lift * W_by_S) * (P_to_W * a.nm * a.np / Vt - q_t * a.Cdo / W_by_S)
    n = math.sqrt(arg) if arg >= 0 else math.nan  # nan: not enough power for level flight
    return _turns_leg(a, P_to_W, Vt, n, turns)


def turn_bank(a, rho, W_by_S, P_to_W, turns, bank, V):
    """Turns at a set bank angle (degrees) and speed (Excel 'Turns (Bank)')."""
    n = 1 / math.cos(math.radians(bank))
    _check_turn_lift(a, rho, W_by_S, n, V, "turn_bank")
    return _turns_leg(a, P_to_W, V, n, turns)


def turn_radius(a, rho, W_by_S, P_to_W, turns, radius, V):
    """Turns of a set radius (m) and speed (Excel 'Turns (Radius)')."""
    n = math.sqrt(V**4 / (radius**2 * a.g**2) + 1)
    _check_turn_lift(a, rho, W_by_S, n, V, "turn_radius")
    return _turns_leg(a, P_to_W, V, n, turns)


def _check_turn_lift(a, rho, W_by_S, n, V, name):
    # The Excel sheets turn the CL cell red in this case
    CL = 2 * W_by_S * n / (rho * V**2)
    if CL > a.Cl_max:
        warnings.warn(f"{name}: needs CL = {CL:.2f}, above Cl_max = {a.Cl_max}; the turn is not possible")


LEGS = {
    "takeoff": takeoff,
    "best_cruise": best_cruise,
    "cruise": cruise,
    "loiter": loiter,
    "turn": turn,
    "turn_bank": turn_bank,
    "turn_radius": turn_radius,
}


# =============================================================================
# 7. Sizing at a point and over the feasible region
# =============================================================================
@dataclass
class Leg:
    name: str
    Wb: float  # Battery weight fraction Wb/Wto
    time: float  # s
    distance: float  # m


@dataclass
class SizingResult:
    W_by_S: float  # N/m^2
    P_to_W: float  # W/N
    legs: list  # Leg, in mission order
    Wb: float  # Total battery weight fraction
    Wto: float  # Take-off weight, N
    mass: float  # Take-off mass, kg
    W_empty: float  # Empty weight, N
    W_battery: float  # Battery weight, N
    S: float  # Wing area, m^2
    b: float  # Wing span, m
    Power: float  # Battery power, W
    endurance: float  # Total mission time, s
    range: float  # Total distance flown, m

    def __str__(self):
        lines = [f"Point W/S = {self.W_by_S:.3f} N/m^2, P/W = {self.P_to_W:.3f} W/N",
                 "Leg            Wb/Wto     time (min)  distance (km)"]
        lines += [f"  {leg.name:<12} {leg.Wb:.5f}  {leg.time / 60:10.2f}  {leg.distance / 1000:12.3f}"
                  for leg in self.legs]
        lines += [
            f"  {'total':<12} {self.Wb:.5f}  {self.endurance / 60:10.2f}  {self.range / 1000:12.3f}",
            f"Take-off weight  {self.Wto:10.4f} N ({self.mass:.4f} kg)",
            f"Empty weight     {self.W_empty:10.4f} N",
            f"Battery weight   {self.W_battery:10.4f} N",
            f"Wing area        {self.S:10.4f} m^2",
            f"Wing span        {self.b:10.4f} m",
            f"Power            {self.Power:10.4f} W",
        ]
        return "\n".join(lines)


def run_mission(a, mission, W_by_S, P_to_W):
    """Battery fraction, time and distance of each leg, as a list of Leg.

    mission is a list of (leg name, parameters) with parameters in SI units.
    A leg may give "h", its altitude in m; without it the leg uses sea-level
    1.225 kg/m^3.
    """
    legs = []
    for name, params in mission:
        params = dict(params)
        rho = _rho(params.pop("h", None))
        legs.append(Leg(name, *LEGS[name](a, rho, W_by_S, P_to_W, **params)))
    return legs


def size_point(a, mission, payload_mass, W_by_S, P_to_W):
    """Run the mission and close the weight equation at one (W/S, P/W) point."""
    legs = run_mission(a, mission, W_by_S, P_to_W)
    Wb = sum(leg.Wb for leg in legs)
    if a.We_to_Wto + Wb >= 1:
        raise ValueError(f"empty + battery fractions = {a.We_to_Wto + Wb:.3f}; the design does not close")
    Wto = payload_mass * a.g / (1 - (a.We_to_Wto + Wb))
    S = Wto / W_by_S
    return SizingResult(
        W_by_S=W_by_S,
        P_to_W=P_to_W,
        legs=legs,
        Wb=Wb,
        Wto=Wto,
        mass=Wto / a.g,
        W_empty=a.We_to_Wto * Wto,
        W_battery=Wb * Wto,
        S=S,
        b=math.sqrt(a.AR * S),
        Power=P_to_W * Wto,
        endurance=sum(leg.time for leg in legs),
        range=sum(leg.distance for leg in legs),
    )


@dataclass
class Region:
    """Feasible design points and the airplane sized at each one."""
    W_by_S: numpy.ndarray  # N/m^2
    P_to_W: numpy.ndarray  # W/N
    Wto: numpy.ndarray  # N
    S: numpy.ndarray  # m^2
    b: numpy.ndarray  # m
    Power: numpy.ndarray  # W
    lightest: SizingResult  # The feasible point with the lowest take-off weight

    def bounds(self, name):
        """(min, max) of W_by_S, P_to_W, Wto, S, b or Power over the region."""
        values = getattr(self, name)
        return float(values.min()), float(values.max())


def feasible_region(a, r, mission, payload_mass, P_to_W_max, n=80,
                    W_by_S_min=0, W_by_S_max=None, P_to_W_min=0):
    """Size the airplane at every feasible point of an n x n grid.

    The grid spans the search window W_by_S_min..W_by_S_max (capped at the
    approach line) by P_to_W_min..P_to_W_max. A point in it is feasible when its
    P/W is at or above every constraint curve, every turn in the mission is
    possible and the weight equation closes.
    """
    W_by_S_hi = approach_constraint(a, r)
    if W_by_S_max is not None:
        W_by_S_hi = min(W_by_S_hi, W_by_S_max)
    if W_by_S_min >= W_by_S_hi:
        raise ValueError(f"no feasible design points: W_by_S_min = {W_by_S_min:g} is not below "
                         f"the W/S limit of {W_by_S_hi:.2f} N/m^2 (approach line or W_by_S_max)")
    W_by_S_grid = numpy.linspace(W_by_S_min if W_by_S_min > 0 else W_by_S_hi / n, W_by_S_hi, n)
    P_to_W_grid = numpy.linspace(P_to_W_min if P_to_W_min > 0 else P_to_W_max / n, P_to_W_max, n)
    results = []
    for W_by_S, P_req in zip(W_by_S_grid, required_power(a, r, W_by_S_grid)):
        for P_to_W in P_to_W_grid[P_to_W_grid >= P_req]:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("error")  # turn_bank/turn_radius CL warnings
                    results.append(size_point(a, mission, payload_mass, float(W_by_S), float(P_to_W)))
            except (ValueError, Warning):
                continue
    if not results:
        raise ValueError("no feasible design points: widen the W/S or P/W search window or relax the requirements")
    return Region(
        W_by_S=numpy.array([res.W_by_S for res in results]),
        P_to_W=numpy.array([res.P_to_W for res in results]),
        Wto=numpy.array([res.Wto for res in results]),
        S=numpy.array([res.S for res in results]),
        b=numpy.array([res.b for res in results]),
        Power=numpy.array([res.Power for res in results]),
        lightest=min(results, key=lambda res: res.Wto),
    )


# =============================================================================
# 8. Plot
# =============================================================================
COLORS = {
    "Take off": "#0072BD",
    "Max Speed": "r",
    "Approach Velocity": "g",
    "Ceiling": "m",
    "Rate of Climb": "b",
    "Turns": (0.929, 0.694, 0.125),
    "Landing": "c",
}


def plot_constraints(curves, region=None, design_point=None, ax=None, axis=(40, 100, 0, 18)):
    """Constraint diagram (P/W against W/S) with the curve crossings.

    region shades the feasible points; design_point is drawn as a star.
    """
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots()
    if region is not None:
        ax.scatter(region.W_by_S, region.P_to_W, color="0.8", s=2, label="Feasible Region")
    for name, (x, y) in curves.items():
        ax.plot(x, y, color=COLORS.get(name), label=name)
    crossings = intersections(curves)
    if crossings:
        ax.plot([p[2] for p in crossings], [p[3] for p in crossings], "o",
                color="0.3", fillstyle="none", label="Intersections")
    if design_point is not None:
        ax.plot(*design_point, "*", color="tab:orange", markersize=12, label="Design point")
    ax.set_xlabel("Wing loading W/S (N/m^2)")
    ax.set_ylabel("Power Loading P/W (Watt/N)")
    ax.grid(True)
    ax.axis(axis)
    ax.legend(fontsize="small")
    return ax
