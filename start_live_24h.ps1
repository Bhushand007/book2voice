$ErrorActionPreference = "Continue"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ServerLog = Join-Path $ProjectRoot "server.out.log"
$ServerErrLog = Join-Path $ProjectRoot "server.err.log"
$TunnelLog = Join-Path $ProjectRoot "tunnel.out.log"
$TunnelErrLog = Join-Path $ProjectRoot "tunnel.err.log"
$PublicUrlFile = Join-Path $ProjectRoot "LIVE_URL.txt"
$TunnelPidFile = Join-Path $ProjectRoot "tunnel.pid"
$EndAt = (Get-Date).AddHours(24)

function Start-Book2VoiceServer {
    $running = Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue
    if (-not $running) {
        Start-Process -FilePath "python" `
            -ArgumentList "backend/app.py" `
            -WorkingDirectory $ProjectRoot `
            -RedirectStandardOutput $ServerLog `
            -RedirectStandardError $ServerErrLog `
            -WindowStyle Hidden
        Start-Sleep -Seconds 4
    }
}

function Start-PublicTunnel {
    $currentUrl = Get-Content $PublicUrlFile -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($currentUrl) {
        try {
            $health = Invoke-WebRequest -UseBasicParsing -Uri "$currentUrl/health" -TimeoutSec 10
            if ($health.StatusCode -eq 200) {
                return
            }
        } catch {
            # A running SSH process can still point at an expired public tunnel.
        }
    }

    $managedPid = Get-Content $TunnelPidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($managedPid -and (Get-Process -Id $managedPid -ErrorAction SilentlyContinue)) {
        Stop-Process -Id $managedPid -Force
    }
    Remove-Item $TunnelPidFile -Force -ErrorAction SilentlyContinue
    Remove-Item $TunnelLog -Force -ErrorAction SilentlyContinue

    $tunnel = Start-Process -FilePath "ssh" `
            -ArgumentList @(
                "-T",
                "-o", "ExitOnForwardFailure=yes",
                "-o", "StrictHostKeyChecking=no",
                "-o", "ServerAliveInterval=60",
                "-R", "80:127.0.0.1:5000",
                "nokey@localhost.run"
            ) `
            -WorkingDirectory $ProjectRoot `
            -RedirectStandardOutput $TunnelLog `
            -RedirectStandardError $TunnelErrLog `
            -WindowStyle Hidden `
            -PassThru

    Set-Content -Path $TunnelPidFile -Value $tunnel.Id
    Start-Sleep -Seconds 10
    $line = Select-String -Path $TunnelLog -Pattern "https://[a-z0-9.-]+\.lhr\.life" -AllMatches -ErrorAction SilentlyContinue |
        Select-Object -Last 1

    if ($line) {
        $url = $line.Matches[$line.Matches.Count - 1].Value
        Set-Content -Path $PublicUrlFile -Value $url
        Write-Output "Live URL: $url"
    } else {
        Write-Warning "Public tunnel did not provide a URL. It will retry on the next health check."
    }
}

while ((Get-Date) -lt $EndAt) {
    Start-Book2VoiceServer
    Start-PublicTunnel
    Start-Sleep -Seconds 60
}
