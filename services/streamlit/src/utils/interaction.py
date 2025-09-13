import time
import logging
from typing import Optional, Dict, Any, Tuple
import requests
import streamlit as st
from fastapi import UploadFile, File
from queue import Queue
import threading

logger = logging.getLogger(__name__)

def manager_input(
    user_input: Dict[str, Any] | None,
    recorded_audio: Optional[UploadFile],
    *,  # Obliga a usar keywords para los siguientes argumentos
    asr_transcription_url: str,
    asr_timeout: int,
    language: Optional[str] = None
) -> Optional[str]:
    ## Procesar entrada del usuario (texto y/o audio)
    text_input = None
    ## ------------------------------------------
    ## CASO 1: Si el usuario envía solo texto
    ## ------------------------------------------
    if user_input and user_input["text"] and not user_input["files"]:
        # Guardar en session_state
        st.session_state['last_text_input'] = user_input['text']
        st.session_state['last_audio_input'] = ''
        st.session_state['last_transcription_time'] = ''
        # Mostrar y guardar en historial
        # 1) Añadir al historial primero
        st.session_state.chat_history.append({"role": "user", "content": st.session_state['last_text_input']})
        # 2) Pintar
        st.chat_message("user").write(st.session_state['last_text_input'])
        # Devolver texto procesado
        text_input = st.session_state['last_text_input']
    ## ------------------------------------------
    ## CASO 2: Si el usuario adjunta un archivo de audio
    ## ------------------------------------------
    elif user_input and user_input["files"] and not user_input["text"]:
        # Preparamos el input de la transcripción
        audio_name = user_input["files"][0].name
        audio_file = user_input["files"][0]
        audio_type = user_input["files"][0].type
        if hasattr(audio_file, "read"):
            audio_bytes = audio_file.read()
            st.audio(audio_bytes, format=audio_type)
            if hasattr(audio_file, "seek"):
                audio_file.seek(0)
        else:
            st.warning("Could not get audio to play.")

        # Transcribimos el audio
        result = transcribe_audio(audio_name, audio_file, audio_type, asr_transcription_url=asr_transcription_url, asr_timeout=asr_timeout, language=language)
        if not result:
            return None
        transcription_text, transcription_time = result
        # Guardamos en session_state
        st.session_state['last_text_input'] = ''
        st.session_state['last_audio_input'] = transcription_text
        if not st.session_state['last_audio_input']:
            raise ValueError("Audio upload could not be transcribed.")
        st.session_state['last_transcription_time'] = f"{transcription_time:.1f}"
        # 1) Añadir al historial primero
        user_msg = f"[Audio]: {st.session_state['last_audio_input']}".strip()
        st.session_state.chat_history.append({"role": "user", "content": user_msg})
        # 2) Pintar
        st.chat_message("user").write(user_msg)
        st.info(f"Transcription time: {st.session_state['last_transcription_time']} seconds", icon="⏱️")
        # Devolver texto procesado
        text_input = st.session_state['last_audio_input']
    ## ------------------------------------------
    ## CASO 3: Si el usuario sube audio y texto, los combinamos
    ## ------------------------------------------
    elif user_input and user_input["text"] and user_input["files"]:
        # Preparamos el input de la transcripción
        audio_name = user_input["files"][0].name
        audio_file = user_input["files"][0]
        audio_type = user_input["files"][0].type
        if hasattr(audio_file, "read"):
            audio_bytes = audio_file.read()
            st.audio(audio_bytes, format=audio_type)
            audio_file.seek(0)
        else:
            st.warning("Could not get audio to play.")
        
        # Transcribimos el audio
        result = transcribe_audio(audio_name, audio_file, audio_type, asr_transcription_url=asr_transcription_url, asr_timeout=asr_timeout, language=language)
        if not result:
            return None
        transcription_text, transcription_time = result
        # Guardamos en session_state
        st.session_state['last_text_input'] = user_input['text']
        st.session_state['last_audio_input'] = transcription_text
        # Mostrar también el texto escrito en el historial del chat y guardamos resultado
        if not st.session_state['last_audio_input']:
            st.warning("Audio upload could not be transcribed.")
            st.session_state['last_transcription_time'] = ''
            st.session_state.chat_history.append({"role": "user", "content": st.session_state['last_text_input']})
            st.chat_message("user").write(st.session_state['last_text_input'])
            text_input = st.session_state['last_text_input']
        else:
            st.session_state['last_transcription_time'] = f"{transcription_time:.1f}"
            # Para History: guarda con salto markdown "two spaces + \\n"
            user_msg_hist = f"[Audio]: {st.session_state['last_audio_input']}  \n[Input]: {st.session_state['last_text_input']}"
            st.session_state.chat_history.append({"role": "user", "content": user_msg_hist})
            # Para el bubble actual: dos writes en el mismo contenedor
            msg = st.chat_message("user").write(user_msg_hist)
            st.info(f"Transcription time: {st.session_state['last_transcription_time']} seconds", icon="⏱️")
            text_input = f"{st.session_state['last_text_input']} and {st.session_state['last_audio_input']}"
    ## ------------------------------------------
    ## CASO 4: Si el usuario graba audio, lo transcribimos y lo añadimos al historial
    ## ------------------------------------------
    elif recorded_audio and not user_input:
        # Preparar el input de la transcripción
        audio_name = recorded_audio.name
        audio_file = recorded_audio
        audio_type = recorded_audio.type
        
        # Transcribimos el audio        
        result = transcribe_audio(audio_name, audio_file, audio_type, asr_transcription_url=asr_transcription_url, asr_timeout=asr_timeout, language=language)
        if not result:
            return None
        transcription_text, transcription_time = result
        audio_file.seek(0)
        # Guardamos en session_state
        st.session_state['last_text_input'] = ''
        st.session_state['last_audio_input'] = transcription_text
        if not st.session_state['last_audio_input']:
            raise ValueError("Audio upload could not be transcribed.")
        st.session_state['last_transcription_time'] = f"{transcription_time:.1f}"
        # 1) Añadir al historial primero
        user_msg = f"[Audio]: {st.session_state['last_audio_input']}".strip()
        st.session_state.chat_history.append({"role": "user", "content": user_msg})
        # 2) Pintar
        st.chat_message("user").write(user_msg)
        st.info(f"Transcription time: {st.session_state['last_transcription_time']} seconds", icon="⏱️")
        # Devolver texto procesado
        text_input = st.session_state['last_audio_input']
    return text_input

