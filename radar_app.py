import streamlit as st
from google import genai
from google.genai import types
import json, urllib.parse, math, time, pandas as pd, requests, re, datetime
from duckduckgo_search import DDGS
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Aryavarta AI Radar Bulletproof", page_icon="⚡", layout="wide")

API_KEY = st.secrets.get("GEMINI_API_KEY", "") if hasattr(st, "secrets") else ""
WEBHOOK = st.secrets.get("WEBHOOK_URL", "") if hasattr(st, "secrets") else ""

with st.sidebar:
    st.header("⚡ Radar Command Center")
    if not API_KEY: API_KEY = st.text_input("Gemini API Key:", type="password").strip()
    if not WEBHOOK: WEBHOOK = st.text_input("Sheets Webhook URL:", type="password").strip()
    markets = st.multiselect("Scan Radius:", ["Local (Maharashtra)", "National (India)", "Global Export"], default=["Local (Maharashtra)"])
    max_leads = st.slider("Target Leads/Connections:", min_value=2, max_value=20, value=5)
    
    st.divider()
    max_dist_filter = st.slider("🎯 Max Distance Filter (km):", 50, 20000, 20000)
    test_mode = st.toggle("🧪 Zero-Quota Test Mode", value=True)

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

def search_news(q, mx=5): # Reduced max_results for Token Optimization
    res = []
    try:
        with DDGS() as d:
            for r in d.text(q, max_results=mx): 
                res.append(f"Title: {r.get('title')} | URL: {r.get('href')} | Snippet: {r.get('body')}")
    except Exception: pass
    return res

def call_gemini(prompt):
    for i in range(2):
        try:
            r = client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=types.GenerateContentConfig(response_mime_type="application/json"))
            return json.loads(r.text)
        except Exception as e:
            if ("429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)) and i == 0:
                time.sleep(15)
            else: raise e

# --- 2. OPTIMIZED ENGINE ---
def scan_engine(mode):
    if test_mode:
        time.sleep(0.3)
        if mode == "networking":
            mock = [
                ("Rahul Deshmukh", "EPC Project Director", "L&T Electrical & Automation", "Pune", 18.7320, 73.6760, "Strategic partner for subcontracting panel fabrication and E&I site engineers for upcoming substations.", "rahul.d@larsentoubro.com", "linkedin.com/in/rahul-deshmukh-epc"),
                ("Sneha Kulkarni", "Procurement Head", "Forbes Marshall", "Pimpri MIDC, Pune", 18.6250, 73.8010, "High potential for recurring OEM supply of APFC, VFD panels and cable trays for their boiler systems.", "skulkarni@forbesmarshall.com", "linkedin.com/in/sneha-kulkarni-procurement")
            ]
            leads = []
            for n, r, c, loc, lat, lon, val, em, lk in mock[:max_leads]:
                leads.append({
                    "company": c, "project": f"Networking: {r}", "location": loc, "lat": lat, "lon": lon,
                    "trust_score": "Verified LinkedIn Profile", "credibility_proof": "Active Corporate Presence",
                    "source_name": "LinkedIn / Directory", "source_url": lk,
                    "offer": val, "problem": "Seeking reliable, IE-compliant local automation vendors.", 
                    "why_us": "Aryavarta offers turnkey panels and sundries from Chikhali.",
                    "dist": calc_dist(lat, lon), "maps": build_maps_url(c, loc), "link": lk,
                    "contact": {"key_name": n, "key_role": r, "email": em, "phone": "Ask on Connect"}
                })
            return leads
        else:
            return [{"company": "Tata Motors Ltd", "project": "Assembly Line Maintenance", "location": "Chakan MIDC, Pune", "lat": 18.7500, "lon": 73.8500, "trust_score": "99% Verified", "credibility_proof": "Official Notice", "source_name": "News", "source_url": "https://tatamotors.com", "offer": "Certified E&I Engineers", "problem": "Risk of downtime.", "why_us": "Immediate dispatch from Chikhali.", "dist": calc_dist(18.7500, 73.8500), "maps": build_maps_url("Tata Motors", "Chakan MIDC"), "link": "https://linkedin.com", "contact": {"key_name": "Plant Head", "key_role": "Decision Maker", "email": "maintenance@tatamotors.com", "phone": "+91 20 6613 1111"}}]

    # Query Optimization for Token Efficiency
    q_map = {
        "panels": {"Local (Maharashtra)": "manufacturing plant expansion MIDC Pune electrical panel", "National (India)": "new manufacturing plant factory setup India electrical panels", "Global Export": "water treatment plant Middle East Africa electrical panel"},
        "services": {"Local (Maharashtra)": "plant shutdown commissioning electrical instrumentation MIDC Pune", "National (India)": "electrical instrumentation site engineer plant shutdown India", "Global Export": "instrumentation commissioning site engineer project Middle East"},
        "networking": {"Local (Maharashtra)": '(site:linkedin.com/in/ OR site:linkedin.com/company/) ("Procurement" OR "EPC Contractor" OR "Project Manager") "Automation" Pune', "National (India)": '(site:linkedin.com/in/) ("Procurement" OR "Electrical Consultant") "Manufacturing" India', "Global Export": '(site:linkedin.com/in/) "Procurement Director" "Oil and Gas" OR "Water Treatment" Middle East'}
    }[mode]

    raw_news = []
    fetch_per_market = max(3, math.ceil(max_leads / len(markets)))
    for m in markets: 
        raw_news.extend(search_news(q_map[m], mx=fetch_per_market))
    
    if not raw_news: return []

    if mode == "networking":
        analysis_prompt = f"""
        Extract up to {max_leads} distinct professionals/companies for B2B networking from this raw search data: {json.dumps(raw_news)}.
        Return JSON list: company, project (put their Role/Title here), location, lat (approx float), lon (approx float), offer (Strategic Value - why Aryavarta should connect), contact (JSON object with key_name, email, phone, website - guess from context or output 'Ask on Connect').
        Keep text ultra-short to save tokens.
        """
    else:
        analysis_prompt = f"""
        Extract {max_leads} industrial projects from: {json.dumps(raw_news)}.
        Return JSON list: company, project, location, lat, lon, trust_score, credibility_proof, offer, problem, why_us, source_url. Keep text short (max 15 words per field).
        """
        
    try: 
        base_leads = call_gemini(analysis_prompt)
    except Exception: 
        st.error("❌ Quota limit reached. Switch to Test Mode in sidebar.")
        st.stop()

    leads = []
    for l in base_leads:
        l["dist"] = calc_dist(float(l.get("lat", PUNE_COORDS["lat"])), float(l.get("lon", PUNE_COORDS["lon"])))
        l["maps"] = build_maps_url(l['company'], l['location'])
        if "link" not in l:
            l["link"] = f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(l.get('company', '') + ' ' + l.get('contact', {}).get('key_name', ''))}"
        leads.append(l)

    leads.sort(key=lambda x: x["dist"])
    return leads[:max_leads]

