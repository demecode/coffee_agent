import os
import re
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition

load_dotenv()

agent_name = os.getenv("AGENT_NAME", "coffee-agent")
if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", agent_name):
    raise ValueError(
        "AGENT_NAME must start and end with an alphanumeric character, "
        "can contain hyphens in the middle, and must not exceed 63 characters."
    )

project_client = AIProjectClient(
    endpoint=os.environ["PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
)

openai_client = project_client.get_openai_client()

# agent creation

agent = project_client.agents.create_version(
    agent_name=agent_name,
    definition=PromptAgentDefinition(
        model=os.environ["MODEL_DEPLOYMENT_NAME"],
    ),
)

print(f"Agent created (id: {agent.id}, name: {agent.name}, version: {agent.version})")

conversation = openai_client.conversations.create()
print(f"Created conversation (id: {conversation.id})")

while True:
    # Get the user input
    user_input = input("You: ")

    if user_input.lower() in ["exit", "quit"]:
        print("Exiting the chat.")
        break

    # Get the agent response
    response = openai_client.responses.create(
        conversation=conversation.id,
        input=user_input,
        extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
    )

    # Print the agent response
    print(f"Assistant: {response.output_text}")
