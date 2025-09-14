import logging
from langchain_core.documents import Document

# from src.embedders.sentence_transformers_embedders import Embedder
from src.database.chromadb_repository import VectorDBRepository
from src.llm.ollama_service import LLMClientOllama
from langchain_core.prompts import PromptTemplate
from typing import Optional, Union, List
import json
# Obtiene un logger para el módulo actual
logger = logging.getLogger(__name__)

class RAG:
    def __init__(
        self,
        vector_db: VectorDBRepository,
        llm: LLMClientOllama,
        prompt: Union[str, PromptTemplate],
        output_no_context_answer: str,
        output_not_match_answer_context: str,
        search_type: Optional[str] = None,
        search_kwargs: Optional[dict] = None
    ) -> None:
        """
        Inicializa el RAG con los componentes necesarios.

        Args:
            vector_db (VectorDBRepository): Repositorio vectorial para recuperación de información.
            llm (LLMClientOllama): Cliente LLM para generación de respuestas.
            prompt (PromptTemplate): Prompt para el pipeline RAG.
            search_type (str, opcional): Tipo de búsqueda para el retriever ("similarity", "mmr", "similarity_score_threshold").
            search_kwargs (dict, opcional): Argumentos para el retriever (k, score_threshold, fetch_k, lambda_mult, filter, etc).

        Returns:
            None: No se devuelven valores.

        Raises:
            RuntimeError: Si ocurre un error al inicializar el pipeline RAG.
        """
        try:
            logger.debug("[RAG] Inicializando el RAG...")
            # self.embedder = embedder
            self.vector_db = vector_db
            self.llm = llm
            # Si prompt es string, conviértelo a PromptTemplate
            if isinstance(prompt, str):
                self.prompt = PromptTemplate(input_variables=['context', 'input'], template=prompt)
            else:
                self.prompt = prompt
            self._search_type = search_type
            self._search_kwargs = search_kwargs or {}
            self.output_no_context_answer = output_no_context_answer
            self.output_not_match_answer_context = output_not_match_answer_context

            logger.info("[RAG] Inicializado correctamente.")
        except Exception as e:
            logger.error(f"[RAG] Error al inicializar: {e}", exc_info=True)
            raise RuntimeError(f"Error al inicializar el RAG: {e}")

    def post_process_result(self, result_content: dict, query: str, context_full_streamlit: list[dict]) -> dict:
        """
        Procesa el resultado del modelo para verificar si cumple con los requisitos.

        Args:
            result_content (dict): Respuesta generada por el modelo.
            query (str): Consulta original del usuario.
            context_text (list[dict]): Contexto utilizado para generar la respuesta.

        Returns:
            dict: Diccionario con la estructura de salida procesada.
        """
        try:

            # Verificar si todas las componentes están vacías
            if (
                
                not result_content.get("steps")
            ):
                logger.info("[RAG] La respuesta no coincide con el contexto proporcionado.")
                return {
                    "input": query,
                    "context": context_full_streamlit,
                    "answer": self.output_not_match_answer_context
                }

            # Si tiene al menos una componente no vacía, es exitoso
            return {
                "input": query,
                "context": context_full_streamlit,
                "answer": result_content
            }

        except json.JSONDecodeError as e:
            # Si no es un JSON válido, devolver un error
            logger.warning(f"[RAG] La respuesta no es un JSON válido: {e}")
            raise ValueError("La respuesta del modelo no es un JSON válido.")
        
    def execute(self, query: str) -> str:
        """
        Ejecuta el pipeline RAG para una consulta dada.
        Aplica filtro dinámico en headings usando el LLM.

        Args:
            query (str): Consulta a procesar por el pipeline RAG.

        Returns:
            str: Respuesta generada por el pipeline RAG.

        Raises:
            ValueError: Si la consulta está vacía o es None.
            RuntimeError: Si ocurre un error durante la ejecución del pipeline.
        """
        try:
            logger.info(f"[RAG] Ejecutando RAG para la consulta: {query}")
            if not query or not query.strip():
                logger.error("[RAG] La consulta no puede estar vacía o ser None")
                raise ValueError("La consulta no puede estar vacía o ser None")
            
            # Recupera documentos relevantes
            docs = self.vector_db.search(
                query=query,
                top_k=self._search_kwargs.get("k", 5),
                # search_type=self._search_type,
                # score_threshold=self._search_kwargs,
                return_score=True
            )
            logger.debug(f"[RAG] Documentos recuperados: {len(docs)}")

            # Concatena el contenido de los documentos
            context_text = "\n<other_procedure>\n".join([doc.page_content for doc, _score in docs])
            score_list = []
            score_list.extend(round(_score, 2) for doc, _score in docs)
            
            context_full_streamlit = []
            for doc, _score in docs:
                context_full_streamlit.append({
                    "content": doc.page_content,
                    "score": round(_score, 2)
                })

            # Si no hay documentos, devuelve respuesta por defecto
            if not context_text.strip():
                logger.warning("[RAG] No se encontraron documentos relevantes.")
                return {
                    "input": query,
                    "context": None,
                    "answer": self.output_no_context_answer
                }
            
            # Invocar el modelo LLM
            logger.debug(f"[RAG] Documentos: \n {context_text}")
            result = self.llm.client.invoke(self.prompt.format(input=query, context=context_text))
            logger.debug(f"[RAG] Respuesta del RAG:\n{result}")

            # Convertir result.content a un diccionario o manejarlo como string
            try:
                if isinstance(result.content, str):
                    # Eliminar comillas iniciales y finales si existen
                    cleaned_content = result.content.strip().strip("'")
                    logger.debug(f"[RAG] Respuesta limpia del RAG:\n{cleaned_content}")
                    
                    # Intentar encapsular en un objeto JSON si no es válido
                    if not cleaned_content.startswith("{") and not cleaned_content.startswith("["):
                        cleaned_content = "{" + cleaned_content + "}"
                    
                    # Intentar cargar como JSON
                    result_content = json.loads(cleaned_content)
                else:
                    result_content = json.loads(result.content)
            except json.JSONDecodeError as e:
                logger.error(f"[RAG] La respuesta del modelo no es un JSON válido: {e}")
                result_content = result.content.strip()

            # Post-procesar el resultado
            return self.post_process_result(result_content, query, context_full_streamlit)
        except Exception as e:
            logger.error(f"[RAG] Error en la ejecución: {e}", exc_info=True)
            raise RuntimeError(f"Error en la ejecución del RAG: {e}")