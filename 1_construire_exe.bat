@echo off
REM ============================================================
REM   Construction de SuiviHDV
REM   Genere dist\SuiviHDV\ (dossier complet, moins suspect AV)
REM ============================================================

echo.
echo === Etape 1/3 : installation des outils ===
python -m pip install --upgrade pip
python -m pip install pyinstaller pywebview

echo.
echo === Etape 2/3 : construction de l'executable ===
cd app
pyinstaller --noconfirm --onedir --windowed ^
  --name "SuiviHDV" ^
  --icon "icon.ico" ^
  --add-data "icon.ico;." ^
  --add-data "web;web" ^
  --hidden-import "webview.platforms.winforms" ^
  --collect-all webview ^
  main_web.py

echo.
echo === Etape 3/3 : recuperation du resultat ===
cd ..
if exist "app\dist\SuiviHDV\SuiviHDV.exe" (
    if exist "dist\SuiviHDV" rmdir /S /Q "dist\SuiviHDV"
    if not exist "dist" mkdir dist
    xcopy /E /Y /I "app\dist\SuiviHDV" "dist\SuiviHDV" > nul
    echo.
    echo TERMINE ^! Votre application est ici : dist\SuiviHDV\
) else (
    echo ERREUR : la construction a echoue. Lisez les messages ci-dessus.
)
echo.
pause
