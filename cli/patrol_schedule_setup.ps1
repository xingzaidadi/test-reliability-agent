# patrol_schedule_setup.ps1
# 在 Windows Task Scheduler 中注册每日 09:30 的 daily_smoke 巡检任务
# 执行前请先配置好所有环境变量
#
# 用法（管理员 PowerShell）：
#   .\cli\patrol_schedule_setup.ps1
#
# 查看任务：
#   Get-ScheduledTask -TaskName "SuperTestAgent-DailySmoke"
#
# 手动触发：
#   Start-ScheduledTask -TaskName "SuperTestAgent-DailySmoke"
#
# 删除任务：
#   Unregister-ScheduledTask -TaskName "SuperTestAgent-DailySmoke" -Confirm:$false

$TaskName    = "SuperTestAgent-DailySmoke"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExe   = (Get-Command python).Source
$PatrolScript = Join-Path $PSScriptRoot "patrol_runner.py"
$LogFile     = Join-Path $ProjectRoot "outputs\patrol_schedule.log"

# 每个环境变量的值从当前 shell 环境读取（不硬编码到任务中）
$EnvVars = @(
    "TARGET_SYSTEM_BASE_URL",
    "TARGET_SYSTEM_TOKEN",
    "TARGET_SYSTEM_UI_URL",
    "TARGET_SYSTEM_TEST_USER",
    "TARGET_SYSTEM_TEST_PASSWORD"
)

Write-Host "检查必要环境变量..."
foreach ($v in $EnvVars) {
    if (-not [System.Environment]::GetEnvironmentVariable($v, "Machine") -and
        -not [System.Environment]::GetEnvironmentVariable($v, "User")) {
        Write-Warning "  $v 未设置为系统/用户级环境变量（仅 session 级不会传给 Task Scheduler）"
    } else {
        Write-Host "  [OK] $v"
    }
}

# 构造执行动作
$Action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "`"$PatrolScript`" --profile daily_smoke >> `"$LogFile`" 2>&1" `
    -WorkingDirectory $ProjectRoot

# 每个工作日 09:30
$Trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday `
    -At "09:30"

# 使用当前登录用户运行
$Principal = New-ScheduledTaskPrincipal `
    -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -RunLevel Highest

$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -RestartCount 1 `
    -RestartInterval (New-TimeSpan -Minutes 5)

# 注册任务
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Principal $Principal `
    -Settings $Settings `
    -Description "Super Test Agent daily_smoke patrol for target-system" `
    -Force

Write-Host ""
Write-Host "[OK] 任务已注册: $TaskName"
Write-Host "     下次触发: 明日 09:30（工作日）"
Write-Host "     日志文件: $LogFile"
Write-Host ""
Write-Host "手动触发："
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'"
