# Install or update the private dashboard on this Windows/WSL host.
# Run from PowerShell. Tailscale must already be connected.
[CmdletBinding()]
param(
    [string]$Distribution = 'Ubuntu-24.04',
    [string]$Repository = '/home/maxtalwar/agent-world'
)
$ErrorActionPreference = 'Stop'
$taskName = 'Agent World Leaderboard'
$wsl = "$env:WINDIR\System32\wsl.exe"
$tailscale = "$env:ProgramFiles\Tailscale\tailscale.exe"
# Copy a standalone app release so switching Git branches cannot remove it.
$install = @'
from pathlib import Path
import shutil
root = Path.cwd()
target = root / ".local/leaderboard-app"
(target / "static").mkdir(parents=True, exist_ok=True)
for module in ["leaderboard.py", "leaderboard_launch.py", "leaderboard_supervisor.py"]:
    shutil.copy2(root / "agent_world" / module, target / module)
shutil.copy2(root / "scripts/serve-leaderboard", target / "serve-leaderboard")
for name in ["leaderboard.html", "leaderboard.css", "leaderboard.js", "leaderboard-launch.js", "inter-latin.woff2"]:
    shutil.copy2(root / "agent_world/static" / name, target / "static" / name)
shutil.copytree(root / "agent_world/static/labs", target / "static/labs", dirs_exist_ok=True)
'@
& $wsl -d $Distribution --cd $Repository --exec python3 -c $install
if ($LASTEXITCODE) { throw 'Could not install the leaderboard release.' }
$supervisor = (Get-Command codex -ErrorAction Stop).Source
$supervisorWsl = (& $wsl -d $Distribution --exec wslpath -u $supervisor).Trim()
$tailnet = (& $tailscale status --json | ConvertFrom-Json)
$settingsJson = @{
    launch_enabled = $true
    supervisor_binary = $supervisorWsl
    allowed_hosts = @($tailnet.Self.DNSName.TrimEnd('.'), $tailnet.Self.HostName.ToLower())
} | ConvertTo-Json -Compress
$settingsJson | & $wsl -d $Distribution --cd $Repository --exec python3 -c "import sys,pathlib,json; v=json.load(sys.stdin); pathlib.Path('.local/leaderboard-settings.json').write_text(json.dumps(v))"
if ($LASTEXITCODE) { throw 'Could not configure the benchmark launcher.' }
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) { Stop-ScheduledTask -TaskName $taskName }
# Task Scheduler owns the foreground WSL process; it survives the Codex task.
$run = "& '$wsl' -d '$Distribution' --cd '$Repository' --exec /bin/bash '$Repository/.local/leaderboard-app/serve-leaderboard' '$Repository' '$Repository/.local/leaderboard-app/leaderboard.py'; exit " + '$LASTEXITCODE'
$action = New-ScheduledTaskAction -Execute "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument ("-NoProfile -NonInteractive -WindowStyle Hidden -Command " + '"' + $run + '"')
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Private Agent World leaderboard. Restarts on failure and starts at Windows sign-in.' -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
& $tailscale serve --bg --http=8091 http://127.0.0.1:8091
if ($LASTEXITCODE) { throw 'The app is installed, but the Tailscale route could not be configured.' }
Write-Output 'Leaderboard installed. Task: Agent World Leaderboard. Port: 8091.'
