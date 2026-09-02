import streamlit as st
from google import genai
import json, urllib.parse, math, time, pandas as pd, requests, re, datetime
from duckduckgo_search import DDGS

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Aryavarta AI Radar 360", page_icon="⚡", layout="wide")

API_KEY = st.secrets.get("GEMINI_API_KEY", "") if hasattr(st, "secrets") else ""
WEBHOOK = st.secrets.get("WEBHOOK_URL", "") if hasattr(st, "secrets") else ""

with st.sidebar:
    st.header("⚡ Radar Command Center")
    if not API_KEY: API_KEY = st.text_input("Gemini API Key:", type="password").strip()
    if not WEBHOOK: WEBHOOK = st.text_input("Sheets Webhook URL:", type="password").strip()
    markets = st.multiselect("Scan Radius:", ["Local (Maharashtra)", "National (India)", "Global Export"], default=["Local (Maharashtra)"])
    max_leads = st.slider("Target Intelligence Profiles:", min_value=2, max_value=20, value=10)
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

def search_news(q, mx=4):
    res = []
    try:
        with DDGS() as d:
            for r in d.text(q, max_results=mx): 
                # FIXED: Now capturing the exact URL to build the Pinpoint link
                res.append(f"Title: {r.get('title')} | URL: {r.get('href')} | Body: {r.get('body')}")
    except Exception: 
        pass 
    return res

def call_gemini(prompt):
    model_name = 'gemini-3.6-flash' 
    for i in range(3):
        try:
            r = client.models.generate_content(
                model=model_name, 
                contents=prompt
            )
            clean_text = r.text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        except Exception as e:
            if i == 2:
                raise e
            time.sleep(3)

