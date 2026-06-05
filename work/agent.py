import argparse
import glob
import os
import re
import json
from pathlib import Path
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, FileSearchTool, FunctionTool, Tool, MCPTool
from openai import OpenAIError
from openai.types.responses.response_input_param import FunctionCallOutput, ResponseInputParam

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
ENV_PATH = ROOT_DIR / ".env"

load_dotenv(ENV_PATH)

instructions_path = SCRIPT_DIR / "instructions.txt"
agent_name = os.getenv("AGENT_NAME", "coffee-agent")
coffee_mcp_server_url = os.getenv("COFFEE_MCP_SERVER_URL", "").strip()
if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", agent_name):
    raise ValueError(
        "AGENT_NAME must start and end with an alphanumeric character, "
        "can contain hyphens in the middle, and must not exceed 63 characters."
    )


def parse_args() -> argparse.Namespace:
    configured_vector_store_id = os.getenv("VECTOR_STORE_ID", "").strip()
    default_vector_store_mode = os.getenv(
        "VECTOR_STORE_MODE",
        "reuse" if configured_vector_store_id else "ask",
    )

    parser = argparse.ArgumentParser(description="Run the Coffee Agent.")
    parser.add_argument(
        "--vector-store-mode",
        choices=["reuse", "create", "ask"],
        default=default_vector_store_mode,
        help="Reuse VECTOR_STORE_ID, create a new vector store, or ask at runtime.",
    )
    parser.add_argument(
        "--vector-store-id",
        default=configured_vector_store_id,
        help="Existing vector store ID to use when reusing a vector store.",
    )
    parser.add_argument(
        "--upload-documents",
        action="store_true",
        help="Upload files matching DOCUMENTS_GLOB into the selected vector store before starting the chat. Prefer scripts/sync_vector_store_documents.py for routine document updates.",
    )
    return parser.parse_args()


