# Encode once to preserve empty strings and quotes in Windows PowerShell 5.1 too.
$ErrorActionPreference = 'Stop'
$argumentJson = ConvertTo-Json -InputObject @($args) -Compress
$encodedArguments = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($argumentJson))
& python (Join-Path $PSScriptRoot 'specify_tool.py') --repo-args-base64 $encodedArguments
exit $LASTEXITCODE
