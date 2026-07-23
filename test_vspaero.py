"""
test_vspaero.py - Standalone VSPAero analysis script

Tests a single VSP model using the same analysis parameters as the optimization framework.

Calculates aerodynamic parameters (Reynolds number, Mach, xcg) from mission requirements,
matching exactly how the optimization framework sets up VSPAero.

Usage:
    python test_vspaero.py <vsp_file> [mission parameters] [--output csv_file]

Examples:
    python test_vspaero.py model.vsp3
    python test_vspaero.py model.vsp3 --cruise_speed 30.9 --stall_speed 28.3 --cruise_altitude 7620
    python test_vspaero.py model.vsp3 --wing_span 66 --power 1500 --output results.csv
"""

import os
import sys
import argparse
import pandas as pd
import numpy as np
from pathlib import Path

# Add project root to path so we can import Analysis
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from Analysis import Aero


def calculate_altitude_conditions(altitude_m):
    """
    Calculate air density and temperature at given altitude using standard atmosphere.
    
    Args:
        altitude_m: Altitude in meters
        
    Returns:
        (rho, temperature, pressure): Air density (kg/m³), temperature (°C), pressure (Pa)
    """
    if altitude_m <= 11000:  # Below 11 km
        T = 15.04 - 0.00649 * altitude_m
        P = 101.29 * ((T + 273.1) / 288.08) ** 5.256
    elif altitude_m <= 25000:
        T = -56.46
        P = 22.65 * np.exp(1.73 - 0.000157 * altitude_m)
    else:
        T = -131.21 + 0.00299 * altitude_m
        P = 2.488 * ((T + 273.1) / 216.6) ** -11.388
    
    rho = P / (0.2869 * (T + 273.1))
    return rho, T, P


def calculate_mach_number(cruise_speed_ms, altitude_m):
    """
    Calculate Mach number from cruise speed and altitude.
    
    Args:
        cruise_speed_ms: Cruise speed in m/s
        altitude_m: Altitude in meters
        
    Returns:
        mach: Mach number
    """
    # Temperature at altitude
    if altitude_m <= 11000:
        T = 15.04 - 0.00649 * altitude_m
    elif altitude_m <= 25000:
        T = -56.46
    else:
        T = -131.21 + 0.00299 * altitude_m
    
    # Speed of sound: a = sqrt(1.4 * R * T), where R = 287 J/(kg·K)
    T_kelvin = T + 273.15
    a = np.sqrt(1.4 * 287 * T_kelvin)
    
    mach = cruise_speed_ms / a
    return mach


def calculate_reynolds_number(cruise_speed_ms, wing_span_m, altitude_m):
    """
    Calculate Reynolds number at cruise conditions using wing span as reference length.
    
    Args:
        cruise_speed_ms: Cruise speed in m/s
        wing_span_m: Wing span in meters
        altitude_m: Altitude in meters
        
    Returns:
        reynolds: Reynolds number
    """
    rho, _, _ = calculate_altitude_conditions(altitude_m)
    
    # Dynamic viscosity of air (Sutherland's law, approximate for 0-100m altitude)
    # mu ≈ 1.81e-5 Pa·s at sea level
    mu = 1.81e-5
    
    # Reynolds number: Re = (rho * V * L) / mu
    reynolds = (rho * cruise_speed_ms * wing_span_m) / mu
    
    return reynolds


def calculate_xcg_from_wingspan(wing_span_ft):
    """
    Calculate CG position from wing span using framework formulas.
    
    Formulas (from Pymoo.py):
        Fuse_length = 0.47 * Wing_span (in meters)
        xcg = 0.33 * Fuse_length
        
    Args:
        wing_span_ft: Wing span in feet
        
    Returns:
        xcg: Center of gravity position in meters
    """
    # Convert feet to meters
    wing_span_m = wing_span_ft * 0.3048
    
    # Apply framework formulas
    fuse_length = 0.47 * wing_span_m
    xcg = 0.33 * fuse_length
    
    return xcg, wing_span_m, fuse_length


