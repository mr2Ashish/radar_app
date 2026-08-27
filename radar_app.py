import streamlit as st
from google import genai
from google.genai import types
import json, urllib.parse, math, time, pandas as pd, requests, re, datetime
from duckduckgo_search import DDGS
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Aryavarta AI Radar 360", page_icon="⚡", layout="wide")

API_KEY = st.secrets.get("GEMINI_API_KEY", "") if hasattr(st, "secrets") else ""
WEBHOOK = st.secrets.get("WEBHOOK_URL", "") if hasattr(st, "secrets") else ""

with st.sidebar:
    st.header("⚡ Radar Command Center")
    if not API_KEY: API_KEY = st.text_input("Gemini API Key:", type="password").strip()
    if not WEBHOOK: WEBHOOK = st.text_input("Sheets Webhook URL:", type="password").strip()
    markets = st.multiselect("Scan Radius:", ["Local (Maharashtra)", "National (India)", "Global Export"], default=["Local (Maharashtra)"])
    max_leads = st.slider("Target Intelligence Profiles:", min_value=2, max_value=20, value=20)
    st.divider()
    max_dist_filter = st.slider("🎯 Max Distance Filter (km from Chikhali):", 50, 3000, 3000)
    test_mode = st.toggle("🧪 Zero-Quota Test Mode", value=False, help="Turn OFF to use real AI.")

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

def search_news(q, mx=3):
    res = []
    try:
        with DDGS() as d:
            for r in d.text(q, max_results=mx): 
                res.append(f"Title: {r.get('title')} | Body: {r.get('body')}")
    except Exception: 
        pass 
    return res

def call_gemini(prompt):
    model_name = 'gemini-3.6-flash' 
    for i in range(2):
        try:
            r = client.models.generate_content(
                model=model_name, 
                contents=prompt, 
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            return json.loads(r.text)
        except Exception as e:
            if i == 0: time.sleep(3)
            else: raise e

# --- 2. ENGINE ---
def scan_engine(mode):
    if test_mode:
        st.info("Test Mode Active: Returning Mock Data.")
        return []

    q_map = {
        "panels": {"Local (Maharashtra)": "manufacturing plant expansion MIDC Pune Maharashtra electrical panel requirement", "National (India)": "new manufacturing plant commissioning India electrical panels"},
        "services": {"Local (Maharashtra)": "plant shutdown maintenance commissioning electrical MIDC Pune", "National (India)": "electrical instrumentation site engineer plant shutdown India"},
        "networking": {"Local (Maharashtra)": '(site:linkedin.com/company) "Procurement" "EPC" Pune', "National (India)": '(site:linkedin.com/company) "Procurement Head" "Manufacturing" India'}
    }
    
    query_dict = q_map.get(mode, q_map["panels"])
    raw_data = []
    for m in markets: 
        search_term = query_dict.get(m, query_dict["Local (Maharashtra)"])
        raw_data.extend(search_news(search_term, mx=2))

    analysis_prompt = f"""
    You are an industrial lead generator. Generate up to {max_leads} realistic corporate targets in India requiring Aryavarta Automation's services.
    Context from web (if any): {json.dumps(raw_data)}. Use your internal knowledge if web context is empty.
    
    You MUST return ONLY a JSON ARRAY of objects. 
    CRITICAL GEOGRAPHY: "lat" MUST be between 15.0 and 28.0. "lon" MUST be between 72.0 and 85.0 (Strictly inside India).
    
    Exact keys required per object:
    - company, location, lat (float), lon (float), project, trust_score, source_url
    - company_overview: 2 sentences max.
    - strategic_vision: 1 sentence.
    - partner_criteria: 1 sentence.
    - client_problem: Specific electrical/operational issue.
    - primary_solution: The panel or service solving it.
    - deal_expansion: Complementary products (cable trays, glands, etc).
    - integration_workflow: How it installs.
    - resolution_roadmap: Brief steps.
    - contact: Object with key_name, key_role, email, phone.
    """
    
    try: 
        base_leads = call_gemini(analysis_prompt)
    except Exception as e: 
        st.error(f"⚠️ Search Failed. Ensure your API Key is valid. Error: {e}")
        return []

    leads = []
    for l in base_leads:
        try:
            l["dist"] = calc_dist(float(l.get("lat", PUNE_COORDS["lat"])), float(l.get("lon", PUNE_COORDS["lon"])))
            l["maps"] = build_maps_url(l.get('company',''), l.get('location',''))
            l["link"] = f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(l.get('company','') + ' ' + l.get('contact',{}).get('key_name',''))}"
            leads.append(l)
        except Exception: pass

    leads.sort(key=lambda x: x.get("dist", 0))
    return leads[:max_leads]

