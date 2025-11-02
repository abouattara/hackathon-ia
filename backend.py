#UploadFile sera utilisé pour la gestion des fichiers téléchargés via le formulaire
#File pour déclarer des paramètres comme fichiers téléchargés
#Form pour déclarer des paramètres comme des données de formulaire
#Optional indique qu'une variable peut être d'un certain type ou non
#Shutil va nous permettre de déplacer ou copier les fichiers téléchargés
#os va nous permettre d'interagir avc notre système (créer des dossiers, supprimer, ...)
# notre application sera donc amener à gérer des formulaires, des fichiers téléchargés et à effectuer 
#des opérations de manipulation de fichiers
LLAMA_API_URL = "http://localhost:11434/api/generate"
LLAMA_MODEL_NAME = "llama3"
from fastapi import FastAPI, Form, UploadFile, File
from typing import Optional
import shutil
import os
import time
import requests

## --- Configuration pour le traitement des fichiers ---
## Chemin temporaire pour stocker les fichiers reçus

UPLOAD_DIR = "uploaded_files"
os.makedirs(UPLOAD_DIR, exist_ok=True) 
# -------------------------------------------------------------
#   Initialisation
#---------------------------------------------------------------
app = FastAPI(title="Service Administratif")

# -------------------------------------------------------------
# Traitement 
# -------------------------------------------------------------

#cette fonction va consister à convertir les fichiers non textuels en texte pour notre modèle pour 
#pourra ensuite lire et générer une reponse

def treatment(filepath: str) -> str:
    filename = os.path.basename(filepath)
    time.sleep(1.5)

    if filename.endswith(('.doc', '.docx', '.pdf')):
        return f"Le document '{filename}' a été extrait"
    elif filename.endswith(('.jpg', '.png', '.jpeg')):
        return f"L'image '{filename}' a été analysée"
    elif filename.endswith('.wav'):
        return f"L'enregistrement audio a été transcrit"
    
    return f"Fichier '{filename}' traité avec succès"

# -----------------------------------------------------------
# Definition de l'endpoint
# ------------------------------------------------------------

@app.post("/multiquery/")

async def requete_multimodal(
    query: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    context = ""

    if file:
        file_location = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_location, "wb") as f:
            shutil.copyfileobj(file.file, f)

        context = treatment(file_location)
        os.remove(file_location)

    if not query:
        final_prompt = f"L'utilisateur a fourni un fichier. Contexte intégré : {context}. Quelle est l'information principale de ce fichier ?"
    else:
        final_prompt = (
            f"Question de l'utilisateur : '{query}'."
            f"Contextes supplémentaires fournis par le fichier : {context}."
            "Reponds à la question en utilisant ce contexte"
        )

    try:
        payload = {
            "model" : LLAMA_MODEL_NAME,
            "prompt" : final_prompt,
            "stream" : False 
        }
        
        response = requests.post(LLAMA_API_URL, json=payload)
        response.raise_for_status()

        data = response.json()
        rag_response = data.get("response", "Erreur: Réponse llama vide.")

    except requests.exceptions.RequestException as e:
        rag_response = f"Erreur de connexion à l'API llama: {e}"

    except Exception as e:
        rag_response = f"Erreur inattendue lors du traitement llama: {e}"

    return {"status": "success", "response": rag_response}