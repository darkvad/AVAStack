# signer_msix.ps1 - signe un paquet .msix AVAStack avec un certificat AUTO-SIGNE
#
# POURQUOI : Windows REFUSE d'installer un MSIX non signe, et la signature du
# Microsoft Store n'existe qu'APRES soumission (c'est Microsoft qui RE-SIGNE le
# paquet publie). Pour tester en local AVANT le Store, il faut donc signer avec
# un certificat auto-signe et faire CONFIANCE a ce certificat sur la machine de
# test. Le .cer exporte sert uniquement a ca : il ne part JAMAIS chez personne.
#
# Le SUJET du certificat doit etre EXACTEMENT le Publisher du manifeste
# (defaut : "CN=AVAStack Test").
#
# Usage :
#   powershell -NoProfile -ExecutionPolicy Bypass -File signer_msix.ps1 `
#       -Msix "installer\windows\output\avastack-2.49.0-windows.msix"
#   ... -Timestamp      : horodatage RFC3161 (exige Internet ; pour le Store)
#   ... -Installer      : fait CONFIANCE au certificat et INSTALLE le paquet
# NB : script volontairement sans caracteres accentues (encodage PS 5.1).

param(
    [Parameter(Mandatory = $true)][string]$Msix,
    [string]$Publisher = 'CN=AVAStack Test',
    [string]$MotDePasse = 'avastack',
    [switch]$Timestamp,
    [switch]$Installer
)

$ErrorActionPreference = 'Stop'

# Les commandes NATIVES (signtool) ecrivent sur stderr des messages qui, avec
# ErrorActionPreference='Stop', deviennent des erreurs TERMINANTES (piege connu
# du projet) : on les lance donc avec 'Continue' et on MERGE stderr dans la
# sortie, pour que le message s'affiche SANS faire echouer le script.
function Invoquer-Natif {
    param([string]$Exe, [string[]]$Arguments, [switch]$Silencieux)
    $ancien = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $sortie = & $Exe @Arguments 2>&1 | Out-String
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $ancien
    }
    if ($sortie -and -not $Silencieux) { Write-Host $sortie.TrimEnd() }
    return $code
}

function Trouver-Signtool {
    $dansPath = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($dansPath) { return $dansPath.Source }
    $trouves = @()
    $racines = @(
        (Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\bin'),
        (Join-Path $env:ProgramFiles 'Windows Kits\10\bin')
    )
    foreach ($racine in $racines) {
        if (-not (Test-Path $racine)) { continue }
        foreach ($v in (Get-ChildItem $racine -Directory)) {
            if ($v.Name -notmatch '^\d+(\.\d+)+$') { continue }
            $c = Join-Path $v.FullName 'x64\signtool.exe'
            if (Test-Path $c) {
                $trouves += [pscustomobject]@{ V = [version]$v.Name; P = $c }
            }
        }
    }
    if ($trouves.Count -gt 0) {
        return ($trouves | Sort-Object V | Select-Object -Last 1).P
    }
    $secours = Join-Path ${env:ProgramFiles(x86)} `
        'Windows Kits\10\App Certification Kit\signtool.exe'
    if (Test-Path $secours) { return $secours }
    return $null
}

$Signtool = Trouver-Signtool
if (-not $Signtool) {
    Write-Host 'ERREUR : signtool.exe introuvable (il vient du Windows SDK).' -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $Msix)) {
    Write-Host "ERREUR : paquet introuvable : $Msix" -ForegroundColor Red
    exit 1
}

# --- Certificat : reutilise celui du sujet, sinon le CREE --------------------
$Cert = Get-ChildItem 'Cert:\CurrentUser\My' -ErrorAction SilentlyContinue |
    Where-Object { $_.Subject -eq $Publisher } | Select-Object -First 1
if (-not $Cert) {
    Write-Host "Certificat auto-signe absent : creation ($Publisher)"
    $Cert = New-SelfSignedCertificate -Type Custom -Subject $Publisher `
        -KeyUsage DigitalSignature -FriendlyName 'AVAStack (essai MSIX)' `
        -CertStoreLocation 'Cert:\CurrentUser\My' `
        -TextExtension @('2.5.29.37={text}1.3.6.1.5.5.7.3.3',
                         '2.5.29.19={text}')
}
Write-Host "Certificat : $($Cert.Thumbprint)  ($($Cert.Subject))"

# --- Export .cer (a faire CONFIANCE) + .pfx (pour signer) --------------------
$Dossier = Split-Path $Msix -Parent
$Base = [IO.Path]::GetFileNameWithoutExtension($Msix)
$Cer = Join-Path $Dossier "$Base.cer"
$Pfx = Join-Path $Dossier "$Base.pfx"
Export-Certificate -Cert $Cert -FilePath $Cer -Force | Out-Null
$Securise = ConvertTo-SecureString -String $MotDePasse -Force -AsPlainText
Export-PfxCertificate -Cert $Cert -FilePath $Pfx -Password $Securise -Force |
    Out-Null

# --- Signature ---------------------------------------------------------------
$SignArgs = @('sign', '/fd', 'SHA256', '/f', $Pfx, '/p', $MotDePasse)
if ($Timestamp) {
    $SignArgs += @('/tr', 'http://timestamp.digicert.com', '/td', 'SHA256')
}
$SignArgs += $Msix
Write-Host "Signature : signtool sign /fd SHA256 $(Split-Path $Msix -Leaf)"
$CodeSign = Invoquer-Natif -Exe $Signtool -Arguments $SignArgs
if ($CodeSign -ne 0) {
    Write-Host "ERREUR : signtool a echoue (code $CodeSign)." -ForegroundColor Red
    exit $CodeSign
}

Write-Host ''
$CodeVerif = Invoquer-Natif -Exe $Signtool `
    -Arguments @('verify', '/pa', $Msix) -Silencieux
if ($CodeVerif -eq 0) {
    Write-Host 'Signature VERIFIEE (certificat approuve).' -ForegroundColor Green
} else {
    Write-Host 'Signature posee. Elle ne sera VERIFIEE qu''une fois le certificat'
    Write-Host 'approuve (etape "faire CONFIANCE" ci-dessous) : avant cela, Windows'
    Write-Host 'repond "root certificate which is not trusted" : c''est NORMAL.'
}
Write-Host ''
Write-Host "OK - paquet signe : $Msix" -ForegroundColor Green
Write-Host "     certificat   : $Cer   (a faire CONFIANCE pour installer)"
Write-Host "     mot de passe : $MotDePasse   (.pfx, NE PAS diffuser)"

if ($Installer) {
    Write-Host ''
    Write-Host 'Confiance au certificat (CurrentUser\TrustedPeople) puis installation...'
    Import-Certificate -FilePath $Cer -CertStoreLocation 'Cert:\CurrentUser\TrustedPeople' |
        Out-Null
    Add-AppxPackage -Path $Msix
    Write-Host 'Installe : l''application apparait dans le menu Demarrer.' -ForegroundColor Green
} else {
    Write-Host ''
    Write-Host 'Pour INSTALLER (2 commandes, une seule fois par machine) :'
    Write-Host "  Import-Certificate -FilePath `"$Cer`" -CertStoreLocation Cert:\CurrentUser\TrustedPeople"
    Write-Host "  Add-AppxPackage -Path `"$Msix`""
    Write-Host 'Puis lancer AVAStack depuis le menu Demarrer.'
    Write-Host 'Pour DESINSTALLER :'
    Write-Host '  Get-AppxPackage AVAStack* | Remove-AppxPackage'
}
exit 0