# test-squad PowerShell 启动器
# 用法：. .\cli\test-squad.ps1  （在项目根目录执行，然后可以直接调 test-squad）
#
# 或者直接运行单次命令：
#   python "$PSScriptRoot\test_squad.py" doctor --workspace target-system-test

param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$Args
)

$ScriptDir = $PSScriptRoot
python "$ScriptDir\test_squad.py" @Args