def upsert_env_value(path: Path, key: str, value: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    replacement = f"{key}={value}"

    for index, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[index] = replacement
            break
    else:
        if lines and lines[-1] != "":
            lines.append("")
        lines.append(replacement)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def should_create_vector_store(mode: str, vector_store_id: str) -> bool:
    if mode == "create":
        return True
    if mode == "reuse":
        if not vector_store_id:
            raise ValueError(
                "VECTOR_STORE_ID is required when VECTOR_STORE_MODE=reuse. "
                "Set VECTOR_STORE_MODE=create or run with --vector-store-mode create to create one."
            )
        return False

    if vector_store_id:
        answer = input(f"Use existing vector store {vector_store_id}? [Y/n]: ").strip().lower()
        return answer in {"n", "no"}

    answer = input("No VECTOR_STORE_ID is configured. Create a new vector store? [Y/n]: ").strip().lower()
    if answer in {"", "y", "yes"}:
        return True
    raise ValueError("A vector store is required to run file search.")


def upload_documents_to_vector_store(vector_store_id: str) -> None:
    documents_glob = os.getenv("DOCUMENTS_GLOB", str(SCRIPT_DIR / "documents" / "*.md"))
    document_paths = [Path(path) for path in sorted(glob.glob(documents_glob))]

    if not document_paths:
        print(f"No documents matched {documents_glob}; vector store has no uploaded files from this run.")
        return

    for file_path in document_paths:
        with file_path.open("rb") as document:
            file = openai_client.vector_stores.files.upload_and_poll(
                vector_store_id=vector_store_id,
                file=document,
            )
        print(f"File uploaded to vector store (file: {file_path}, id: {file.id})")


args = parse_args()

project_client = AIProjectClient(
    endpoint=os.environ["PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
)

openai_client = project_client.get_openai_client()

# vector store creation
if should_create_vector_store(args.vector_store_mode, args.vector_store_id):
    vector_store = openai_client.vector_stores.create(name=os.getenv("VECTOR_STORE_NAME", "CoffeeStores"))
    print(f"Vector store created (id: {vector_store.id})")
    upload_documents_to_vector_store(vector_store.id)
    upsert_env_value(ENV_PATH, "VECTOR_STORE_ID", vector_store.id)
    print(f"Saved VECTOR_STORE_ID={vector_store.id} to {ENV_PATH}")
else:
    vector_store = openai_client.vector_stores.retrieve(args.vector_store_id)
    print(f"Using existing vector store (id: {vector_store.id})")

if args.upload_documents:
    upload_documents_to_vector_store(vector_store.id)


## -- Function Calling Tool -- ##
func_tool = FunctionTool(
    name="recommend_coffee_order",
    parameters={
        "type": "object",
        "properties": {
            "people": {
                "type": "integer",
                "description": "The number of people the coffee order should serve.",
                "minimum": 1,
            },
            "drink_style": {
                "type": "string",
                "description": "The customer's preferred coffee style.",
                "enum": [
                    "espresso-forward",
                    "milk-forward",
                    "sweet",
                    "iced",
                    "black coffee",
                    "mixed group",
                    "not sure",
                ],
            },
            "caffeine_preference": {
                "type": "string",
                "description": "The preferred caffeine level.",
                "enum": ["regular", "strong", "low-caf", "decaf", "mixed", "not sure"],
            },
            "milk_preference": {
                "type": "string",
                "description": "The preferred milk or dairy-free option.",
                "enum": ["dairy", "oat", "almond", "soy", "coconut", "black", "mixed", "not sure"],
            },
            "sweetness": {
                "type": "string",
                "description": "The preferred sweetness level.",
                "enum": ["unsweetened", "light", "medium", "sweet", "mixed", "not sure"],
            },
            "temperature": {
                "type": "string",
                "description": "Whether the drinks should be hot, iced, or a mix.",
                "enum": ["hot", "iced", "mixed", "not sure"],
            },
        },
        "required": ["people", "drink_style", "caffeine_preference"],
        "additionalProperties": False,
    },
    description="Recommend coffee drinks based on group size, taste, caffeine, milk, and sweetness preferences.",
    strict=False,
)

def recommend_coffee_order(
    people: int,
    drink_style: str,
    caffeine_preference: str,
    milk_preference: str = "not sure",
    sweetness: str = "not sure",
    temperature: str = "not sure",
) -> str:
    """Recommend a practical coffee order from customer preferences."""
    print(f"[FUNCTION CALL:recommend_coffee_order] Recommending coffee for {people} people.")

    if drink_style == "espresso-forward":
        drink = "flat white" if milk_preference not in {"black", "not sure"} else "americano"
    elif drink_style == "milk-forward":
        drink = "latte"
    elif drink_style == "sweet":
        drink = "mocha" if sweetness in {"medium", "sweet", "not sure"} else "vanilla latte"
    elif drink_style == "iced":
        drink = "iced latte" if milk_preference != "black" else "cold brew"
    elif drink_style == "black coffee":
        drink = "americano" if temperature == "hot" else "cold brew"
    else:
        drink = "a mix of lattes, americanos, and mochas"

    caffeine_note = {
        "strong": "add an extra espresso shot",
        "low-caf": "make it half-caf",
        "decaf": "make it decaf",
        "mixed": "offer regular and decaf options",
    }.get(caffeine_preference, "use regular espresso")

    milk_note = "" if milk_preference in {"not sure", "mixed"} else f" with {milk_preference} milk"
    return f"For {people} people, recommend {people} {drink}{milk_note}; {caffeine_note}."


# file search tool definition / creation

toolset: list[Tool] = []
toolset.append(FileSearchTool(vector_store_ids=[vector_store.id]))
toolset.append(func_tool)

if coffee_mcp_server_url:
    toolset.append(
        MCPTool(
            server_label="coffee",
            server_url=coffee_mcp_server_url,
            server_description="Coffee menu, recommendation, store information, pricing, and order tools.",
            allowed_tools=[
                "get_menu",
                "recommend_coffee",
                "estimate_order_total",
                "get_store_info",
                "create_order",
            ],
            require_approval="never",
        )
    )
    print(f"Using Coffee MCP server: {coffee_mcp_server_url}")
else:
    print("COFFEE_MCP_SERVER_URL is not configured; running without the Coffee MCP server.")


# agent creation
agent = project_client.agents.create_version(
    agent_name=agent_name,
    definition=PromptAgentDefinition(
        model=os.environ["MODEL_DEPLOYMENT_NAME"],
        instructions=instructions_path.read_text(encoding="utf-8"),
        tools=toolset,
    ),
)

print(f"Agent created (id: {agent.id}, name: {agent.name}, version: {agent.version})")

conversation = openai_client.conversations.create()
print(f"Created conversation (id: {conversation.id})")

while True:
    # Get the user input
    try:
        user_input = input("You: ")
    except EOFError:
        print("No input received. Exiting the chat.")
        break

    if user_input.lower() in ["exit", "quit"]:
        print("Exiting the chat.")
        break

    # Get the agent response
    try:
        response = openai_client.responses.create(
            conversation=conversation.id,
            input=user_input,
            extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
        )
    except OpenAIError as error:
        print(f"Assistant error: {error}")
        continue

    # Handle function calls in the response
    input_list: ResponseInputParam = []
    for item in response.output:
        if item.type == "function_call":
            if item.name == "recommend_coffee_order":
                # Execute the coffee recommendation function.
                coffee_recommendation = recommend_coffee_order(**json.loads(item.arguments))
                # Provide function call results to the model
                input_list.append(
                    FunctionCallOutput(
                        type="function_call_output",
                        call_id=item.call_id,
                        output=json.dumps({"coffee_recommendation": coffee_recommendation}),
                    )
                )

    if input_list:
        try:
            response = openai_client.responses.create(
                previous_response_id=response.id,
                input=input_list,
                extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
            )
        except OpenAIError as error:
            print(f"Assistant error: {error}")
            continue

    # Print the agent response
    print(f"Assistant: {response.output_text}")
