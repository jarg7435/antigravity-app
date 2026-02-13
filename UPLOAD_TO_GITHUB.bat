@echo off
echo ===================================================
echo 🚀 PREPARANDO SUBIDA A GITHUB
echo ===================================================
echo.
echo 1. Inicializando repositorio...
git init
git add .
git commit -m "Initial commit for Streamlit Cloud"
echo.
echo 2. Renombrando rama a 'main'...
git branch -M main
echo.
echo 3. Vinculando con tu cuenta GitHub...
echo.
echo ⚠️ IMPORTANTE:
echo Ahora, ve a https://github.com/new y crea un repositorio llamado 'antigravity-app'.
echo NO marques la casilla de "Add a README file".
echo.
set /p REPO_URL="Pega aqui la URL de tu nuevo repositorio (ej: https://github.com/jarg7435/antigravity-app.git): "
echo.
git remote add origin %REPO_URL%
git push -u origin main
echo.
echo ✅ Cdigo subido con exito.
echo Ahora ve a https://share.streamlit.io/ y despliega el repositorio.
pause