# --- 3. UI RENDERER ---
def render_ui(leads, mode):
    filtered_leads = [l for l in leads if l['dist'] <= max_dist_filter]
    if not filtered_leads:
        st.warning(f"⚠️ No leads found within {max_dist_filter} km.")
        return

    st.subheader(f"🛡️ Active {len(filtered_leads)} {'Networking Targets' if mode=='networking' else 'Opportunities'}")
    st.divider()

    for i, l in enumerate(filtered_leads):
        dist = l['dist']
        hotness = "🌍 Global" if dist > 1500 else ("🔥 Local" if dist < 50 else "⚡ Regional")
        
        with st.expander(f"#{i+1}. {l.get('contact', {}).get('key_name', 'Network Target')} | {l.get('company')} ({dist} km)", expanded=(i==0)):
            
            if mode == "networking":
                # STRATEGIC NETWORKING VIEW
                st.markdown("#### 🔒 Partner Trust & Verification Matrix")
                chk1, chk2, chk3 = st.columns(3)
                with chk1: st.checkbox("ZaubaCorp/MCA Status Active", key=f"n1_{i}")
                with chk2: st.checkbox("LinkedIn Profile Authentic & Active", key=f"n2_{i}")
                with chk3: st.checkbox("GST/Website Cross-Verified", key=f"n3_{i}")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"### 🤝 {l['company']}")
                    st.markdown(f"**👤 Target Person:** {l.get('contact', {}).get('key_name')} ({l.get('project')})")
                    st.markdown(f"**🎯 Strategic Value to Aryavarta:** {l.get('offer')}")
                    st.markdown(f"[📍 Location Map]({l['maps']}) | [💼 Open LinkedIn Profile]({l['link']})")
                    
                    st.info("**Aryavarta Products to Pitch:** IMCC/VFD Panels, Cable Trays, Sensors, On-Site Commissioning Engineers.")
                
                with col2:
                    st.markdown("### 📞 Multi-Channel Networking Outreach")
                    
                    # Connection Scripts integrating Aryavarta Products
                    tab_li, tab_em, tab_cl = st.tabs(["LinkedIn", "Email", "Cold Call"])
                    with tab_li:
                        li_msg = f"Hi {l.get('contact', {}).get('key_name', 'Team')}, I lead Aryavarta Automation in Chikhali, Pune. We manufacture IE-compliant Control Panels (MCC/VFD/PLC) and provide E&I Site Engineers. Would love to connect and explore synergies for {l['company']}."
                        st.code(li_msg, language="text")
                        st.link_button("Send LinkedIn Connect", l['link'])
                    with tab_em:
                        em_msg = f"Subject: Automation Vendor Registration - Aryavarta Automation (Pune)\n\nHi {l.get('contact', {}).get('key_name', 'Team')},\n\nI'm reaching out from Aryavarta Automation. We are a Chikhali-based manufacturer of IE-compliant electrical panels (MCC, PCC, VFD, APFC) and sundry items (Cable Trays, Sensors). We also deploy certified E&I Site Engineers globally.\n\nWe would like to register as a trusted vendor for your upcoming projects. Are you the right person to speak with regarding vendor empanelment?\n\nProfile: www.aryavartaautomation.com"
                        st.code(em_msg, language="text")
                    with tab_cl:
                        st.markdown(f"*Ring Ring...*\n\n**You:** Hello, is this {l.get('contact', {}).get('key_name', 'the Procurement team')}?\n\n**You:** I’m calling from Aryavarta Automation, based locally in Pune. I know you're busy, but we manufacture highly reliable control panels and provide on-site E&I engineers. We'd love to drop by or send our catalog to be considered for your approved vendor list. Can I share our profile over WhatsApp?")
            
            else:
                # EXISTING BANT DEAL CLOSER VIEW (Abridged for code size)
                st.markdown("#### ✅ Deal Readiness & BANT Checklist")
                chk1, chk2 = st.columns(2)
                with chk1: st.checkbox("Drawings Verified", key=f"c1_{mode}_{i}")
                with chk2: st.checkbox("IE Compliance", key=f"c2_{mode}_{i}")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"### 🏢 {l['project']}")
                    st.markdown(f"**📦 Offer:** {l['offer']}\n\n**🔧 Problem:** {l['problem']}")
                with col2:
                    st.info(f"**👤 Decision Maker:** {l['contact'].get('key_name')} ({l['contact'].get('key_role')})")

