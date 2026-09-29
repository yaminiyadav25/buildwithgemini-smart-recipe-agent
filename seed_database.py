import sys
from google.cloud import firestore

# Hardcoded project ID as required to prevent Agent Platform project number resolution issue
GCP_PROJECT_ID = "qwiklabs-gcp-01-9acb3984a34b"

SEED_RECIPES = [
    {
        "id": "spaghetti-carbonara",
        "name": "Classic Spaghetti Carbonara",
        "cuisine": "Italian",
        "prep_time_minutes": 20,
        "servings": 4,
        "dietary_tags": ["dairy-optional", "high-protein"],
        "ingredients": [
            "400g spaghetti",
            "150g guanciale or pancetta",
            "4 large egg yolks",
            "50g Pecorino Romano cheese, grated",
            "Freshly cracked black pepper"
        ],
        "instructions": "1. Boil spaghetti in salted water until al dente.\n2. Crisp guanciale in a skillet over medium heat.\n3. Whisk egg yolks with grated cheese and black pepper.\n4. Toss hot pasta with guanciale and remove from heat.\n5. Stir in egg-cheese mixture quickly to form a creamy sauce."
    },
    {
        "id": "mediterranean-quinoa-bowl",
        "name": "Mediterranean Quinoa Bowl",
        "cuisine": "Mediterranean",
        "prep_time_minutes": 15,
        "servings": 2,
        "dietary_tags": ["vegan", "vegetarian", "gluten-free"],
        "ingredients": [
            "1 cup cooked quinoa",
            "1 cucumber, diced",
            "1 cup cherry tomatoes, halved",
            "1/2 cup Kalamata olives",
            "1/2 cup chickpeas, rinsed",
            "2 tbsp lemon tahini dressing"
        ],
        "instructions": "1. Layer cooked quinoa as the base in serving bowls.\n2. Arrange diced cucumber, cherry tomatoes, Kalamata olives, and chickpeas on top.\n3. Drizzle generously with lemon tahini dressing and serve fresh."
    },
    {
        "id": "chicken-tikka-masala",
        "name": "Creamy Chicken Tikka Masala",
        "cuisine": "Indian",
        "prep_time_minutes": 35,
        "servings": 4,
        "dietary_tags": ["gluten-free", "high-protein"],
        "ingredients": [
            "600g boneless chicken thigh, cubed",
            "1/2 cup Greek yogurt",
            "2 tbsp tikka masala spice blend",
            "1 onion, finely chopped",
            "1 can (400g) tomato puree",
            "1/2 cup heavy cream or coconut cream"
        ],
        "instructions": "1. Marinate chicken in yogurt and spices for 15 mins.\n2. Sear chicken in skillet until golden brown.\n3. Saute onions, tomato puree, and cream to form sauce.\n4. Simmer chicken in sauce for 15 minutes until tender."
    },
    {
        "id": "avocado-toast-poached-egg",
        "name": "Avocado Toast with Poached Egg",
        "cuisine": "American",
        "prep_time_minutes": 10,
        "servings": 1,
        "dietary_tags": ["vegetarian"],
        "ingredients": [
            "2 slices sourdough bread",
            "1 ripe avocado",
            "1 tbsp fresh lemon juice",
            "1 poached egg",
            "Chili flakes and sea salt"
        ],
        "instructions": "1. Toast sourdough slices until golden and crisp.\n2. Mash ripe avocado with lemon juice, salt, and pepper.\n3. Spread avocado onto toast and top with a warm poached egg and chili flakes."
    }
]


def seed_firestore():
    print(f"Connecting to Firestore for project: {GCP_PROJECT_ID}...")
    db = firestore.Client(project=GCP_PROJECT_ID)
    collection_ref = db.collection("recipes")

    for recipe in SEED_RECIPES:
        doc_id = recipe["id"]
        doc_ref = collection_ref.document(doc_id)
        doc_ref.set(recipe)
        print(f"  ✓ Seeded recipe: {recipe['name']} (ID: {doc_id})")

    print("\nSuccessfully seeded Firestore 'recipes' collection!")


if __name__ == "__main__":
    seed_firestore()