def query_services(
    user_input: str,
    *,
    rag_url: str,
    agent_react_url: str,
    rag_timeout: int = 60,
    agent_timeout: int = 60,
) -> Dict[str, Any]:
    """Query RAG and Agent React services in parallel and render results.

    Args:
        user_input: The text to query (typed or transcribed).
        rag_url: Endpoint for the RAG service.
        agent_react_url: Endpoint for the Agent React service.
        rag_timeout: Timeout in seconds for RAG request.
        agent_timeout: Timeout in seconds for Agent React request.

    Returns:
        Dict[str, Any]:
            - rag_answer (str)
            - rag_status (str | None)
            - rag_time (float | None)
            - agent_answer (str)
            - agent_status (str | None)
            - agent_time (float | None)
            - input_text (str)
            - input_audio (str)
            - transcription_time (str)
    """
    col_rag, col_agent = st.columns(2)
    rag_placeholder = col_rag.empty()
    agent_placeholder = col_agent.empty()

    queue: "Queue[tuple[str, Optional[Dict[str, Any]], Optional[str], Optional[str], Optional[float]]]" = Queue()

    def fetch_rag_async(text: str, q: Queue):
        try:
            logger.info(f"Enviando consulta a RAG: {text}")
            start_rag = time.time()
            response_rag = requests.post(rag_url, json={"transcription": text}, timeout=rag_timeout)
            response_rag.raise_for_status()
            end_rag = time.time()
            rag_json = response_rag.json()
            status = rag_json.get("status", "")
            resp = rag_json.get("response", {})
            q.put(("rag", resp, status, None, end_rag - start_rag))
        except requests.Timeout:
            q.put(("rag", None, "timeout", "Request to RAG timed out", None))
        except Exception as e:
            q.put(("rag", None, None, str(e), None))

    def fetch_agent_async(text: str, q: Queue):
        try:
            logger.info(f"Enviando consulta a Agent React: {text}")
            start_agent = time.time()
            response_agent = requests.post(agent_react_url, json={"transcription": text}, timeout=agent_timeout)
            response_agent.raise_for_status()
            end_agent = time.time()
            agent_json = response_agent.json()
            status = agent_json.get("status", "")
            resp = agent_json.get("response", {})
            q.put(("agent", resp, status, None, end_agent - start_agent))
        except requests.Timeout:
            q.put(("agent", None, "timeout", "Request to Agent React timed out", None))
        except Exception as e:
            q.put(("agent", None, None, str(e), None))

    thread_rag = threading.Thread(target=fetch_rag_async, args=(user_input, queue))
    thread_agent = threading.Thread(target=fetch_agent_async, args=(user_input, queue))
    thread_rag.start()
    thread_agent.start()

    # Placeholders with initial state
    with rag_placeholder.container():
        st.subheader("RAG")
        st.info("Waiting for RAG response...")
    with agent_placeholder.container():
        st.subheader("Agent React")
        st.info("Waiting for Agent React response...")

    rag_answer: Optional[str] = None
    rag_status: Optional[str] = None
    rag_time: Optional[float] = None

    agent_answer: Optional[str] = None
    agent_status: Optional[str] = None
    agent_time: Optional[float] = None

    for _ in range(2):
        who, resp, status, error, elapsed = queue.get()
        if who == "rag":
            rag_answer = resp.get("answer", "") if resp else ""
            rag_status = status
            rag_time = elapsed
            rag_placeholder.empty()
            with rag_placeholder.container():
                st.subheader("RAG")
                if error:
                    if status == "timeout":
                        st.warning("RAG took too long. Please try again or refine your query.")
                    else:
                        st.error("RAG error while fetching response.")
                    logger.exception(f"Error en RAG: {error}")
                    st.session_state.chat_history.append({"role": "assistant", "content": f"[RAG] Error: {error}"})
                else:
                    st.chat_message("assistant").write(rag_answer)
                    st.session_state.chat_history.append({"role": "assistant", "content": f"[RAG] {rag_answer}"})
                    with st.expander("RAG Details", expanded=False):
                        st.markdown(f"**🟢 Status:** {rag_status}")
                        st.markdown(f"**📝 Input:** {resp.get('input', '') if resp else ''}")
                        st.markdown(f"**📚 Context:** {resp.get('context', '') if resp else ''}")
                        if rag_time is not None:
                            st.markdown(f"**⏱️ Response Time:** {rag_time:.1f} seconds")
        elif who == "agent":
            agent_answer = resp.get("output", "") if resp else ""
            agent_status = status
            agent_time = elapsed
            agent_placeholder.empty()
            with agent_placeholder.container():
                st.subheader("Agent React")
                if error:
                    if status == "timeout":
                        st.warning("Agent React took too long. Please try again or refine your query.")
                    else:
                        st.error("Agent React error while fetching response.")
                    logger.exception(f"Error en Agent React: {error}")
                    st.session_state.chat_history.append({"role": "assistant", "content": f"[Agent React] Error: {error}"})
                else:
                    st.chat_message("assistant").write(agent_answer)
                    st.session_state.chat_history.append({"role": "assistant", "content": f"[Agent React] {agent_answer}"})
                    with st.expander("Agent React Details", expanded=False):
                        st.markdown(f"**🟢 Status:** {agent_status}")
                        st.markdown(f"**📝 Input:** {resp.get('input', '') if resp else ''}")
                        if resp and 'context' in resp:
                            st.markdown(f"**📚 Context:** {resp.get('context', '')}")
                        if agent_time is not None:
                            st.markdown(f"**⏱️ Agent React Response Time:** {agent_time:.1f} seconds")

    return {
        'rag_answer': rag_answer or '',
        'rag_status': rag_status,
        'rag_time': rag_time,
        'agent_answer': agent_answer or '',
        'agent_status': agent_status,
        'agent_time': agent_time,
        'input_text': user_input,
        'input_audio': st.session_state.get('last_audio_input', ''),
        'transcription_time': st.session_state.get('last_transcription_time', '')
    }


