import streamlit as st
from google import genai
from google.genai import types
import json, urllib.parse, math, time, requests, re

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Aryavarta AI Radar 360", page_icon="⚡", layout="wide")
API_KEY = st.secrets.get("GEMINI_API_KEY", "") if hasattr(st, "secrets") else ""
WEBHOOK = st.secrets.get("WEBHOOK_URL", "") if hasattr(st, "secrets") else ""

with st.sidebar:
    st.header("⚡ Radar Command Center")
    if not API_KEY: API_KEY = st.text_input("Gemini API Key:", type="password").strip()
    if not WEBHOOK: WEBHOOK = st.text_input("Sheets Webhook URL:", type="password").strip()
    markets = st.multiselect("Scan Radius:", ["Local (Maharashtra)", "National (India)", "Global Export"], default=["Local (Maharashtra)"])
    max_leads = st.slider("Target Profiles:", 1, 20, 10) 
    st.divider()
    max_dist_filter = st.slider("🎯 Max Dist (km from Chikhali):", 50, 3000, 3000)
    test_mode = st.toggle("🧪 Zero-Quota Test Mode", False)

if not API_KEY and not test_mode: st.warning("⚠️ API Key needed."); st.stop()
client = genai.Client(api_key=API_KEY) if not test_mode else None
PUNE_COORDS = {"lat": 18.6822, "lon": 73.8183}
CHIKHALI_ADDR = "Gat No. 1610, Dehu Alandi Road, Chikhali, Pune, Maharashtra 411062"

def calc_dist(lat, lon):
    try:
        dlat, dlon = math.radians(float(lat) - PUNE_COORDS["lat"]), math.radians(float(lon) - PUNE_COORDS["lon"])
        a = math.sin(dlat/2)**2 + math.cos(math.radians(PUNE_COORDS["lat"])) * math.cos(math.radians(float(lat))) * math.sin(dlon/2)**2
        return round(6371.0 * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))), 1)
    except Exception:
        return 15.0 

def call_gemini(prompt):
    models = ['gemini-2.0-flash', 'gemini-1.5-pro'] 
    err = ""
    for m in models:
        for _ in range(3):
            try:
                r = client.models.generate_content(
                    model=m, 
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        tools=[{"google_search": {}}]
                    )
                )
                if not getattr(r, 'text', None): raise Exception("Empty AI text.")
                clean_json = r.text.replace('```json', '').replace('
