import os
from dotenv import load_dotenv

load_dotenv()

APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")

ACTOR_ID = "compass/crawler-google-places"

SEARCH_LOCATION = "Kulon Progo, Yogyakarta, Indonesia"