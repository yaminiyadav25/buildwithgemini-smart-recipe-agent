import base64
import io
import json
import os
import urllib.parse
import urllib.request
import uuid
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
from google import genai
from google.adk.tools import ToolContext
from google.cloud import firestore, storage
from google.genai import types

# Load environment variables from .env file
load_dotenv()

# Hardcoded project ID as required to prevent Agent Platform project number resolution issue
GCP_PROJECT_ID = "qwiklabs-gcp-01-9acb3984a34b"
GCS_BUCKET_NAME = "smart-recipe-images-qwiklabs-gcp-01-9acb3984a34b"


def get_firestore_client():
    return firestore.Client(project=GCP_PROJECT_ID)


def get_storage_client():
    return storage.Client(project=GCP_PROJECT_ID)


def get_maps_api_key():
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    return key


def search_recipes(query: str = "", cuisine: str = "", tag: str = "") -> str:
    """Searches recipes in the Firestore database matching search terms, cuisine, or dietary tags.

    Args:
        query: Optional search keyword to look for in recipe names or ingredients (e.g. "pasta", "chicken", "avocado").
        cuisine: Optional filter by cuisine type (e.g. "Italian", "Mediterranean", "Indian", "American").
        tag: Optional filter by dietary tag (e.g. "vegan", "vegetarian", "gluten-free", "high-protein").

    Returns:
        JSON string listing matching recipes with ID, name, cuisine, prep_time_minutes, servings, and dietary_tags.
    """
    db = get_firestore_client()
    recipes_ref = db.collection("recipes")
    docs = recipes_ref.stream()

    matches = []
    q_lower = query.lower().strip()
    cuisine_lower = cuisine.lower().strip()
    tag_lower = tag.lower().strip()

    for doc in docs:
        data = doc.to_dict()
        name = data.get("name", "")
        c_type = data.get("cuisine", "")
        tags = [t.lower() for t in data.get("dietary_tags", [])]
        ingredients = [i.lower() for i in data.get("ingredients", [])]

        if cuisine_lower and cuisine_lower not in c_type.lower():
            continue
        if tag_lower and not any(tag_lower in t for t in tags):
            continue
        if q_lower:
            text_match = (
                q_lower in name.lower()
                or any(q_lower in ing for ing in ingredients)
                or any(q_lower in t for t in tags)
            )
            if not text_match:
                continue

        matches.append({
            "id": doc.id,
            "name": name,
            "cuisine": c_type,
            "prep_time_minutes": data.get("prep_time_minutes", 0),
            "servings": data.get("servings", 0),
            "dietary_tags": data.get("dietary_tags", []),
            "ingredients": data.get("ingredients", []),
        })

    if not matches:
        return f"No recipes found matching query='{query}', cuisine='{cuisine}', tag='{tag}'."

    return json.dumps(matches, indent=2)


def get_recipe_details(recipe_id: str) -> str:
    """Fetches full recipe details including full ingredients and step-by-step instructions from Firestore.

    Args:
        recipe_id: The document ID of the recipe (e.g. "spaghetti-carbonara", "mediterranean-quinoa-bowl").

    Returns:
        JSON string containing the complete recipe details or an error message if not found.
    """
    db = get_firestore_client()
    doc_ref = db.collection("recipes").document(recipe_id.strip())
    doc = doc_ref.get()

    if not doc.exists:
        return f"Recipe with ID '{recipe_id}' not found in Firestore database."

    data = doc.to_dict()
    data["id"] = doc.id
    return json.dumps(data, indent=2)


def add_new_recipe(
    recipe_id: str,
    name: str,
    cuisine: str,
    prep_time_minutes: int,
    servings: int,
    dietary_tags: list[str],
    ingredients: list[str],
    instructions: str,
) -> str:
    """Saves a new recipe to the Firestore database.

    Args:
        recipe_id: A unique snake-case identifier for the recipe (e.g. "tacos-al-pastor").
        name: Full name of the dish.
        cuisine: Cuisine style (e.g. "Mexican", "Japanese").
        prep_time_minutes: Total preparation and cooking time in minutes.
        servings: Number of servings the recipe yields.
        dietary_tags: List of applicable dietary tags (e.g. ["gluten-free", "spicy"]).
        ingredients: List of ingredients with quantities.
        instructions: Step-by-step preparation instructions.

    Returns:
        A confirmation message string.
    """
    db = get_firestore_client()
    doc_ref = db.collection("recipes").document(recipe_id.strip())
    recipe_data = {
        "id": recipe_id.strip(),
        "name": name.strip(),
        "cuisine": cuisine.strip(),
        "prep_time_minutes": int(prep_time_minutes),
        "servings": int(servings),
        "dietary_tags": dietary_tags,
        "ingredients": ingredients,
        "instructions": instructions.strip(),
    }
    doc_ref.set(recipe_data)
    return f"Successfully saved recipe '{name}' with ID '{recipe_id}' to Firestore!"


