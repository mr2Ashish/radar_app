import streamlit as st
from google import genai
from google.genai import types
import json, urllib.parse, math, time, pandas as pd, requests, re, datetime

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Aryavarta AI Radar 360", page_icon="⚡", layout="wide")

API_KEY = st.secrets.get("GEMINI_API_KEY", "") if hasattr(st, "secrets") else ""
WEBHOOK = st.secrets.get("WEBHOOK_URL", "") if hasattr(st, "secrets") else ""

with st.sidebar:
    st.header("⚡ Radar Command Center")
    if not API_KEY: API_KEY = st.text_input("Gemini API Key:", type="password").strip()
    if not WEBHOOK: WEBHOOK = st.text_input("Sheets Webhook URL:", type="password").strip()
    markets = st.multiselect("Scan Radius:", ["Local (Maharashtra)", "National (India)", "Global Export"], default=["Local (Maharashtra)"])
    
    max_leads = st.slider("Target Intelligence Profiles:", min_value=1, max_value=20, value=10) 
    
    st.divider()
    max_dist_filter = st.slider("🎯 Max Distance Filter (km from Chikhali):", 50, 3000, 3000)
    test_mode = st.toggle("🧪 Zero-Quota Test Mode", value=False)

if not API_KEY and not test_mode:
    st.warning("⚠️ Enter Gemini API Key in sidebar.")
    st.stop()

client = genai.Client(api_key=API_KEY) if not test_mode else None
PUNE_COORDS = {"lat": 18.6822, "lon": 73.8183}
CHIKHALI_ADDR = "Gat No. 1610, Dehu Alandi Road, Chikhali, Pune, Maharashtra 411062"

def calc_dist(lat, lon):
    R = 6371.0
    dlat, dlon = math.radians(lat - PUNE_COORDS["lat"]), math.radians(lon - PUNE_COORDS["lon"])
    a = math.sin(dlat/2)**2 + math.cos(math.radians(PUNE_COORDS["lat"])) * math.cos(math.radians(lat)) * math.sin(dlon/2)**2
    return round(R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))), 1)

def build_maps_url(comp, loc):
    return f"https://www.google.com/maps/dir/?api=1&origin={urllib.parse.quote(CHIKHALI_ADDR)}&destination={urllib.parse.quote(f'{comp} {loc}')}"

def call_gemini(prompt):
    # FIXED: Removed the deprecated '-latest' suffixes to prevent 404 crashes masking the real error
    fallback_models = ['gemini-1.5-pro', 'gemini-1.5-flash'] 
    
    last_error = ""
    for model_name in fallback_models:
        for i in range(3):
            try:
                r = client.models.generate_content(
                    model=model_name, 
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        tools=[{"google_search": {}}] 
                    )
                )
                clean_text = r.text.replace('```json', '').replace('
