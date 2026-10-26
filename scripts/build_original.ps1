# Build helper only. This script does not run an executable.
# Requires Intel classic ifort and its configured Visual Studio environment.
[CmdletBinding()]
param(
    [string]$BuildDirectory = "results/original_build",
    [string]$InputFile = "vendor/calvano_original/AER_paper_Rscripts/table_I/A_InputParameters.txt"
)
$ErrorActionPreference = "Stop"
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$buildPath = [IO.Path]::GetFullPath((Join-Path $projectRoot $BuildDirectory))
$sourcePath = Join-Path $projectRoot "vendor/calvano_original/AER_fcode/baseline"
$inputPath = [IO.Path]::GetFullPath((Join-Path $projectRoot $InputFile))
if (-not $buildPath.StartsWith($projectRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw "BuildDirectory must be inside the project."
}
$compiler = Get-Command ifort.exe -ErrorAction SilentlyContinue
if (-not $compiler) {
    throw "Intel classic ifort was not found. Open a configured Intel compiler environment; see docs/ORIGINAL_CODE.md."
}
if (-not (Test-Path -LiteralPath $inputPath -PathType Leaf)) {
    throw "Input parameter file was not found: $inputPath"
}
$moduleNames = @(
    "generic_routines", "globals", "QL_routines", "PI_routines",
    "LearningSimulation", "ConvergenceResults", "EquilibriumCheck",
    "ImpulseResponse", "QGapToMaximum", "DetailedAnalysis",
    "LearningTrajectory", "main"
)
$sourceFiles = @($moduleNames | ForEach-Object { Join-Path $sourcePath ($_.ToString() + ".f90") })
New-Item -ItemType Directory -Path $buildPath -Force | Out-Null
Push-Location -LiteralPath $buildPath
try {
    & $compiler.Source /nologo /O2 /fpp /Qopenmp @sourceFiles /exe:baseline.exe /link /STACK:800000000,800000000
    if ($LASTEXITCODE -ne 0) { throw "Original-source compilation failed with code $LASTEXITCODE" }
    Copy-Item -LiteralPath $inputPath -Destination (Join-Path $buildPath "A_InputParameters.txt")
    Write-Host "Build completed: $buildPath"
    Write-Host "Review the copied input parameters before manually running the newly compiled baseline.exe."
} finally {
    Pop-Location
}