# --- 2. ENGINE ---
def scan_engine(mode):
    if test_mode: return []

    target_region = " and ".join(markets)
    q_map = {
        "panels": {
            "Local (Maharashtra)": '(Food OR Beverage OR Dairy OR FMCG) "manufacturing plant" OR "expansion" ("MCC panel" OR "PLC panel" OR "VFD") Pune OR Maharashtra', 
            "National (India)": '(Food OR FMCG OR Brewery) "factory setup" ("Low voltage panel" OR "automation") India'
        },
        "services": {
            "Local (Maharashtra)": '(Food OR Dairy) "plant shutdown" OR "maintenance" "electrical instrumentation" Maharashtra', 
            "National (India)": '(FMCG OR Beverage) "electrical instrumentation site engineer" India'
        },
        "networking": {
            "Local (Maharashtra)": '(site:linkedin.com/company) "Procurement" ("Food" OR "FMCG") Pune', 
            "National (India)": '(site:linkedin.com/company) "Procurement Head" ("Food" OR "Beverage") India'
        }
    }
    
    query_dict = q_map.get(mode, q_map["panels"])
    raw_data = []
    for m in markets: 
        search_term = query_dict.get(m, query_dict["Local (Maharashtra)"])
        raw_data.extend(search_news(search_term, mx=3))

    analysis_prompt = f"""
    ROLE: You are an elite B2B Industrial Intelligence AI. Your ONLY target market is Food, Beverage, FMCG, and Dairy manufacturing plants in {target_region}.
    OUR SERVICES: Aryavarta Automation exclusively manufactures Low Voltage (LV) panels (MCC, PLC, VFD, Relay-based panels) and provides electrical automation services.
    
    Context from live web search: {json.dumps(raw_data)}. 
    
    Using the context above and your internal knowledge, generate exactly {max_leads} highly detailed corporate targets. 
    You MUST return ONLY a valid JSON ARRAY of objects. Do not include markdown blocks.
    CRITICAL GEOGRAPHY: "lat" MUST be between 15.0 and 28.0. "lon" MUST be between 72.0 and 85.0.
    
    Exact keys required per object:
    - company, location, lat (float), lon (float), project, trust_score
    - source_url: The exact URL from the context. If using internal knowledge, leave as "".
    - exact_problem_quote: A verbatim 4-to-6 word copy-paste from the text that proves the problem exists (used for pinpoint URL highlighting). Leave as "" if no exact text exists.
    - company_overview: Detail their exact food/beverage manufacturing scope.
    - strategic_vision: Their scaling/production goals.
    - partner_criteria: 1 sentence on vendor requirements.
    - client_problem: Must be highly technical, verified, and specific to food processing (e.g., washdown environment failures).
    - primary_solution: Specifically how our MCC, PLC, VFD, or Relay panel directly solves it.
    - deal_expansion: Complementary products (cable trays, glands, sensors).
    - integration_workflow: How it installs in a food-grade environment.
    - resolution_roadmap: Brief steps.
    - contact: Object with key_name, key_role, email, phone. (CRITICAL: Extract ONLY verified corporate HQ numbers and standard procurement emails).
    - call_script_custom: Write a highly professional, multi-stage B2B sales call script to close this specific deal. 
    """
    
    try: 
        base_leads = call_gemini(analysis_prompt)
    except Exception as e: 
        st.error(f"⚠️ Search Failed. Ensure your API Key is valid and try lowering target count to 5. Error: {e}")
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
    if not leads: return 
    
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
        qty_str = f"{p_cnt} LV Panels" if mode in ["panels", "networking"] else f"{e_cnt} Man-Days"
        est_val = (p_cnt * (2200 if is_export else 175000)) if mode in ["panels", "networking"] else (e_cnt * (150 if is_export else 6500))
        est_str = f"{ '$' if is_export else '₹' }{est_val:,} {curr}"
        
        pay_term = st.session_state.get(f"pt_{mode}_{i}", "30% Advance, 60% Dispatch, 10% Commissioning")
        fatsat_val = st.session_state.get(f"fs_{mode}_{i}", "Factory Acceptance Testing (FAT) Included")
        notes_val = st.session_state.get(f"notes_{mode}_{i}", "")
        
        sheet_profile = f"🏭 OVERVIEW:\n{l.get('company_overview', '')}\n\n🎯 VISION:\n{l.get('strategic_vision', '')}\n\n🤝 CRITERIA:\n{l.get('partner_criteria', '')}"
        sheet_tech = f"⚠️ PROBLEM:\n{l.get('client_problem', '')}\n\n✅ SOLUTION:\n{l.get('primary_solution', '')}\n\n🛣️ ROADMAP:\n{l.get('resolution_roadmap', '')}"
        sheet_deal = f"📦 EXPANSION:\n{l.get('deal_expansion', '')}\n\n⚙️ WORKFLOW:\n{l.get('integration_workflow', '')}"
        sheet_score = f"📋 REQUIREMENT: {qty_str}\n💰 ESTIMATE: {est_str}\n\nTerms: {pay_term}\nQA: {fatsat_val}"
        
        corp_email = f"Subject: Automation & LV Panel Empanelment - {l.get('company')}\n\nDear {l.get('contact',{}).get('key_name', 'Procurement Team')},\n\nWe manufacture IE-compliant Low Voltage Panels (MCC, PLC, VFD) specifically designed for food and beverage operations. We understand the operational priority of addressing: {l.get('client_problem', '')}\n\nAryavarta Engineered Solution: {l.get('primary_solution', '')}\nTarget Requirement: {qty_str}\n\nWe welcome the opportunity to submit our profile for your Vendor List.\n\nsupport@aryavartaautomation.com\n+91 8045802403"
        wa_msg = f"Hello {l.get('contact',{}).get('key_name', 'Sir/Madam')},\nGreetings from Aryavarta Automation (Pune). We specialize in LV/MCC panels for the food industry and can directly solve {str(l.get('client_problem', ''))[:60]}... Can we share our technical catalog? www.aryavartaautomation.com"
        call_script = l.get('call_script_custom', 'No script generated.')
        inmail_text = f"Hi {l.get('contact',{}).get('key_name')}, I lead partnerships at Aryavarta Automation. We provide IE-compliant LV/MCC panels for food industries. Given your focus at {l.get('company')}, I'd welcome the opportunity to connect."

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
                st.write(f"**Food/Beverage Operations:**\n{l.get('company_overview')}")
                st.write(f"**Strategic Vision:**\n{l.get('strategic_vision')}")
                st.write(f"**Partner Criteria:**\n{l.get('partner_criteria')}")
                st.markdown(f"[📍 Google Maps]({l.get('maps')}) | [💼 LinkedIn]({l.get('link')})")

            with t_tech:
                st.error(f"**Detailed Food Plant Bottleneck:**\n{l.get('client_problem')}")
                
                # --- FIXED: DYNAMIC PINPOINT PROBLEM SOURCE LINK ---
                src_url = l.get('source_url', '')
                quote = l.get('exact_problem_quote', '')
                if src_url and src_url.startswith("http") and quote:
                    pinpoint_link = f"{src_url}#:~:text={urllib.parse.quote(quote)}"
                    st.markdown(f"🎯 **[Direct Problem Source (Jumps to exact paragraph)]({pinpoint_link})**")
                elif src_url and src_url.startswith("http"):
                    st.markdown(f"🔗 **[Company/Project Source Link]({src_url})**")
                else:
                    search_q = urllib.parse.quote(f'"{l.get("company", "")}" {l.get("client_problem", "")}')
                    st.markdown(f"🔍 **[Verify Problem via Deep Search]({f'https://www.google.com/search?q={search_q}'})**")
                
                st.success(f"**Aryavarta LV Panel Solution:**\n{l.get('primary_solution')}")
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
                        st.number_input("LV Panels Required:", min_value=1, value=3, key=f"p_cnt_{mode}_{i}")
                    else:
                        st.number_input("Man-Days:", min_value=1, value=7, key=f"e_cnt_{mode}_{i}")
                    st.info(f"Budgetary Estimate: {crm_sync_data[i]['commercial_estimate']}")

            with t_outreach:
                st.info(f"**👤 {l.get('contact',{}).get('key_name')}** | ✉️ `{l.get('contact',{}).get('email')}` | 📞 `{l.get('contact',{}).get('phone')}`")
                
                o_em, o_wa, o_call, o_li = st.tabs(["📧 Email", "💬 WhatsApp", "📞 Professional Call Script", "💼 LinkedIn"])
                
                with o_em:
                    st.text_area("Ready Email:", value=corp_email, height=180, key=f"em_{mode}_{i}")
                    em_to = l.get('contact',{}).get('email','')
                    gmail_url = f"https://mail.google.com/mail/?view=cm&fs=1&to={em_to if '@' in em_to else ''}&su={urllib.parse.quote('Automation & LV Panel Empanelment - Aryavarta')}&body={urllib.parse.quote(corp_email)}"
                    st.link_button("🚀 1-Click Send via Gmail", gmail_url, type="primary")
                    
                with o_wa:
                    st.text_area("Ready WhatsApp:", value=wa_msg, height=120, key=f"wa_{mode}_{i}")
                    clean_phone = re.sub(r'[^0-9]', '', str(l.get('contact',{}).get('phone','')))
                    wa_url = f"https://api.whatsapp.com/send?phone={clean_phone}&text={urllib.parse.quote(wa_msg)}" if clean_phone else f"https://api.whatsapp.com/send?text={urllib.parse.quote(wa_msg)}"
                    st.link_button("💬 1-Click Send via WhatsApp", wa_url, type="secondary")
                    
                with o_call:
                    st.markdown(call_script)
                    
                with o_li:
                    st.text_area("LinkedIn Connect:", value=inmail_text, height=100, key=f"li_{mode}_{i}")
                    st.link_button("💼 Open LinkedIn Profile", l.get('link'))

                st.divider()
                st.text_area("📝 Internal Sales Notes (Syncs to CRM):", key=f"notes_{mode}_{i}")

# --- 4. MAIN TABS ---
st.title("⚡ Aryavarta Global AI Radar Enterprise 360")
tab_p, tab_s, tab_n = st.tabs(["🏭 LV Panels & Sundries", "👷 E&I Site Services", "🤝 Strategic Networking"])

with tab_p:
    if st.button("🚀 Scan Food Industry Panel Opportunities", type="primary", key="bp"):
        with st.status("Scanning projects...", expanded=True): st.session_state.p_leads = scan_engine("panels")
    if 'p_leads' in st.session_state: render_leads(st.session_state.p_leads, "panels")

with tab_s:
    if st.button("🚀 Scan Food Plant Maintenance Contracts", type="primary", key="bs"):
        with st.status("Scanning contracts...", expanded=True): st.session_state.s_leads = scan_engine("services")
    if 's_leads' in st.session_state: render_leads(st.session_state.s_leads, "services")

with tab_n:
    if st.button("🤝 Discover Food/FMCG Partners", type="primary", key="bn"):
        with st.status("Scanning directories...", expanded=True): st.session_state.n_leads = scan_engine("networking")
    if 'n_leads' in st.session_state: render_leads(st.session_state.n_leads, "networking")