def generate_recipe_image(dish_name: str, cuisine: str = "Gourmet Dish") -> str:
    """Generates a visual dish preview card and uploads it to a public Cloud Storage bucket for web viewing.

    Args:
        dish_name: The name of the dish or recipe (e.g. "Spaghetti Carbonara", "Avocado Toast").
        cuisine: Optional cuisine category (e.g. "Italian", "Mexican", "Mediterranean").

    Returns:
        JSON string containing the generated image's public Cloud Storage URL and metadata.
    """
    width, height = 600, 400
    img = Image.new("RGB", (width, height), color=(30, 41, 59))
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, width, 100], fill=(234, 88, 12))

    font_large = ImageFont.load_default()
    draw.text((30, 35), "SMART RECIPE CONCIERGE", fill=(255, 255, 255), font=font_large)
    draw.text((30, 140), f"Dish: {dish_name}", fill=(248, 250, 252), font=font_large)
    draw.text((30, 180), f"Cuisine: {cuisine}", fill=(203, 213, 225), font=font_large)
    draw.text((30, 220), "Status: Freshly Prepared & Grounded", fill=(52, 211, 153), font=font_large)

    draw.rectangle([30, 280, width - 30, 360], outline=(234, 88, 12), width=2)
    draw.text((50, 310), "✨ Visual preview generated by Smart Recipe Agent", fill=(148, 163, 184), font=font_large)

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    file_id = f"{uuid.uuid4().hex[:8]}.png"
    storage_client = get_storage_client()
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(file_id)
    blob.upload_from_file(buffer, content_type="image/png")

    public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{file_id}"

    return json.dumps({
        "status": "success",
        "dish_name": dish_name,
        "image_url": public_url,
        "bucket": GCS_BUCKET_NAME,
        "file_name": file_id
    }, indent=2)


def generate_recipe_dish_image(dish_description: str, tool_context: ToolContext) -> str:
    """Generates an image for a food item using the gemini-3.1-flash-lite-image model in global region, saves it as an ADK artifact, and uploads to Cloud Storage.

    Args:
        dish_description: Description or name of the food item or recipe to generate an image for (e.g. "A delicious bowl of ramen").
        tool_context: ADK ToolContext injected automatically by the framework.

    Returns:
        JSON string containing status, public GCS HTTPS URL, and artifact details.
    """
    # 1. Generate image using gemini-3.1-flash-lite-image in global region
    client = genai.Client(
        vertexai=True,
        project=GCP_PROJECT_ID,
        location="global"
    )
    prompt = f"A realistic, appetizing, high-resolution food photograph of {dish_description}."

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite-image",
        contents=prompt,
        config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"])
    )

    image_bytes = None
    for part in response.parts:
        if part.inline_data is not None:
            image_bytes = part.inline_data.data
            break

    if not image_bytes:
        return f"Failed to generate image for description: '{dish_description}'."

    filename = f"recipe_{uuid.uuid4().hex[:8]}.png"

    # 2. Save artifact to Playground via tool_context
    artifact_part = types.Part.from_bytes(data=image_bytes, mime_type="image/png")
    tool_context.save_artifact(filename=filename, artifact=artifact_part)

    # 3. Upload bytes to public Cloud Storage bucket
    storage_client = get_storage_client()
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_string(image_bytes, content_type="image/png")

    public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"

    return json.dumps({
        "status": "success",
        "dish_description": dish_description,
        "filename": filename,
        "public_url": public_url,
        "bucket": GCS_BUCKET_NAME
    }, indent=2)


def generate_recipe_video(item_description: str, tool_context: ToolContext) -> str:
    """Generates a short cooking video for a food item using Google's Omni model (gemini-omni-flash-preview) in the global region. Saves the video as an ADK artifact and uploads it to a public Cloud Storage bucket.

    Args:
        item_description: Description or name of the food item or recipe to generate a video for (e.g. "Sizzling steak fajitas", "Pouring sauce over pasta").
        tool_context: ADK ToolContext injected automatically by the framework.

    Returns:
        JSON string containing status, public Cloud Storage HTTPS URL, filename, and bucket name.
    """
    client = genai.Client(
        vertexai=True,
        project=GCP_PROJECT_ID,
        location="global"
    )
    prompt = f"A short, high quality cooking video showing preparation of {item_description}."

    interaction = client.interactions.create(
        model="gemini-omni-flash-preview",
        input=prompt,
    )

    raw_data = interaction.output_video.data
    if isinstance(raw_data, str):
        video_bytes = base64.b64decode(raw_data)
    else:
        try:
            video_bytes = base64.b64decode(raw_data)
        except Exception:
            video_bytes = raw_data

    if not video_bytes:
        return f"Failed to generate video for item: '{item_description}'."

    filename = f"recipe_{uuid.uuid4().hex[:8]}.mp4"

    # 1. Save video as an ADK artifact in Playground
    artifact_part = types.Part.from_bytes(data=video_bytes, mime_type="video/mp4")
    tool_context.save_artifact(filename=filename, artifact=artifact_part)

    # 2. Upload video bytes to public Cloud Storage bucket (without writing a local file)
    storage_client = get_storage_client()
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_string(video_bytes, content_type="video/mp4")

    public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"

    return json.dumps({
        "status": "success",
        "item_description": item_description,
        "filename": filename,
        "public_url": public_url,
        "bucket": GCS_BUCKET_NAME
    }, indent=2)


