import json
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings

class RAGSystem:
    def __init__(self):
        # 1. Modèle d'embeddings
        self.embedding_model = SentenceTransformer(
            'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
        )

        # 2. Base vectorielle ChromaDB
        self.chroma_client = chromadb.Client(Settings(
            anonymized_telemetry=False,
            allow_reset=True
        ))
        self.collection = self.chroma_client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"}
        )
        
        # 3. Prompt système pour guider le LLM
        self.system_prompt = """Tu es un assistant expert qui répond aux questions en te basant UNIQUEMENT sur les documents fournis.

Instructions IMPORTANTES :
- Cite TOUJOURS tes sources en utilisant [1], [2], [3] etc. immédiatement après chaque information
- Les numéros [1], [2], [3] correspondent exactement aux documents fournis ci-dessous
- Organise ta réponse en paragraphes clairs et bien structurés
- Si une information vient de plusieurs sources, cite-les toutes : [1][2]
- Si tu ne trouves pas l'information dans les documents, dis-le clairement
- Ne fabrique JAMAIS d'information qui n'est pas dans les documents

Exemple de réponse attendue :
"Le terme 'intelligence artificielle' désigne la capacité d'une machine à imiter l'intelligence humaine [1]. Elle englobe plusieurs domaines comme l'apprentissage automatique et le traitement du langage naturel [2]. Les applications de l'IA sont variées et incluent la reconnaissance d'image et la traduction automatique [1][3]."
"""

        # 4. Configuration du LLM (choisir une option)
        # Option A : Ollama (local, gratuit)
        #self.llm_client = "ollama"  # Nécessite Ollama installé
        # self.model_name = "mistral"  # ou "llama3", "gemma2", etc.
        
        # Option B : OpenAI
        # from openai import OpenAI
        # self.llm_client = OpenAI(api_key="votre_cle_api")
        # self.model_name = "gpt-4o-mini"
        
        # Option C : Anthropic Claude
        # from anthropic import Anthropic
        # self.llm_client = Anthropic(api_key="votre_cle_api")
        # self.model_name = "claude-3-5-sonnet-20241022"
        
        # Pour l'exemple, je mets Ollama (local)
        self.llm_client = "ollama"
        self.model_name = "mistral"

    def add_documents(self, documents):
        embeddings = self.embedding_model.encode(
            documents,
            show_progress_bar=True,
            convert_to_numpy=True
        )
        ids = [f"doc_{i}" for i in range(len(documents))]
        metadatas = [{"source": f"document_{i}"} for i in range(len(documents))]
        self.collection.add(
            embeddings=embeddings.tolist(),
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

    def search_similar(self, query, n_results=3):
        query_embedding = self.embedding_model.encode([query], convert_to_numpy=True)
        results = self.collection.query(
            query_embeddings=query_embedding.tolist(),
            n_results=n_results
        )
        return results
    
    def generate_answer_with_llm(self, question, documents):
        """
        Génère une réponse avec un LLM en citant les sources
        """
        # Construction du contexte avec numéros
        context = ""
        for i, doc in enumerate(documents, 1):
            context += f"\n[{i}] {doc}\n"
        
        # Prompt complet
        user_prompt = f"""Documents de référence :
{context}

Question de l'utilisateur : {question}

Réponds à la question en citant tes sources avec [1], [2], [3] :"""

        # Appel au LLM selon la configuration
        if self.llm_client == "ollama":
            # Avec Ollama (local)
            import requests
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": f"{self.system_prompt}\n\n{user_prompt}",
                    "stream": False
                }
            )
            answer = response.json().get("response", "Erreur de génération")
        else:
            answer = "LLM non configuré"
        
        return answer

    def query(self, question, n_results=3):
        """
        Méthode principale pour interroger le RAG
        """
        # 1. Recherche vectorielle des documents pertinents
        results = self.search_similar(question, n_results)

        if not results['documents'][0]:
            return {
                "answer": "Aucun document pertinent trouvé dans la base de données.",
                "sources": []
            }

        documents = results['documents'][0]
        metadatas = results['metadatas'][0]
        distances = results['distances'][0]

        # 2. Génération de la réponse avec le LLM
        try:
            answer = self.generate_answer_with_llm(question, documents)
        except Exception as e:
            # Fallback si le LLM échoue
            answer = f"Erreur lors de la génération : {str(e)}\n\n"
            answer += "Documents trouvés :\n"
            for i, doc in enumerate(documents, 1):
                answer += f"[{i}] {doc[:300]}...\n\n"

        # 3. Préparation des sources avec index
        sources = [
            {
                "index": i + 1,
                "content": doc,
                "metadata": meta,
                "similarity": (1 - dist) * 100  # Convertir distance en pourcentage
            }
            for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances))
        ]

        return {
            "answer": answer,
            "sources": sources
        }
