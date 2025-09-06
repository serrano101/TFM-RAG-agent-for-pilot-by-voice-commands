
import chromadb
import json
from langchain_core.prompts import PromptTemplate
from langchain.agents import create_react_agent, AgentExecutor
from langchain.tools import tool
from langchain_ollama import ChatOllama
# CONECTION CHROMAD
db_path = "/home/serrano101/projects/TFM-RAG-agent-for-pilot-by-voice-commands/common/vector_db/"
client = chromadb.PersistentClient(path=db_path)
collection = client.get_collection("documentos")

#SEARCH
def search_text(text, top_k=5, headings=None):
    """Busca información relevante en la base de datos vectorial, filtrando por headings si se proporciona."""
    if headings:
        results = collection.query(
            query_texts=[text], 
            n_results=top_k, 
            where_document={"$contains": headings})
    else:
        results = collection.query(query_texts=[text], n_results=top_k)
    return results
# results = collection.query(
#     query_texts=[text], 
#     n_results=top_k, 
#     where_document={"$contains": headings})
# #IMPRIMIR RESULTADOS
# print("Resultados encontrados:")
# print(json.dumps(results.get("documents")))

@tool
def search_vector_db(query: str, headings: str = '') -> str:
    """Busca información relevante en la base de datos vectorial, filtrando por headings si se proporciona.
    Example of input JSON:
    {
        "query": "tell me procedure of manual landing",
        "headings": "manual landing"
    }
    Example of output:
    {
    }
    """
    # parsed_json = json.loads(json_input)
    # query = parsed_json.get("query")
    # headings = parsed_json.get("headings")
    docs = search_text(query, headings=headings).get("documents")
    if not docs:
        # Si no se encuentran documentos, devuelve un mensaje específico
        return "No relevant documents found."
    else:
        return json.dumps(docs)

tools = [search_vector_db]
temop_1 = """
    You are an intelligent assistant that always thinks in English and ONLY uses the provided tools: {tool_names} to answer queries.
    You must search exclusively in the database using the available tools: {tools}.

    You need to call a tool, respond using this exact format:

    Thought: [Explain your reasoning]
    Action: Tool to call
    Action Input: Tool input in JSON format with no additional quotes around the entire input.
    If a tool response is received:
    - If the tool response is "No relevant documents found.", reply ONLY with:
        Final Answer: No relevant documents found.
    - Otherwise, extract all the relevant information from the tool response to give a proper answer to the user query:
        Final Answer: [Your final response to the query: {input}. Include all raw information of the documents found.]
    Important: If no relevant information is found in the database, do NOT attempt to answer the query in any other way. Only reply that you do not have information.

    Query: {input}

    {agent_scratchpad}
    """ 

temp_2 = """
Answer the following questions as best you can. You have access to the following tools:

{tools}

Use the following format:
Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action. 
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: Format the final answer as a Markdown checklist. The raw content from the tool exactly as it was returned, without any modifications.

Begin!

Question: {input}
Thought:{agent_scratchpad}"""
temp_3 =  """
Answer the following questions as best you can. You have access to the following tools:

{tools}

Use the following format:
Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action.
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question. Checklist of the content raw.

Begin!

Question: {input}
Thought:{agent_scratchpad}"""

prompt = PromptTemplate(
    input_variables=["input", "tool_names", "agent_scratchpad"],
    template=temp_3
)
llm = ChatOllama(model="mistral:instruct", base_url="http://localhost:11434")
agent = create_react_agent(llm, tools, prompt)
agent_executor = AgentExecutor.from_agent_and_tools(agent , tools=tools, handle_parsing_errors=True,verbose=True)


#INPUTS
top_k = 5
# headings = "Aircraft Setup"
text = "Information Aircraft Setup"
agent_executor.invoke({"input": text})
# Mostrar el resultado final
# print(result["output"])
# console = Console()
# markdown_content = Markdown(result["output"])
# console.print(markdown_content)



# PROMPT_TEMPLATE = """
# Answer the question based only on the following context:
# {context}
# - -
# Answer the question based on the above context: {question}
# """
# Result =  search_text(text, top_k=5, headings="Aircraft Setup")
# print("Resultados encontrados:")
# print(Result)