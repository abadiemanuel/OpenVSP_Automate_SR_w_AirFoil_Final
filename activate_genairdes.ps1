# Activation script for GenAirDes conda environment with OpenVSP support

# Activate conda environment
conda activate GenAirDes

# Add OpenVSP to PATH
$env:PATH = "$PSScriptRoot\OpenVSP-3.47.0-win64;" + $env:PATH

Write-Host "GenAirDes environment activated with OpenVSP support!" -ForegroundColor Green
Write-Host "You can now use: import openvsp as vsp" -ForegroundColor Cyan
