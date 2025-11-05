import streamlit as st
import pytesseract
import speech_recognition as sr
from PIL import Image
import io
import base64
from typing import List, Dict
import time

# Configuration de la page
st.set_page_config(
    page_title="RAG Assistant",
    page_icon="🤖",
    layout="wide"
)

# Initialisation de la session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = []
if "processing" not in st.session_state:
    st.session_state.processing = False

# Fonction pour simuler la réponse du modèle (à remplacer par notre backend RAG)
#=============================================================================
import requests

from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class RAGResponse:
    answer: str
    sources: List[Dict]
    
def get_rag_response(query: str, context_files: List = None) -> RAGResponse:
    """
    Fonction qui envoie la question au backend FastAPI (RAG réel)
    et récupère la réponse générée à partir du corpus.
    """
    try:
        response = requests.post(
            "http://127.0.0.1:8000/ask",
            json={"question": query},
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            
            # Retourner un objet structuré
            return RAGResponse(
                answer=data.get("answer", "Pas de réponse trouvée."),
                sources=data.get("sources", [])
            )
        else:
            return RAGResponse(
                answer=f"⚠️ Erreur du serveur ({response.status_code})",
                sources=[]
            )
    
    except requests.exceptions.ConnectionError:
        return RAGResponse(
            answer="⚠️ Impossible de se connecter au serveur FastAPI. Vérifie qu'il tourne bien avec `uvicorn backend:app --reload`.",
            sources=[]
        )
    except Exception as e:
        return RAGResponse(
            answer=f"⚠️ Erreur: {str(e)}",
            sources=[]
        )

    


# Fonction pour traiter l'audio
def transcribe_audio(audio_file):
    """
    Transcrit un fichier audio en texte
    """
    try:
        recognizer = sr.Recognizer()
        audio_data = sr.AudioFile(audio_file)
        
        with audio_data as source:
            audio = recognizer.record(source)
        
        text = recognizer.recognize_google(audio, language='fr-FR')
        return text
    except Exception as e:
        return f"Erreur de transcription: {str(e)}"

# Fonction pour extraire le texte des images (OCR basique)
def extract_text_from_image(image_file):
    """
    Extrait le texte d'une image (nécessite pytesseract pour un OCR complet)
    """
    try:
        image = Image.open(image_file)
        # Note: Pour un OCR complet, installer pytesseract et utiliser:
        text = pytesseract.image_to_string(image, lang='fra')
        return f"transcription de l'image: {text}"
    except Exception as e:
        return f"Erreur de traitement de l'image: {str(e)}"

# Fonction pour lire les fichiers texte
def read_text_file(file):
    """
    Lit le contenu d'un fichier texte
    """
    try:
        content = file.read()
        if isinstance(content, bytes):
            content = content.decode('utf-8')
        return content
    except Exception as e:
        return f"Erreur de lecture du fichier: {str(e)}"

# Interface principale
st.title("🤖 Assistant Admimistratif")
st.markdown("---")

# Sidebar pour la gestion des documents
with st.sidebar:
    st.header("📁 Gestion des Documents")
    
    # Upload de fichiers
    uploaded_files = st.file_uploader(
        "Charger des documents",
        type=['txt', 'pdf', 'docx', 'jpg', 'png', 'jpeg'],
        accept_multiple_files=True,
        help="Formats supportés: TXT, PDF, DOCX, Images"
    )
    
    if uploaded_files:
        st.session_state.uploaded_files = uploaded_files
        st.success(f"✅ {len(uploaded_files)} fichier(s) chargé(s)")
        
        # Affichage des fichiers chargés
        with st.expander("Voir les fichiers"):
            for file in uploaded_files:
                st.text(f"📄 {file.name} ({file.size} bytes)")
    
    # Upload audio
    st.markdown("---")
    st.subheader("🎙️Entrée Vocale")
    audio_file = st.file_uploader(
        "Charger un fichier audio",
        type=['wav', 'mp3', 'ogg','webm'],
        help="Enregistrez votre question en audio"
    )
    
    if audio_file:
        st.audio(audio_file)
        if st.button("🎯 Transcrire l'audio"):
            with st.spinner("Transcription en cours..."):
                # appel de la fonction de transcription
                transcription = transcribe_audio(audio_file)
                st.session_state.audio_transcription = transcription
                st.success("Transcription terminée!")
    
    # Options
    st.markdown("---")
    st.subheader("⚙️ Paramètres")
    temperature = st.slider("Température", 0.0, 1.0, 0.7, 0.1)
    max_tokens = st.slider("Tokens maximum", 100, 2000, 500, 100)
    
    # Bouton pour effacer l'historique
    if st.button("Effacer l'historique"):
        st.session_state.messages = []
        st.rerun()

# Zone principale de chat
st.header("💬 Conversation")

# Affichage de l'historique des messages
chat_container = st.container()
with chat_container:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            # Affichage des images si présentes
            if "image" in message:
                st.image(message["image"], width=300)

# Zone de saisie
col1, col2 = st.columns([6, 1])

with col1:
    user_input = st.chat_input("Posez votre question ici...")

with col2:
    # Option pour utiliser la transcription audio au lieu du texte
    if "audio_transcription" in st.session_state:
        if st.button("📝 Utiliser transcription"):
            user_input = st.session_state.audio_transcription

# Upload d'image directe dans le chat
uploaded_image = st.file_uploader(
    "📸 Ajouter une image à votre question",
    type=['jpg', 'png', 'jpeg'],
    key="chat_image"
)

# Traitement de la question
# Traitement de la question
if user_input or st.session_state.get("use_transcription"):
    if st.session_state.get("use_transcription"):
        user_input = st.session_state.audio_transcription
        st.session_state.use_transcription = False
    
    # Ajout du message utilisateur
    user_message = {"role": "user", "content": user_input}
    
    if uploaded_image:
        image = Image.open(uploaded_image)
        user_message["image"] = image
        image_info = extract_text_from_image(uploaded_image)
        user_message["content"] += f"\n\n[Image jointe: {image_info}]"
    
    st.session_state.messages.append(user_message)
    
    # Affichage du message utilisateur
    with st.chat_message("user"):
        st.markdown(user_input)
        if uploaded_image:
            st.image(image, width=300)
    
    # Génération de la réponse
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        # Génération de la réponse du RAG
        with st.spinner("🔍 Recherche dans les documents..."):
            response = get_rag_response(
                user_input, 
                st.session_state.uploaded_files
            )
        
        # Effet de streaming pour la réponse
        with st.spinner("✍️ Génération de la réponse..."):
            # Affichage progressif de la réponse
            for chunk in response.answer.split():
                full_response += chunk + " "
                time.sleep(0.03)
                message_placeholder.markdown(full_response + "▌")
            
            # Affichage final de la réponse
            message_placeholder.markdown(full_response)
        
        # Affichage des sources trouvées
        if response.sources and len(response.sources) > 0:
            with st.expander(f"📚 Voir les sources ({len(response.sources)} document(s) trouvé(s))"):
                st.markdown("### 📑 Documents utilisés pour générer la réponse\n")
                
                for source in response.sources:
                    # Affichage de chaque source avec son numéro
                    st.markdown(f"**[{source['index']}]** — Score de pertinence: {source.get('similarity', 0):.2%}")
                    
                    # Métadonnées du document (si disponibles)
                    metadata = source.get('metadata', {})
                    if metadata:
                        if 'filename' in metadata:
                            st.caption(f"📄 Fichier: {metadata['filename']}")
                        if 'page' in metadata:
                            st.caption(f"📖 Page: {metadata['page']}")
                    
                    # Extrait du contenu
                    st.markdown(f"```\n{source['content']}\n```")
                    st.markdown("---")
        else:
            with st.expander("📚 Voir les sources"):
                st.info("ℹ️ Aucune source spécifique trouvée pour cette réponse.")
    
    # Ajout de la réponse à l'historique
    st.session_state.messages.append({
        "role": "assistant",
        "content": full_response
    })
    
    # Réinitialiser l'état
    st.rerun()
# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center'>
        <p>💡 Astuce: Uploadez des documents dans la sidebar pour enrichir le contexte</p>
    </div>
    """,
    unsafe_allow_html=True
)