"""
VSP Worker - subprocess entry point for VSPAero analysis.

Called by Pymoo.py to isolate native OpenVSP/VSPAero crashes from the
main optimization process.

Usage:
    python vsp_worker.py <vsp_file> <engine_power> <cg> <wing_area_planform>

Outputs JSON wrapped in markers so the parent can extract it even if
VSPAero prints stray text to stdout.
"""
import sys
import os
import json
import traceback
import shutil
import tempfile

# Ensure the project root is on sys.path so we can import Analysis
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    if len(sys.argv) != 5:
        print(f"Usage: {sys.argv[0]} <vsp_file> <engine_power> <cg> <wing_area_planform>",
              file=sys.stderr)
        sys.exit(1)

    vsp_file = sys.argv[1]
    engine_power = float(sys.argv[2])
    cg = float(sys.argv[3])
    wing_area_planform = float(sys.argv[4])

    try:
        # Import here so any openvsp init happens inside the subprocess
        from Analysis import Aero

        worker_root = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "output_vsp_files",
            "worker_tmp",
        )
        os.makedirs(worker_root, exist_ok=True)

        stem, ext = os.path.splitext(os.path.basename(vsp_file))
        work_dir = tempfile.mkdtemp(
            prefix=f"{stem}_{os.getpid()}_",
            dir=worker_root,
        )
        local_vsp_file = os.path.join(work_dir, f"{stem}{ext}")
        shutil.copy2(vsp_file, local_vsp_file)

        # VSPAero writes sidecar files next to the input model. Use a private
        # copy so parallel workers do not contend for the same files.
        os.chdir(work_dir)

        aero = Aero(path=local_vsp_file, Engine_Power=engine_power, xcg=cg)
        # CL_req is computed inside compute_objective() from THIS candidate's
        # planform area, so each design is checked against its own wing.
        aero.wing_area_planform = wing_area_planform

        # compute_objective() returns a dict with every key Pymoo reads,
        # including "status", "CL_req", "CL_min", "CL_max". An infeasible design
        # (e.g. CL_req not reachable) is still a successful run: feasibility is
        # reported in result["status"], not by success=False.
        result = aero.compute_objective()
        result["success"] = True

    except Exception as e:
        result = {
            "success": False,
            "error": f"{type(e).__name__}: {str(e)}",
            "traceback": traceback.format_exc(),
        }

    # Emit result between unique markers so the parent can find it
    # even if OpenVSP prints unexpected text to stdout.
    payload = json.dumps(result, default=float)   # default=float handles numpy scalars
    print(f">>>VSP_WORKER_RESULT>>>{payload}<<<VSP_WORKER_RESULT<<<", flush=True)


if __name__ == "__main__":
    main()