# --- 3. UI RENDERER ---
def render_leads(leads, mode):
    filtered_leads = [l for l in leads if l['dist'] <= max_dist_filter]
    if not filtered_leads:
        st.warning(f"⚠️ Targets were found, but none were within your {max_dist_filter} km filter limit.")
        return
    
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("🛡️ Verified Intelligence Profiles", len(filtered_leads))
    kpi2.metric("🔥 Local Ecosystem Partners (<50km)", sum(1 for l in filtered_leads if l['dist'] < 50))
    kpi3.metric("📍 Engineering Base", "Chikhali, Pune")
    st.divider()

    crm_sync_data = []
    for i, l in enumerate(filtered_leads):
        dist = l['dist']
        is_export = dist > 1500
        curr = "USD ($)" if is_export else "INR (₹)"
        
        p_cnt = st.session_state.get(f"p_cnt_{mode}_{i}", 3)
        e_cnt = st.session_state.get(f"e_cnt_{mode}_{i}", 7)
        qty_str = f"{p_cnt} Panels" if mode in ["panels", "networking"] else f"{e_cnt} Man-Days"
        est_val = (p_cnt * (2200 if is_export else 175000)) if mode in ["panels", "networking"] else (e_cnt * (150 if is_export else 6500))
        est_str = f"{ '$' if is_export else '₹' }{est_val:,} {curr}"
        
        pay_term = st.session_state.get(f"pt_{mode}_{i}", "30% Advance, 60% Dispatch, 10% Commissioning")
        fatsat_val = st.session_state.get(f"fs_{mode}_{i}", "Factory Acceptance Testing (FAT) Included")
        notes_val = st.session_state.get(f"notes_{mode}_{i}", "")
        
        # --- FIXED: ADDING PANEL/MAN-DAY QUANTITIES TO CRM PAYLOAD ---
        sheet_profile = f"🏭 OVERVIEW:\n{l.get('company_overview', '')}\n\n🎯 VISION:\n{l.get('strategic_vision', '')}\n\n🤝 CRITERIA:\n{l.get('partner_criteria', '')}"
        sheet_tech = f"⚠️ PROBLEM:\n{l.get('client_problem', '')}\n\n✅ SOLUTION:\n{l.get('primary_solution', '')}\n\n🛣️ ROADMAP:\n{l.get('resolution_roadmap', '')}"
        sheet_deal = f"📦 EXPANSION:\n{l.get('deal_expansion', '')}\n\n⚙️ WORKFLOW:\n{l.get('integration_workflow', '')}"
        sheet_score = f"📋 REQUIREMENT: {qty_str}\n💰 ESTIMATE: {est_str}\n\nTerms: {pay_term}\nQA: {fatsat_val}"
        
        # --- FIXED: FULL OUTREACH SCRIPTS FOR CRM ---
        corp_email = f"Subject: Technical Vendor Empanelment - {l.get('company')}\n\nDear {l.get('contact',{}).get('key_name', 'Procurement Team')},\n\nWe manufacture IE-compliant Control Panels and deploy E&I Site Engineers from Pune. We understand the priority of addressing: {l.get('client_problem', '')}\n\nAryavarta Scope: {l.get('primary_solution', '')}\nTarget Quantity: {qty_str}\n\nWe welcome the opportunity to submit our profile for your Vendor List.\n\nsupport@aryavartaautomation.com"
        wa_msg = f"Hello {l.get('contact',{}).get('key_name', 'Sir/Madam')},\nGreetings from Aryavarta Automation (Pune). We solve {str(l.get('client_problem', ''))[:50]}... with custom panels. Can we share our catalog? www.aryavartaautomation.com"
        call_script = f"1. Intro: Good morning {l.get('contact',{}).get('key_name')}, from Aryavarta Automation.\n2. Hook: We help eliminate {str(l.get('client_problem', ''))[:50]}...\n3. CTA: Can I send our technical catalog?"
        inmail_text = f"Hi {l.get('contact',{}).get('key_name')}, I lead partnerships at Aryavarta Automation. Given your focus at {l.get('company')}, I'd welcome the opportunity to connect."

        sheet_outreach = f"👤 {l.get('contact',{}).get('key_name', '')} | 📧 {l.get('contact',{}).get('email', '')} | 📞 {l.get('contact',{}).get('phone', '')}\n\n📧 EMAIL:\n{corp_email}\n\n💬 WHATSAPP:\n{wa_msg}\n\n📞 CALL SCRIPT:\n{call_script}"

        crm_sync_data.append({
            "mode": mode.capitalize(), "company": l.get('company', ''), "location": l.get('location', ''),
            "distance": dist, "project_scope": l.get('project', ''), "panels_mandays": qty_str,
            "client_problem": l.get('client_problem', ''), "aryavarta_solution": l.get('primary_solution', ''),
            "value_add": l.get('resolution_roadmap', ''), "commercial_estimate": est_str,
            "payment_terms": pay_term, "testing_protocol": fatsat_val, 
            "decision_maker": l.get('contact', {}).get('key_name', ''), "role": l.get('contact', {}).get('key_role', ''),
            "email": l.get('contact', {}).get('email', ''), "phone": l.get('contact', {}).get('phone', ''),
            "source_url": l.get('source_url', ''), "sales_notes": notes_val,
            "company_profile": sheet_profile, "tech_bottleneck": sheet_tech,
            "deal_expansion": sheet_deal, "commercial_scoring": sheet_score,
            "ready_outreach": sheet_outreach
        })

    c1, c2, c3 = st.columns([2, 1, 1])
    c1.subheader(f"🛡️ Active {len(filtered_leads)} Corporate Dossiers")
    
    if c2.button(f"☁️ Sync to Sheets CRM", key=f"s_{mode}"):
        if WEBHOOK:
            success_count = 0
            for record in crm_sync_data:
                try:
                    res = requests.post(WEBHOOK, json=record, timeout=10)
                    if res.status_code == 200: success_count += 1
                except Exception: pass
            st.toast(f"✅ Synced {success_count} detailed dossiers to CRM!")
        else: st.warning("⚠️ Webhook URL missing.")

    for i, l in enumerate(filtered_leads):
        with st.expander(f"#{i+1}. {l.get('company')} — {l.get('location')} ({l['dist']} km)", expanded=(i==0)):
            t_overview, t_tech, t_deal, t_comm, t_outreach = st.tabs(["🏢 Profile", "🔧 Tech Fix", "📦 Deal Expand", "💰 Commercials", "🚀 Outreach"])
            
            with t_overview:
                st.write(f"**Business & Manufacturing Function:**\n{l.get('company_overview')}")
                st.write(f"**Strategic Vision:**\n{l.get('strategic_vision')}")
                st.write(f"**Partner Criteria:**\n{l.get('partner_criteria')}")
                st.markdown(f"[📍 Google Maps]({l.get('maps')}) | [💼 LinkedIn]({l.get('link')})")

            with t_tech:
                st.error(f"**Client Bottleneck:**\n{l.get('client_problem')}")
                st.success(f"**Aryavarta Solution:**\n{l.get('primary_solution')}")
                st.info(f"**Resolution Roadmap:**\n{l.get('resolution_roadmap')}")

            with t_deal:
                st.markdown(f"**Expansion Opportunities:**\n{l.get('deal_expansion')}")
                st.write(f"**Integration Workflow:**\n{l.get('integration_workflow')}")

            with t_comm:
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    st.selectbox("Payment:", ["30% Advance, 60% Dispatch, 10% Comms", "Net 30"], key=f"pt_{mode}_{i}")
                    st.selectbox("QA:", ["FAT Included", "SAT Support"], key=f"fs_{mode}_{i}")
                with col_c2:
                    if mode in ["panels", "networking"]:
                        st.number_input("Panels:", min_value=1, value=3, key=f"p_cnt_{mode}_{i}")
                    else:
                        st.number_input("Man-Days:", min_value=1, value=7, key=f"e_cnt_{mode}_{i}")
                    st.info(f"Budgetary Estimate: {crm_sync_data[i]['commercial_estimate']}")

            with t_outreach:
                st.info(f"**👤 {l.get('contact',{}).get('key_name')}** | ✉️ `{l.get('contact',{}).get('email')}` | 📞 `{l.get('contact',{}).get('phone')}`")
                
                # --- FIXED: RESTORED FULL MULTI-TAB OUTREACH UI ---
                o_em, o_wa, o_call, o_li = st.tabs(["📧 Email", "💬 WhatsApp", "📞 Call Script", "💼 LinkedIn"])
                
                with o_em:
                    st.text_area("Ready Email:", corp_email, height=180, key=f"em_txt_{mode}_{i}")
                    em_to = l.get('contact',{}).get('email','')
                    gmail_url = f"https://mail.google.com/mail/?view=cm&fs=1&to={em_to if '@' in em_to else ''}&su={urllib.parse.quote('Technical Vendor Empanelment - Aryavarta Automation')}&body={urllib.parse.quote(corp_email)}"
                    st.link_button("🚀 1-Click Send via Gmail", gmail_url, type="primary")
                    
                with o_wa:
                    st.text_area("Ready WhatsApp:", wa_msg, height=120, key=f"wa_txt_{mode}_{i}")
                    clean_phone = re.sub(r'[^0-9]', '', str(l.get('contact',{}).get('phone','')))
                    wa_url = f"https://api.whatsapp.com/send?phone={clean_phone}&text={urllib.parse.quote(wa_msg)}" if clean_phone else f"https://api.whatsapp.com/send?text={urllib.parse.quote(wa_msg)}"
                    st.link_button("💬 1-Click Send via WhatsApp", wa_url, type="secondary")
                    
                with o_call:
                    st.markdown(call_script.replace('\n', '\n\n'))
                    
                with o_li:
                    st.text_area("LinkedIn Connect:", inmail_text, height=100, key=f"li_txt_{mode}_{i}")
                    st.link_button("💼 Open LinkedIn Profile", l.get('link'))

                st.divider()
                st.session_state[f"notes_{mode}_{i}"] = st.text_area("📝 Internal Sales Notes:", value=st.session_state.get(f"notes_{mode}_{i}", ""), key=f"notes_{mode}_{i}")

# --- 4. MAIN TABS ---
st.title("⚡ Aryavarta Global AI Radar Enterprise 360")
tab_p, tab_s, tab_n = st.tabs(["🏭 Panels & Sundries", "👷 E&I Site Services", "🤝 Strategic Networking"])

with tab_p:
    if st.button("🚀 Scan Panel Opportunities", type="primary", key="bp"):
        with st.status("Scanning projects...", expanded=True): st.session_state.p_leads = scan_engine("panels")
    if 'p_leads' in st.session_state: render_leads(st.session_state.p_leads, "panels")

with tab_s:
    if st.button("🚀 Scan Site Engineer Contracts", type="primary", key="bs"):
        with st.status("Scanning contracts...", expanded=True): st.session_state.s_leads = scan_engine("services")
    if 's_leads' in st.session_state: render_leads(st.session_state.s_leads, "services")

with tab_n:
    if st.button("🤝 Discover Networking Partners", type="primary", key="bn"):
        with st.status("Scanning directories...", expanded=True): st.session_state.n_leads = scan_engine("networking")
    if 'n_leads' in st.session_state: render_leads(st.session_state.n_leads, "networking")