def main():
    parser = argparse.ArgumentParser(
        description="Test VSPAero analysis on a single VSP model with mission-based parameters",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "vsp_file",
        type=str,
        help="Path to the VSP file (.vsp3)"
    )
    
    # Mission parameters (all optional with defaults)
    parser.add_argument(
        "--cruise_speed",
        type=float,
        default=30.9,
        help="Cruise speed in m/s (default: 30.9, i.e., 60 kts)"
    )
    parser.add_argument(
        "--stall_speed",
        type=float,
        default=28.3,
        help="Stall speed in m/s (default: 28.3, i.e., 55 kts) - used for reference"
    )
    parser.add_argument(
        "--cruise_altitude",
        type=float,
        default=7620,
        help="Cruise altitude in meters (default: 7620)"
    )
    parser.add_argument(
        "--wing_span",
        type=float,
        default=66.0,
        help="Wing span in feet (default: 66.0 ft, auto-calculates xcg)"
    )
    parser.add_argument(
        "--power",
        type=float,
        default=None,
        help="Engine power in Watts (optional; if not provided, uses midpoint of feasible range)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Save results to CSV file (optional)"
    )

    args = parser.parse_args()

    # Validate input file
    if not os.path.exists(args.vsp_file):
        print(f"ERROR: VSP file not found: {args.vsp_file}")
        sys.exit(1)

    # Calculate xcg from wing span
    xcg, wing_span_m, fuse_length = calculate_xcg_from_wingspan(args.wing_span)
    
    # Calculate atmospheric conditions at cruise altitude
    rho_cruise, temp_cruise, _ = calculate_altitude_conditions(args.cruise_altitude)
    
    # Calculate Mach number
    mach = calculate_mach_number(args.cruise_speed, args.cruise_altitude)
    
    # Calculate Reynolds number
    reynolds = calculate_reynolds_number(args.cruise_speed, wing_span_m, args.cruise_altitude)
    
    # Use provided power or default
    if args.power is None:
        # Use a typical midpoint (1000 W default from original)
        engine_power = 1000
        power_source = "default"
    else:
        engine_power = args.power
        power_source = "user-specified"

    abs_vsp_path = os.path.abspath(args.vsp_file)
    print(f"\n{'='*75}")
    print(f"VSPAero Test Analysis - Mission-Based Setup")
    print(f"{'='*75}")
    print(f"Model: {abs_vsp_path}")
    print(f"\n--- Mission Parameters ---")
    print(f"  Cruise Speed: {args.cruise_speed} m/s ({args.cruise_speed*1.944:.1f} kts)")
    print(f"  Stall Speed: {args.stall_speed} m/s ({args.stall_speed*1.944:.1f} kts)")
    print(f"  Cruise Altitude: {args.cruise_altitude} m")
    print(f"  Wing Span: {args.wing_span} ft ({wing_span_m:.3f} m)")
    print(f"\n--- Calculated Parameters ---")
    print(f"  Fuselage Length: {fuse_length:.3f} m (0.47 × Wing_span)")
    print(f"  CG Position (Xcg): {xcg:.3f} m (0.33 × Fuse_length)")
    print(f"  Air Density @ {args.cruise_altitude}m: {rho_cruise:.4f} kg/m³")
    print(f"  Temperature @ {args.cruise_altitude}m: {temp_cruise:.1f}°C")
    print(f"  Mach Number: {mach:.4f}")
    print(f"  Reynolds Number: {reynolds:.2e}")
    print(f"\n--- VSPAero Simulation Setup ---")
    print(f"  Engine Power: {engine_power} W ({power_source})")
    print(f"  Alpha Sweep: -1.0° to 10.0° (5 points)")
    print(f"  Analysis Type: VLM (Vortex Lattice Method)")
    print(f"{'='*75}\n")

    try:
        # Create Aero object with calculated parameters
        aero = Aero(path=abs_vsp_path, Engine_Power=engine_power, xcg=xcg)

        # Run the complete analysis
        cost, area, neg_L2D, CMy = aero.compute_objective()

        # Convert negative L/D back to positive
        L2D = -neg_L2D

        # Prepare results dictionary
        results = {
            "Model": abs_vsp_path,
            "Cruise_Speed_ms": args.cruise_speed,
            "Cruise_Altitude_m": args.cruise_altitude,
            "Wing_Span_ft": args.wing_span,
            "Wing_Span_m": f"{wing_span_m:.3f}",
            "Xcg_m": f"{xcg:.3f}",
            "Air_Density_kg_m3": f"{rho_cruise:.4f}",
            "Mach_Number": f"{mach:.4f}",
            "Reynolds_Number": f"{reynolds:.2e}",
            "Engine_Power_W": engine_power,
            "Cost_USD": f"{cost:.2f}",
            "Wetted_Area_m2": f"{sum(area):.2f}",
            "L/D": f"{L2D:.2f}",
            "CMy": f"{CMy:.6f}",
            "Component_Areas_m2": str(area),
        }

        # Print summary
        print(f"{'='*75}")
        print(f"ANALYSIS RESULTS")
        print(f"{'='*75}")
        for key, value in results.items():
            if key != "Component_Areas_m2":
                print(f"  {key}: {value}")
        print(f"  Component Areas: {', '.join([f'{a:.2f}' for a in area])} m²")
        print(f"{'='*75}\n")

        # Save to CSV if requested
        if args.output:
            df = pd.DataFrame([results])
            df.to_csv(args.output, index=False)
            print(f"Results saved to: {args.output}\n")

        return 0

    except FileNotFoundError as e:
        print(f"\nERROR: {e}")
        sys.exit(1)
    except RuntimeError as e:
        print(f"\nERROR: VSPAero analysis failed")
        print(f"  {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nUNEXPECTED ERROR: {type(e).__name__}")
        print(f"  {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())