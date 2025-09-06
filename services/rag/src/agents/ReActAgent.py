import logging
from typing import Union

# Obtiene un logger para el módulo actual
logger = logging.getLogger(__name__)

# from src.domain.entities.query import Query
import logging
# from src.embedders.sentence_transformers_embedders import Embedder
from src.database.chromadb_repository import VectorDBRepository
# from src.infra.services.llm_service import LLMService
from src.llm.ollama_service import LLMClientOllama
import json
from langchain_core.prompts import PromptTemplate
from langchain.agents import create_react_agent, AgentExecutor
from langchain.tools import tool

# Obtiene un logger para el módulo actual
logger = logging.getLogger(__name__)

class ReActAgentService:
    """
    Servicio para ejecutar el agente ReAct sobre una consulta de usuario.
    """
    def __init__(
        self, 
        # embedder: Embedder, 
        vector_db: VectorDBRepository, 
        llm: LLMClientOllama, 
        prompt: Union[str, PromptTemplate]
    ) -> None:
        """
        Inicializa el agente con los componentes necesarios.

        Args:
            vector_db (VectorDBRepository): Repositorio vectorial para recuperación de información.
            llm (LLMClientOllama): Cliente LLM para generación de respuestas.
            prompt (PromptTemplate): Prompt para el agente.

        Returns:
            None: No se devuelven valores. 

        Raises:
            RuntimeError: Si ocurre un error al inicializar las dependencias o crear el agente.
        """
        try:
            logger.debug("[ReActAgentService] Inicializando las dependencias de agente ReAct...")
            self.vector_db = vector_db
            self.llm = llm
            logger.info("[ReActAgentService] Dependencias de agente ReAct inicializadas correctamente.")
        except Exception as e:
            logger.error(f"[ReActAgentService] Error al inicializar: {e}", exc_info=True)
            raise RuntimeError(f"Error al inicializar ReActAgentService: {e}")
        
        try:
            logger.debug("[ReActAgentService] Creando herramientas para el agente ReAct...")
            # Define la herramienta como método de instancia
            @tool
            def search_vector_db(json_input: json) -> str:
                """
                Busca información relevante en la base de datos vectorial, filtrando por headings si se proporciona.

                Args:
                    json_input (json): Diccionario con los siguientes campos:
                        - query (str): Consulta de búsqueda.
                        - headings (str, opcional): Encabezados o temas para filtrar los resultados.
                    Example of input JSON:
                    {
                        "query": "tell me procedure of manual landing",
                        "headings": "manual landing"
                    }
                Returns:
                    str: Documentos relevantes en formato JSON. Si no se encuentran documentos, devuelve un mensaje indicándolo.

                Raises:
                    KeyError: Si falta el campo 'query' en la entrada.
                    Exception: Si ocurre un error inesperado durante la búsqueda.
                """
                try:
                    parsed_json = json.loads(json_input)
                except Exception as e:
                    return f"Error: input no es un JSON válido: {e}"
                query_text = parsed_json.get("query")
                headings = parsed_json.get("headings")
                # Solo aplicar filtro si headings es un string no vacío
                search_kwargs = {
                    "query": query_text,
                    "top_k": 5
                }
                if isinstance(headings, str) and headings.strip():
                    search_kwargs["where_document"] = {"$contains": headings.strip()}
                docs = self.vector_db.search(**search_kwargs)
                # Convertir Document a dict si es necesario
                def doc_to_dict(doc):
                    if hasattr(doc, 'dict'):
                        return doc.dict()
                    elif hasattr(doc, '__dict__'):
                        return dict(doc.__dict__)
                    return doc
                docs_serializable = [doc_to_dict(d) for d in docs]
                if not docs_serializable:
                    return "No relevant documents found."
                else:
                    try:
                        return json.dumps(docs_serializable, ensure_ascii=False, indent=2)
                    except Exception as e:
                        return f"Error serializando documentos: {e}"

            self.tools = [search_vector_db]
            self.prompt = PromptTemplate(
                input_variables=["input", "tool_names", "agent_scratchpad"],
                template=prompt
                )
            self.agent = create_react_agent(llm=self.llm.client, tools=self.tools, prompt=self.prompt) # Queda pendiente utilizar response_format
            self.agent_executor = AgentExecutor.from_agent_and_tools(self.agent , tools=self.tools, handle_parsing_errors=True)
            logger.info("[ReActAgentService] Agente ReAct creado correctamente.")
        except Exception as e:
            logger.error(f"[ReActAgentService] Error al crear el agente ReAct: {e}", exc_info=True)
            raise RuntimeError(f"Error al crear el agente ReAct: {e}")
        
    def execute(self, user_input: str) -> str:
        """
        Ejecuta el agente ReAct sobre una consulta dada y devuelve la respuesta.

        Args:
            user_input (str): Consulta del usuario a procesar por el agente.

        Returns:
            str: Respuesta generada por el agente.

        Raises:
            RuntimeError: Si ocurre un error durante la ejecución del agente.
        """
        logger.info(f"[ReActAgentService] Ejecutando agente ReAct para la consulta: {user_input[:100]}")
        try:
            # Ejecuta el reasoning loop
            result = self.agent_executor.invoke({"input": user_input})
            # final_answer = result["output"]
            logger.debug(f"[ReActAgentService] Respuesta del Agente ReAct:\n{result}")
            return result
        except Exception as e:
            logger.error(f"[ReActAgentService] Error en la ejecución de agente ReAct: {e}", exc_info=True)
            raise RuntimeError(f"Error en la ejecución de agente ReAct: {e}")

