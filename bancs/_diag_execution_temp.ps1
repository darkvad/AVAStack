# _diag_execution_temp.ps1 - banc de DIAGNOSTIC (developpement) : Windows
# laisse-t-il EXECUTER depuis %TEMP% un fichier telecharge ?
#
# POURQUOI CE BANC EXISTE (constat reel du 01/10/2026) : l'installateur Inno
# Setup d'AVAStack s'est arrete chez un testeur sur
#     "Impossible d'executer un fichier depuis le dossier temporaire.
#      Abandon de l'installation. Erreur 4551 : une strategie de controle
#      d'application a bloque ce fichier."
# Le seul pas ou Inno execute un fichier DEPUIS %TEMP% est le telechargement
# puis le lancement de l'installateur python.org -- ce qu'il ne fait QUE s'il ne
# trouve aucun Python 3.10+. Ce banc reproduit CE pas, exactement, et rien
# d'autre : il telecharge l'installateur python.org dans %TEMP% et l'EXECUTE de
# la. Il repond a une seule question : le systeme autorise-t-il, ou bloque-t-il ?
#
# SANS CONSEQUENCE : l'option /layout demande a l'installateur de telecharger sa
# charge utile dans un dossier jetable, SANS RIEN INSTALLER (verifie le
# 02/10/2026 : aucune entree "Python 3.12" dans les applications installees).
# Tous les autres arguments neutralisent les effets de bord (pas de PATH, pas de
# raccourcis, pas d'associations, pas de lanceur py).
#
# TEMOIN DEJA MESURE (machine d'Alain, 02/10/2026, Smart App Control ARRETE) :
# execution AUTORISEE (code 0), fichier signe "Valid" par la Python Software
# Foundation. La mesure a rejouer est la MEME avec SAC ACTIF, et surtout sur une
# machine ou l'exécution a echoue.
#
# LECTURE DES RESULTATS
#   - "EXECUTION AUTORISEE" avec SAC actif  -> SAC est innocent : chercher une
#     AUTRE strategie de controle d'application (WDAC "entreprise", antivirus) ;
#   - "EXECUTION BLOQUEE"                   -> le pas %TEMP% est bien le coupable
#     (signer l'installeur, ou faire qu'Inno ne lance rien depuis %TEMP%) ;
#   - signature "NotSigned"/"HashMismatch"  -> le telechargement etait TRONQUE,
#     ce qui expliquerait l'Erreur 4551 a lui seul.
#
# Usage : powershell -NoProfile -ExecutionPolicy Bypass -File _diag_execution_temp.ps1

$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

Write-Host "=== 1. Etat de Smart App Control ==="
$sac = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\CI\Policy' `
        -Name VerifiedAndReputablePolicyState -ErrorAction SilentlyContinue).VerifiedAndReputablePolicyState
Write-Host "VerifiedAndReputablePolicyState = $sac   (0 = arrete, 1 = ACTIVE/applique, 2 = evaluation)"
if ($sac -eq 2) {
    Write-Host "ATTENTION : en EVALUATION, Windows n'applique RIEN -> le test ne prouverait rien."
}

Write-Host "=== 2. Telechargement dans %TEMP% ==="
$dst = Join-Path $env:TEMP 'python-3.12.7-amd64.exe'
if (-not (Test-Path $dst)) {
    Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe' `
        -OutFile $dst -UseBasicParsing
}
Write-Host "fichier : $dst  ($((Get-Item $dst).Length) octets)"
$sig = Get-AuthenticodeSignature $dst
Write-Host "signature : $($sig.Status)   signataire : $($sig.SignerCertificate.Subject)"

Write-Host "=== 3. EXECUTION DEPUIS %TEMP% (le pas en question) ==="
$layout = Join-Path $env:TEMP 'layout-test'
Remove-Item -Recurse -Force $layout -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $layout | Out-Null
try {
    $p = Start-Process -FilePath $dst `
        -ArgumentList @('/quiet', '/layout', $layout, 'InstallAllUsers=0',
                        'PrependPath=0', 'Include_launcher=0', 'Shortcuts=0',
                        'AssociateFiles=0', 'Include_test=0') `
        -Wait -PassThru
    Write-Host "RESULTAT : EXECUTION AUTORISEE  (code de sortie $($p.ExitCode))"
} catch {
    Write-Host "RESULTAT : EXECUTION BLOQUEE -> $($_.Exception.Message)"
}
Write-Host "fichiers extraits dans le layout :"
Get-ChildItem $layout -ErrorAction SilentlyContinue |
    Select-Object -First 5 -ExpandProperty Name | ForEach-Object { "    $_" }

Write-Host "=== 4. Controle : rien ne doit s'etre installe ==="
try {
    Write-Host ("Python 3.12 installe ? " +
        @(Get-Package -Name 'Python 3.12*' -ErrorAction SilentlyContinue).Count)
} catch {
    Write-Host "(controle d'installation indisponible sur ce systeme)"
}
Write-Host ""
Write-Host "NETTOYAGE (a faire apres lecture) :"
Write-Host '  Remove-Item -Recurse -Force "$env:TEMP\layout-test"'
Write-Host '  Remove-Item -Force "$env:TEMP\python-3.12.7-amd64.exe"'