def transcribe_audio(
    audio_name: str = "default_audio",
    audio_file: UploadFile = File(...),
    audio_type: str = "audio/wav",
    asr_transcription_url: str = "",
    asr_timeout: int = 300,
    language: Optional[str] = None,
) -> Optional[Tuple[str, float]]:
    """Send audio to ASR, play it, and persist transcription context.

    Args:
        audio_name: Filename to send in multipart.
        audio_file: Audio file object.
        audio_type: MIME type of audio.
        asr_transcription_url: Endpoint for ASR transcription.
        asr_timeout: Timeout in seconds for ASR request.
        language: Optional ISO code; None for auto-detect.

    Returns:
        (text, elapsed_seconds) on success; None otherwise.
    """
    try:
        files = {"file": (audio_name, audio_file, audio_type)}    
        data = {"language": language} if language else None
        start_transcription = time.time()
        response = requests.post(asr_transcription_url, files=files, data=data, timeout=asr_timeout)
        response.raise_for_status()
        end_transcription = time.time()
        transcribed = response.json().get("transcription")
        transcription_time = end_transcription - start_transcription
        logger.info(f"Transcripción recibida: {transcribed}")
        return transcribed, transcription_time
    except requests.Timeout:
        logger.exception("Timeout en transcripción de audio")
        st.warning("ASR took too long. Please try again or reduce audio length.")
        return None
    except Exception as e:
        logger.exception(f"Error en transcripción de audio: {e}")
        st.error("Error while transcribing audio.")
        return None

