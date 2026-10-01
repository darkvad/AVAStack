@echo off
rem install_avastack.bat - lanceur DOUBLE-CLIC de l'installateur Windows AVAStack.
rem
rem Pourquoi ce fichier : Windows PowerShell refuse d'executer un .ps1 par
rem simple double-clic (politique d'execution). Ce petit lanceur appelle
rem install_avastack.ps1 avec -ExecutionPolicy Bypass POUR CETTE FOIS
rem seulement (rien n'est change sur le systeme) et transmet les options.
rem
rem La fenetre reste ouverte a la fin (pause) pour qu'on puisse LIRE le
rem resultat, y compris en cas d'erreur.
rem
rem Usage : double-clic, ou en terminal :
rem     install_avastack.bat                 (installation par defaut)
rem     install_avastack.bat -Aide           (options)
rem     install_avastack.bat -Desinstaller   (desinstallation)

setlocal
set "SCRIPT=%~dp0install_avastack.ps1"
if not exist "%SCRIPT%" (
    echo.
    echo ERREUR : install_avastack.ps1 introuvable a cote de ce fichier.
    echo Extrais le ZIP EN ENTIER ^(clic droit sur le .zip -^> Extraire tout^),
    echo puis relance ce fichier depuis le dossier extrait.
    echo.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %*
set "CODE=%ERRORLEVEL%"

echo.
if "%CODE%"=="0" (
    echo [AVAStack] installeur termine ^(code 0^).
) else (
    echo [AVAStack] installeur termine AVEC ERREUR ^(code %CODE%^).
    echo [AVAStack] Relis les messages ci-dessus : ils donnent la cause exacte.
)
echo.
pause
exit /b %CODE%