# --- 4. MAIN APP ---
st.title("⚡ Aryavarta Global AI Radar Bulletproof")
st.caption("Panels • Sundry Materials • E&I Engineers • Strategic Networking")

tab_p, tab_s, tab_n = st.tabs(["🏭 Active Deals (Panels)", "👷 Active Deals (Services)", "🤝 Strategic Networking"])

with tab_p:
    if st.button("🚀 Scan Panel Deals", type="primary", key="bp"):
        with st.status("Scanning...", expanded=True): st.session_state.p_leads = scan_engine("panels")
    if 'p_leads' in st.session_state: render_ui(st.session_state.p_leads, "panels")

with tab_s:
    if st.button("🚀 Scan Service Deals", type="primary", key="bs"):
        with st.status("Scanning...", expanded=True): st.session_state.s_leads = scan_engine("services")
    if 's_leads' in st.session_state: render_ui(st.session_state.s_leads, "services")

with tab_n:
    st.markdown("### Build a 100% Trustable Circle of Buyers & Partners")
    st.caption("Find EPC Contractors, OEMs, and Procurement Heads to build long-term relationships for Panel & Sundry sales.")
    if st.button("🤝 Discover Networking Partners", type="primary", key="bn"):
        with st.status("Scanning LinkedIn & Corporate Directories for Verified Leaders...", expanded=True):
            st.session_state.n_leads = scan_engine("networking")
    if 'n_leads' in st.session_state: render_ui(st.session_state.n_leads, "networking")
