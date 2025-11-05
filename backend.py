from fastapi import FastAPI
from pydantic import BaseModel
import json
from bs4 import BeautifulSoup
from src.rag_system import RAGSystem  # Assure-toi que rag_system.py est dans le même dossier

app = FastAPI(title="RAG Local JSON Optimisé")

# -------------------------------
# Charger le JSON (ta base de connaissances)
# -------------------------------
with open("data/corpus.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# -------------------------------
# Fonction de nettoyage HTML
# -------------------------------
def clean_html(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    return soup.get_text(separator=" ", strip=True)

# -------------------------------
# Préparer les documents
# -------------------------------
documents = []
for d in data:
    # Nettoyer le HTML
    raw_text = ""
    if "raw_html" in d:
        try:
            with open(d["raw_html"], "r", encoding="utf-8") as f_html:
                raw_html_content = f_html.read()
                raw_text = clean_html(raw_html_content)
        except FileNotFoundError:
            raw_text = ""
    # Ajouter le contenu du JSON
    content = d.get("content", "")
    # Concaténer et ne garder que le texte utile
    full_text = (raw_text + " " + content).strip()
    if full_text:
        documents.append(full_text)

# -------------------------------
# Initialiser RAG
# -------------------------------
rag = RAGSystem()
rag.add_documents(documents)

# -------------------------------
# Modèle de requête
# -------------------------------
class QuestionRequest(BaseModel):
    question: str

# -------------------------------
# Endpoint pour poser une question
# ------------------------------
@app.post("/ask/")
def ask_question(req: QuestionRequest):
    question = req.question

    # Pipeline RAG complet : recherche + génération
    result = rag.query(question, n_results=3)  # 3 documents comme contexte

    # Retourner réponse synthétique + sources avec index
    return {
        "answer": result["answer"],
        "sources": [
            {
                "index": i + 1,  # Numéro de la source [1], [2], [3]
                "content": doc[:300] + "..." if len(doc) > 300 else doc,
                "similarity": result["sources"][i].get("similarity", 0),
                "metadata": result["sources"][i].get("metadata", {})  # Info du document source
            }
            for i, doc in enumerate(result["sources"])
        ]
    }

