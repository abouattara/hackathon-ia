@echo off
echo === Installation des dépendances Python ===


echo === Lancement du backend (Uvicorn) ===
start cmd /k "uvicorn backend:app --reload"

echo === Lancement du frontend (Streamlit) ===
start cmd /k "streamlit run frontend/frontend.py"

echo === Applications lancees ===
pause
