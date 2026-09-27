$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:UV_CACHE_DIR = Join-Path $PSScriptRoot '.cache'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $PSScriptRoot '.runtime'
$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'

try {
    if (-not (Test-Path -LiteralPath $venvPython)) {
        $uvCommand = Get-Command uv -ErrorAction SilentlyContinue
        if ($uvCommand) {
            & $uvCommand.Source python install 3.13
            if ($LASTEXITCODE -ne 0) { throw 'Python download failed.' }
            & $uvCommand.Source venv --python 3.13 --seed .venv
        } else {
            $basePython = Get-Command python -ErrorAction SilentlyContinue
            if ($basePython) {
                & $basePython.Source -m venv .venv
            } else {
                $pyCommand = Get-Command py -ErrorAction SilentlyContinue
                if (-not $pyCommand) { throw 'Install Python 3.10+ from https://www.python.org/downloads/ and run again.' }
                & $pyCommand.Source -3 -m venv .venv
            }
        }
        if ($LASTEXITCODE -ne 0) { throw 'Could not create Python environment. Please install Python 3.10+.' }
    }
    & $venvPython -m pip install --upgrade -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check your internet connection and retry.' }
    & $venvPython -c "import tkinter, yt_dlp, deno, imageio_ffmpeg; print('All components ready.')"
    if ($LASTEXITCODE -ne 0) { throw 'Dependency verification failed.' }
    Write-Host 'Setup complete. Double-click start.bat to open the downloader.' -ForegroundColor Green
} catch {
    Write-Host $_ -ForegroundColor Red
    exit 1
}
