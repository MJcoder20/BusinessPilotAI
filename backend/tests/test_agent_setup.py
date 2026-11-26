from langchain.agents import create_agent
from langchain_ollama import ChatOllama

model = ChatOllama(
    model="qwen2.5:3b",
    temperature=0
)

print("LangGraph and LangChain imports successful!")
print("Model initialized successfully!")