def fetch_supported_languages(asr_languages_url: str, asr_timeout: int = 60) -> Dict[str, Optional[str]]:
    """
    Obtiene Name->Code desde el micro ASR (sin parámetros).

    Args:
        asr_languages_url: URL completa al endpoint /languages.
        asr_timeout: Timeout de la petición en segundos.

    Returns:
        Dict[str, str]: Mapa nombre->código. Si falla, usa fallback local.
    """
    try:
        resp = requests.get(asr_languages_url.rstrip("/"), params=None, timeout=asr_timeout)
        resp.raise_for_status()
        data = resp.json() or {}
        if data.get("status") == "success":
            langs = data.get("languages", "")
            if isinstance(langs, dict) and langs:
                return langs
        else:
            raise ValueError("Error en la respuesta del ASR, el status no es 'success'")
    except requests.Timeout:
        logger.warning("Timeout al obtener idiomas del ASR")
    except Exception as e:
        logger.error(f"Error al obtener idiomas soportados: {e}", exc_info=True)

    # Fallback local (sin red)
    try:
        from whisper.tokenizer import LANGUAGES, TO_LANGUAGE_CODE
        mapping = {name.title(): code for code, name in LANGUAGES.items()}
        for alias_name, code in TO_LANGUAGE_CODE.items():
            mapping.setdefault(alias_name.title(), code)
        return dict(sorted(mapping.items(), key=lambda kv: kv[0]))
    except Exception:
        return {}