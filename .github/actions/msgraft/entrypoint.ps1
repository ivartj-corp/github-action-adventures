param(
    [Parameter(Mandatory)]
    [string]$AccessToken
)

$InformationPreference = "Continue"

Write-Information "== Installed modules"
Get-InstalledModule | % Name

Write-Information "== Loaded modules"
Get-Module | % Name

Connect-MgGraph -AccessToken (ConvertTo-SecureString $AccessToken -AsPlainText -Force)

Get-MgGroup
