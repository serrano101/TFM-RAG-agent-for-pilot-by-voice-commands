import logging

# from src.embedders.sentence_transformers_embedders import Embedder
from src.database.chromadb_repository import VectorDBRepository
from src.llm.ollama_service import LLMClientOllama
from langchain_core.prompts import PromptTemplate
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from typing import Optional, Union
# Obtiene un logger para el módulo actual
logger = logging.getLogger(__name__)

class RAG:
    def __init__(
        self,
        vector_db: VectorDBRepository,
        llm: LLMClientOllama,
        prompt: Union[str, PromptTemplate],
        prompt_heading: Union[str, PromptTemplate],
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
            if isinstance(prompt_heading, str):
                self.prompt_heading = PromptTemplate(input_variables=['query'], template=prompt_heading)
            else:
                self.prompt_heading = prompt_heading
            self._search_type = search_type
            self._search_kwargs = search_kwargs or {}
            
            # Cadena para combinar documentos recuperados (se mantiene, no depende del filtro)
            self._combine_docs_chain = create_stuff_documents_chain(
                self.llm.client, self.prompt
            )
            logger.info("[RAG] Inicializado correctamente.")
        except Exception as e:
            logger.error(f"[RAG] Error al inicializar: {e}", exc_info=True)
            raise RuntimeError(f"Error al inicializar el RAG: {e}")

    def extract_heading(self, query: str, prompt_extract: PromptTemplate) -> str:
        """
        Usa el LLM para extraer el término clave (heading) de la consulta del usuario.
        """
        try:
            heading = self.llm.client.invoke(prompt_extract.format(query=query))
            if hasattr(heading, 'content'):
                heading = heading.content.strip()
            else:
                heading = str(heading).strip()
            logger.info(f"[RAG] Heading extraído: {heading}")
            return heading
        except Exception as e:
            logger.error(f"[RAG] Error extrayendo heading: {e}", exc_info=True)
            return ""

    def execute(self, query: str, use_custom_search: Optional[bool] = False) -> str:
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
            # Extraer heading relevante usando el LLM
            heading = self.extract_heading(query, self.prompt_heading)
            logger.debug(f"[RAG] Heading para filtro: {heading}")

            if use_custom_search:
                # --- Usar método search personalizado ---
                filter = None
                where_document = None
                if heading:
                    where_document = {"$contains": heading}
                else:
                    logger.warning("[RAG] No se pudo extraer un heading, se aplicará filtro vacío.")
                    where_document = {"$contains": ""}

                logging.info(f"[RAG] Filtros aplicados: filter={filter}, where_document={where_document}")

                docs = self.vector_db.search(
                    query=query,
                    top_k=self._search_kwargs.get("k", 5),
                    filter=filter,
                    where_document=where_document,
                    return_score=False
                )
                logger.debug(f"[RAG] Documentos recuperados: {len(docs)}")
                logger.debug(f"[RAG] Documentos: {[docs]}")

                result = self._combine_docs_chain.invoke({
                    "input": query,
                    "context": "\n\n".join([doc.page_content for doc in docs])
                })
                logger.debug(f"[RAG] Respuesta del RAG:\n{result}")
                return result
            else:
                # --- Usar retriever de LangChain (original) ---
                dynamic_search_kwargs = dict(self._search_kwargs) if self._search_kwargs else {}
                if heading:
                    dynamic_search_kwargs["where_document"] = {"$contains": heading}
                else:
                    logger.warning("[RAG] No se pudo extraer un heading, se aplicará filtro vacío.")
                    dynamic_search_kwargs["where_document"] = {"$contains": ""}

                logging.info(f"[RAG] Search_kwargs aplicados: {dynamic_search_kwargs}")

                retriever = self.vector_db.vector_store.as_retriever(
                    search_type=self._search_type,
                    search_kwargs=dynamic_search_kwargs
                )
                retrieval_chain = create_retrieval_chain(retriever, self._combine_docs_chain)
                result = retrieval_chain.invoke({'input': query})
                logger.debug(f"[RAG] Respuesta del RAG:\n{result}")
                return result
        except Exception as e:
            logger.error(f"[RAG] Error en la ejecución: {e}", exc_info=True)
            raise RuntimeError(f"Error en la ejecución del RAG: {e}")