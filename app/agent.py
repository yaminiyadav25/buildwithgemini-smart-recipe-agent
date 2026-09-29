# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors.agent_engine_sandbox_code_executor import (
    AgentEngineSandboxCodeExecutor,
)
from google.adk.models import Gemini
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

from app.a2ui_utils import a2ui_callback
from app.tools import (
    add_new_recipe,
    fetch_global_recipes_from_mealdb,
    find_nearby_places,
    generate_recipe_dish_image,
    generate_recipe_image,
    generate_recipe_video,
    geocode_address,
    get_recipe_details,
    search_recipes,
)



def get_weather(query: str) -> str:
    """Simulates a web search. Use it to get information on weather.

    Args:
        query: A string containing the location to get weather information for.

    Returns:
        A string with the simulated weather information for the queried location.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    return "It's 90 degrees and sunny."


def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        query: The name of the city to get the current time for.

    Returns:
        A string with the current time information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


async def generate_memories_callback(callback_context: CallbackContext):
    """WRITE: After each conversation turn, save session data into Vertex AI Memory Bank."""
    await callback_context.add_session_to_memory()
    return None


# Build A2UI 0.8 system prompt schema
schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are Smart Recipe Concierge, an AI culinary assistant that helps home cooks plan meals, "
        "search local recipes stored in Cloud Firestore, fetch global recipes from TheMealDB public API, "
        "view detailed ingredients/instructions, generate realistic food photographs using gemini-3.1-flash-lite-image, "
        "generate short cooking videos using Google's Omni model (gemini-omni-flash-preview), "
        "find nearby grocery stores or supermarkets using Google Maps Geocoding and Places (New) APIs, "
        "remember user preferences and food allergies across conversations using Vertex AI Memory Bank, "
        "run Python code safely in a sandbox using code execution, and add custom new recipes."
    ),
    workflow_description="Analyze the request, execute necessary tools, and return structured A2UI components when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        '{"Image": {"url": {"literalString": "https://..."}}}. Never point an '
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects.\n\n"
        "MEMORY AND ALLERGY GUARDRAILS:\n"
        "- Pay strict attention to all user food allergies, intolerances, and dietary restrictions mentioned across conversations.\n"
        "- Remember all user allergies (e.g. peanuts, tree nuts, dairy, gluten, shellfish, eggs, soy, etc.) using your Memory Bank.\n"
        "- ALWAYS recall remembered user allergies before recommending recipes, suggesting meals, or planning menus.\n"
        "- NEVER suggest or recommend any recipe, dish, or ingredient that contains a remembered user allergen.\n"
        "- Clearly notify the user when a recipe has been filtered or adjusted to keep them safe from known allergies."
    ),
    include_schema=True,
    include_examples=True,
)


# Initialize AgentEngineSandboxCodeExecutor from deployment_metadata.json
metadata_path = Path(__file__).parent.parent / "deployment_metadata.json"
code_executor = None

if metadata_path.exists():
    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
            ae_resource_name = metadata.get("remote_agent_runtime_id")
            if ae_resource_name:
                code_executor = AgentEngineSandboxCodeExecutor(
                    agent_engine_resource_name=ae_resource_name
                )
    except Exception as e:
        print(f"Warning: Failed to load deployment metadata for code executor: {e}")


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,
    tools=[
        PreloadMemoryTool(),
        search_recipes,
        fetch_global_recipes_from_mealdb,
        get_recipe_details,
        generate_recipe_dish_image,
        generate_recipe_image,
        generate_recipe_video,
        geocode_address,
        find_nearby_places,
        add_new_recipe,
        get_weather,
        get_current_time,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
    code_executor=code_executor,
)

app = App(
    root_agent=root_agent,
    name="app",
)
