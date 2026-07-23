# Absolute File Path Locations — Update Tracker

## Summary

Only **2 project files** contain hardcoded absolute file paths that should be converted to relative paths. Log files and bundled OpenVSP library files (under `OpenVSP-3.47.0-win64/`) are excluded — they are third-party or auto-generated.

---

## Locations

### 1. `Analysis.py` — Line 8

**Current (absolute):**
```python
VSPAERO_PATH = r"C:\Temp\OpenVSP_Automate_SR\OpenVSP-3.47.0-win64"
```

**Suggested (relative):**
```python
VSPAERO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "OpenVSP-3.47.0-win64")
```

**Context:** This sets the path to the VSPAero solver executable directory. The `OpenVSP-3.47.0-win64` folder already exists inside the project workspace, so a relative path based on the script's location would work.

---

### 2. `activate_genairdes.ps1` — Line 7

**Current (absolute):**
```powershell
$env:PATH = "C:\Users\sramnat\OneDrive - Clemson University\Desktop\Research Work\Generative Aircraft Design\OpenVSP_Automate_SR\OpenVSP-3.47.0-win64;" + $env:PATH
```

**Suggested (relative):**
```powershell
$env:PATH = "$PSScriptRoot\OpenVSP-3.47.0-win64;" + $env:PATH
```

**Context:** This PowerShell activation script adds OpenVSP to the system PATH. `$PSScriptRoot` resolves to the directory containing the script, making it portable.

---

## Files Excluded from Update

| File | Reason |
|------|--------|
| `worker_test.log` | Auto-generated log output, not source code |
| `OpenVSP-3.47.0-win64/python/CHARM/charm/output.py` | Third-party bundled library |
| `OpenVSP-3.47.0-win64/python/CHARM/build/lib/charm/output.py` | Third-party bundled library (build copy) |
| `OpenVSP-3.47.0-win64/scripts/python_scripts/*.py` | Third-party OpenVSP test/example scripts |
