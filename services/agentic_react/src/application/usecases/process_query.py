# from src.domain.entities.query import Query
from src.domain.entities.result import Result
from src.domain.entities.step import Step
from common.embedders.embedders import MpnetBaseEmbedder
from src.infra.repositories.vector_db_repository import VectorDBRepository
# from src.infra.services.llm_service import LLMService
from src.infra.services.llm_service import LLMClientOllama
from langchain_core.prompts import PromptTemplate
from langchain.agents import create_react_agent, AgentExecutor
from langchain.tools import tool


class ReActAgentService:
    def __init__(self, embedder: MpnetBaseEmbedder, vector_db: VectorDBRepository, llm: LLMClientOllama):
        self.embedder = embedder
        self.vector_db = vector_db
        self.llm = llm

        # Define la herramienta como método de instancia
        @tool
        def search_vector_db(query: str) -> str:
            """Busca información relevante en la base de datos vectorial."""
            embedding = self.embedder.embed(query)
            docs = self.vector_db.search_embedding(embedding)
            # docs = self.vector_db.search_text(query)
            if not docs:
                return "No relevant documents found."
            return " | ".join([doc['content'][:100] for doc in docs])
            # return "\n".join(doc for i, doc in enumerate(docs))

        self.tools = [search_vector_db]
        self.prompt = PromptTemplate(
            input_variables=["input", "tool_names", "agent_scratchpad"],
            template="""
            You are an intelligent assistant that always thinks in English, capable of providing detailed responses related to companies using the tools: {tool_names}.
            Here are the available tools: {tools}

            If you need to call a tool, respond using this exact format:

            Thought: [Explain your reasoning]
            Action: Tool to call
            Action Input: Tool input in JSON format with no additional quotes around the entire input

            If a tool response is received:
            - Extract all the relevant information to give a proper answer to user query.
            - Provide a final answer in the following format:

            Final Answer: [Your final response to the query: {input}. Include all relevant information with details.]

            Query: {input}

            {agent_scratchpad}
            """
        )
        self.agent = create_react_agent(self.llm, self.tools, self.prompt)
        self.agent_executor = AgentExecutor.from_agent_and_tools(self.agent , tools=self.tools, handle_parsing_errors=True)

    def execute(self, user_input: str) -> Result:
        # Ejecuta el reasoning loop
        result = self.agent_executor.invoke({"input": user_input})
        final_answer = result["output"]

        # Extrae los pasos intermedios del reasoning loop
        steps = []
        for s in result.get("intermediate_steps", []):
            # s es una tupla: (tool_call, tool_output)
            tool_call, tool_output = s
            step = Step(
                thought=getattr(tool_call, "log", ""),  # o extrae el razonamiento si está disponible
                action=getattr(tool_call, "tool", None),
                observation=str(tool_output),
                tool_used=getattr(tool_call, "tool", None),
                tool_input=getattr(tool_call, "tool_input", None),
                tool_output=tool_output,
                metadata={}
            )
            steps.append(step)

        return Result(response=final_answer, steps=steps, success=True)

