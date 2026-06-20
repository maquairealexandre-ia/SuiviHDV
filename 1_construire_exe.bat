@echo off
REM ============================================================
REM   Construction de SuiviHDV
REM   Genere dist\SuiviHDV.exe (autonome, sans Python)
REM ============================================================

echo.
echo === Etape 1/3 : installation des outils ===
python -m pip install --upgrade pip
python -m pip install pyinstaller pywebview

echo.
echo === Etape 2/3 : construction de l'executable ===
cd app
pyinstaller --noconfirm --onefile --windowed ^
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
if exist "app\dist\SuiviHDV.exe" (
    if not exist "dist" mkdir dist
    copy /Y "app\dist\SuiviHDV.exe" "dist\SuiviHDV.exe"
    echo.
    echo TERMINE ^! Votre application est ici : dist\SuiviHDV.exe
) else (
    echo ERREUR : la construction a echoue. Lisez les messages ci-dessus.
)
echo.
pause
