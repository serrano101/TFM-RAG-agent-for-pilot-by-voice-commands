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

    # Crear cola    [who, status_code, status, error,            resp,                 elapsed]
    queue: "Queue[tuple[str, float, str, Optional[str], Optional[Dict[str, Any]], Optional[float]]]" = Queue()

    def fetch_rag_async(text: str, q: Queue):
        try:
            logger.info(f"Enviando consulta a RAG: {text}")
            start_rag = time.time()
            response_rag = requests.post(rag_url, json={"transcription": text}, timeout=rag_timeout)
            # response_rag.raise_for_status()
            end_rag = time.time()
            time_response = end_rag - start_rag
            rag_json = response_rag.json()
            status_code = response_rag.status_code
            if status_code == 200:                
                status = rag_json.get("status", "success")
                error_message = None
                resp = rag_json.get("response", {})
            elif status_code == 422:
                status = rag_json.get("status", "no_results")
                error_message = rag_json.get("message", "No relevant documents found.")
                resp = rag_json.get("response", {})    
            else:
                status = rag_json.get("status", "unknown_error")
                error_message = rag_json.get("message", f"HTTP {status_code}")
                resp = rag_json.get("response", None)
            q.put(("rag", status_code, status, error_message, resp, time_response))
        except requests.Timeout:
            q.put(("rag", 500, "timeout", "Request to RAG timed out", None, None))
        except Exception as e:
            q.put(("rag", 500, "unknown_error", str(e), None, None))

    def fetch_agent_async(text: str, q: Queue):
        try:
            logger.info(f"Enviando consulta a Agent React: {text}")
            start_agent = time.time()
            response_agent = requests.post(agent_react_url, json={"transcription": text}, timeout=agent_timeout)
            # response_agent.raise_for_status()
            end_agent = time.time()
            time_response = end_agent - start_agent
            agent_json = response_agent.json()
            status_code = response_agent.status_code
            if status_code == 200:                
                status = agent_json.get("status", "success")
                error_message = None
                resp = agent_json.get("response", {})
            else:
                status = agent_json.get("status", "unknown_error")
                error_message = agent_json.get("message", f"HTTP {status_code}")
                resp = agent_json.get("response", None)
            q.put(("agent", status_code, status, error_message, resp, time_response))
        except requests.Timeout:
            q.put(("agent", 500, "timeout", "Request to Agent React timed out", None, None))
        except Exception as e:
            q.put(("agent", 500, "unknown_error", str(e), None, None))

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
        who, status_code, status, error_message, resp, elapsed = queue.get()
        if who == "rag":
            # resp = {input: , context: , answer: }
            rag_status_code = status_code
            rag_status = status
            rag_error_message = error_message
            rag_answer = resp.get("answer", "") if resp else "" 
            rag_input = resp.get("input", "") if resp else ""
            rag_context = resp.get("context", "") if resp else ""            
            rag_time = elapsed
            rag_placeholder.empty()
            with rag_placeholder.container():
                st.subheader("RAG")
                if rag_status_code == 200: # Caso éxito
                    st.chat_message("assistant").write(rag_answer)
                    st.session_state.chat_history.append({"role": "assistant", "content": f"[RAG] {rag_answer}"})
                    with st.expander("RAG Details", expanded=False):
                        st.markdown(f"**ℹ️ Status code:** {rag_status_code}")
                        st.markdown(f"**🟢 Status:** {rag_status}")
                        st.markdown(f"**📝 Input:** {rag_input}")
                        st.markdown(f"**📚 Context:** {rag_context}")
                        if rag_time is not None:
                            st.markdown(f"**⏱️ Response Time:** {rag_time:.1f} seconds")
                elif rag_status_code == 422: # Caso que no hay resultados
                    st.chat_message("assistant").write(rag_error_message)
                    st.session_state.chat_history.append({"role": "assistant", "content": f"[RAG] {rag_error_message}"})
                    with st.expander("RAG Details", expanded=False):
                        st.markdown(f"**ℹ️ Status code:** {rag_status_code}")
                        st.markdown(f"**🟡 Status:** {rag_status}")
                        st.markdown(f"**📝 Input:** {rag_input}")
                        st.markdown(f"**➡️ Answer:** {rag_answer}")
                        st.markdown(f"**📚 Context:** {rag_context}")
                        if rag_time is not None:
                            st.markdown(f"**⏱️ Response Time:** {rag_time:.1f} seconds")
                else: # Error de otros tipos
                    st.error(rag_error_message)
                    with st.expander("RAG Details", expanded=False):
                        st.markdown(f"**ℹ️ Status code:** {rag_status_code}")
                        st.markdown(f"**🔴 Status:** {rag_status}")
                    logger.exception(f"Error en RAG: {rag_error_message}")
                    st.session_state.chat_history.append({"role": "assistant", "content": f"[RAG] Error: {rag_error_message}"})

        elif who == "agent":
            # resp = {input: , output: }
            agent_status_code = status_code
            agent_status = status
            agent_error_message = error_message
            agent_answer = resp.get("output", "") if resp else "" 
            agent_input = resp.get("input", "") if resp else ""
            agent_context = resp.get("context", "") if resp else "" # Por ahora no existe
            agent_time = elapsed
            agent_placeholder.empty()
            with agent_placeholder.container():
                st.subheader("Agent ReAct")
                if agent_status_code == 200: # Caso éxito
                    st.chat_message("assistant").write(agent_answer)
                    st.session_state.chat_history.append({"role": "assistant", "content": f"[Agent ReAct] {agent_answer}"})
                    with st.expander("Agent ReAct Details", expanded=False):
                        st.markdown(f"**ℹ️ Status code:** {agent_status_code}")
                        st.markdown(f"**🟢 Status:** {agent_status}")
                        st.markdown(f"**📝 Input:** {agent_input}")
                        if agent_time is not None:
                            st.markdown(f"**⏱️ Response Time:** {agent_time:.1f} seconds")            
                else: # Error de otros tipos
                    st.error(agent_error_message)
                    with st.expander("Agent ReAct Details", expanded=False):
                        st.markdown(f"**ℹ️ Status code:** {agent_status_code}")
                        st.markdown(f"**🔴 Status:** {agent_status}")
                    logger.exception(f"Error en Agent ReAct: {agent_error_message}")
                    st.session_state.chat_history.append({"role": "assistant", "content": f"[Agent ReAct] Error: {agent_error_message}"})

    return {
        'rag_status_code': rag_status_code,
        'rag_status': rag_status,
        'rag_error_message': rag_error_message,        
        'rag_answer': rag_answer or '',
        'rag_context': rag_context,
        'rag_time': rag_time,
        'agent_status_code': agent_status_code,
        'agent_status': agent_status,
        'agent_error_message': agent_error_message,
        'agent_answer': agent_answer or '',
        'agent_context': agent_context,
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
        # response.raise_for_status()
        end_transcription = time.time()
        transcription_time = end_transcription - start_transcription
        response_data = response.json()
        status_code = response.status_code
        if status_code != 200:
            error_message = response_data.get("message", "unknown error")
            logger.error(f"Error en transcripción de audio: {error_message}")
            st.error(f"{status_code} - Error while transcribing audio: {error_message}")
            return None
        logger.info(f"Transcripción recibida: {response_data.get('transcription', '')}")
        return response_data.get('transcription', ''), transcription_time
    except requests.Timeout:
        logger.exception("Timeout en transcripción de audio")
        st.warning("ASR took too long. Please try again or reduce audio length.")
        return None
    except Exception as e:
        logger.exception(f"Error en transcripción de audio: {e}")
        st.error("Error while transcribing audio.")
        return None

def fetch_supported_languages(
        asr_languages_url: str, 
        asr_timeout: int = 60
) -> Dict[str, Optional[str]]:
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
        # resp.raise_for_status()
        data = resp.json()
        if resp.status_code == 200:
            langs = data.get("languages", "")
            if isinstance(langs, dict) and langs:
                return langs
        else:
            raise ValueError("Error en la respuesta del ASR, el status no es 'success'")
    except requests.Timeout:
        logger.warning("Timeout al obtener idiomas del ASR")
    except Exception as e:
        logger.error(f"Error al obtener idiomas soportados: {e}", exc_info=True)        