def fetch_global_recipes_from_mealdb(search_term: str) -> str:
    """Fetches real recipe data from TheMealDB public API for a given search query (e.g. "chicken", "curry", "pasta").

    Args:
        search_term: Search query or main ingredient to find global recipes for.

    Returns:
        JSON string listing real recipe matches from TheMealDB API with name, category, origin, and ingredients.
    """
    api_key = os.environ.get("THEMEALDB_API_KEY", "1")
    encoded_term = urllib.parse.quote(search_term.strip())
    url = f"https://www.themealdb.com/api/json/v1/{api_key}/search.php?s={encoded_term}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))

        meals = data.get("meals")
        if not meals:
            return f"No global recipes found on TheMealDB for term '{search_term}'."

        results = []
        for m in meals[:3]:
            ingredients = []
            for i in range(1, 21):
                ing = m.get(f"strIngredient{i}")
                meas = m.get(f"strMeasure{i}")
                if ing and ing.strip():
                    item = ing.strip()
                    if meas and meas.strip():
                        item = f"{meas.strip()} {item}"
                    ingredients.append(item)

            results.append({
                "meal_name": m.get("strMeal"),
                "category": m.get("strCategory"),
                "area_cuisine": m.get("strArea"),
                "instructions": (m.get("strInstructions") or "")[:300] + "...",
                "thumbnail_url": m.get("strMealThumb"),
                "ingredients": ingredients[:8],
            })

        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error fetching recipes from TheMealDB API: {str(e)}"


def geocode_address(address: str) -> str:
    """Converts a street address or city name into geographic latitude/longitude coordinates using Google Maps Geocoding API.

    Args:
        address: The street address, city, or landmark to geocode (e.g. "1600 Amphitheatre Pkwy, Mountain View, CA").

    Returns:
        JSON string containing the formatted address, location coordinates (latitude, longitude), and place_id.
    """
    api_key = get_maps_api_key()
    if not api_key or api_key == "PASTE_KEY_HERE":
        return "Error: GOOGLE_MAPS_API_KEY environment variable is not configured with a valid Maps API key."

    encoded_address = urllib.parse.quote(address.strip())
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_address}&key={api_key}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))

        if data.get("status") != "OK" or not data.get("results"):
            return f"Geocoding API returned status '{data.get('status')}': {data.get('error_message', 'No results found.')}"

        first_result = data["results"][0]
        location = first_result.get("geometry", {}).get("location", {})

        return json.dumps({
            "name": address,
            "formatted_address": first_result.get("formatted_address"),
            "location": {
                "latitude": location.get("lat"),
                "longitude": location.get("lng")
            },
            "place_id": first_result.get("place_id")
        }, indent=2)
    except Exception as e:
        return f"Error calling Google Maps Geocoding API: {str(e)}"


def find_nearby_places(latitude: float, longitude: float, place_type: str = "supermarket", radius_meters: float = 3000.0) -> str:
    """Finds nearby places of a given type (e.g. supermarket, grocery_store, restaurant) near coordinates using Google Places API (New).

    Args:
        latitude: Center latitude coordinate.
        longitude: Center longitude coordinate.
        place_type: Type of place to search for (e.g. "supermarket", "grocery_store", "restaurant", "bakery").
        radius_meters: Search radius in meters (default 3000m / 3km).

    Returns:
        JSON string listing matching nearby places with name, formatted address, and location coordinates.
    """
    api_key = get_maps_api_key()
    if not api_key or api_key == "PASTE_KEY_HERE":
        return "Error: GOOGLE_MAPS_API_KEY environment variable is not configured with a valid Maps API key."

    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location"
    }

    payload = {
        "includedTypes": [place_type.strip()],
        "maxResultCount": 5,
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": float(latitude),
                    "longitude": float(longitude)
                },
                "radius": float(radius_meters)
            }
        }
    }

    try:
        json_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=json_data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))

        places = data.get("places", [])
        if not places:
            return f"No nearby places of type '{place_type}' found within {radius_meters}m radius."

        results = []
        for p in places:
            display_name = p.get("displayName", {}).get("text", "Unknown Place")
            formatted_address = p.get("formattedAddress", "")
            loc = p.get("location", {})
            results.append({
                "name": display_name,
                "address": formatted_address,
                "location": {
                    "latitude": loc.get("latitude"),
                    "longitude": loc.get("longitude")
                }
            })

        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error calling Google Places API (New): {str(e)}"
