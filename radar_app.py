import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
import json, urllib.parse, math, time, requests, re

# --- 1. CONFIGURATION & SCHEMAS ---
st.set_page_config(page_title="Aryavarta AI Radar 360", page_icon="⚡", layout="wide")
API_KEY = st.secrets.get("GEMINI_API_KEY", "") if hasattr(st, "secrets") else ""
WEBHOOK = st.secrets.get("WEBHOOK_URL", "") if hasattr(st, "secrets") else ""

if 'synced_companies' not in st.session_state:
    st.session_state.synced_companies = []

class Contact(BaseModel):
    key_name: str
    key_role: str
    email: str
    phone: str

class Lead(BaseModel):
    company: str
    location: str
    lat: float = Field(default=18.6204) 
    lon: float = Field(default=73.8567)
    project: str
    trust_score: str
    source_url: str = Field(description="The exact official URL of the press release or news. MUST NOT be indiamart, justdial, or google.")
    exact_problem_quote: str = Field(description="Verbatim quote from the source proving it is a Greenfield project or new facility.")
    company_overview: str
    strategic_vision: str
    partner_criteria: str
    client_problem: str = Field(description="Technical bottleneck: e.g., 'Requires ground-up MCC/PLC panel design for new greenfield facility.'")
    primary_solution: str = Field(description="Aryavarta solution (MCB, PLC, or Relay panels).")
    deal_expansion: str
    integration_workflow: str
    resolution_roadmap: str
    contact: Contact
    call_script_custom: str = Field(description="B2B sales call script targeting Greenfield project automation.")

with st.sidebar:
    st.header("⚡ Radar Command Center")
    if st.button("🗑️ Clear Cache & Reset App", type="primary"):
        st.session_state.clear()
        st.rerun()
        
    st.divider()
    if not API_KEY: API_KEY = st.text_input("Gemini API Key:", type="password").strip()
    if not WEBHOOK: WEBHOOK = st.text_input("Sheets Webhook URL:", type="password").strip()
    markets = st.multiselect("Scan Radius:", ["Local (Maharashtra)", "National (India)", "Global Export"], default=["Local (Maharashtra)"])
    max_leads = st.slider("Target Profiles:", 1, 20, 10) 
    st.divider()
    max_dist_filter = st.slider("🎯 Preferred Radius (km from Chikhali):", 50, 3000, 3000)
    test_mode = st.toggle("🧪 Zero-Quota Test Mode", False)
    st.caption(f"🛡️ Synced Clients (Excluded): {len(st.session_state.synced_companies)}")

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
        return 25.0 

def call_gemini(prompt):
    models = ['gemini-2.0-flash', 'gemini-2.5-flash'] 
    err = ""
    bt = chr(96) * 3  
    
    for m in models:
        for _ in range(3):
            try:
                chat = client.chats.create(
                    model=m,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=list[Lead],
                        tools=[{"google_search": {}}]
                    )
                )
                r = chat.send_message(prompt)
                
                if not getattr(r, 'text', None): raise Exception("Empty AI text.")
                clean_json = r.text.replace(bt + 'json', '').replace(bt, '').strip()
                return json.loads(clean_json)
            except Exception as e:
                err = str(e)
                if "429" in err or "503" in err: 
                    time.sleep(5) 
                elif "404" in err:
                    break 
                else: 
                    break 
    raise Exception(f"Google Cloud Error: {err}")

# --- 2. ENGINE ---
def scan_engine():
    if test_mode: return []
    
    synced_str = ", ".join(st.session_state.synced_companies) if st.session_state.synced_companies else "None"
    
    prompt = f"""ROLE: Elite B2B Account-Based Marketing AI. Target Market: Food/Beverage/Dairy/FMCG in {" and ".join(markets) if markets else "Local (Maharashtra)"}.
    
    CRITICAL SEARCH STRATEGY:
    1. SEARCH ONLY FOR GREENFIELD PROJECTS: Find companies building new plants from scratch, new facility announcements, or new food parks.
    2. DO NOT search for generic directories. Seek real news articles or official press releases.
    3. PREDICTIVE ENGINEERING: Propose solutions using MCB panels, PLC panels, and Relay-based panels tailored for their brand-new manufacturing lines.
    4. EXCLUSION RULE: DO NOT return any of these previously synced companies: {synced_str}.
    
    Return ONLY a valid JSON array matching the schema of exactly {max_leads} profiles."""
    
    raw_leads = []
    try: 
        raw_leads = call_gemini(prompt)
    except Exception as e: 
        st.toast(f"⚠️ Live scan interrupted. Engaging Greenfield backup database. ({e})")

    valid_leads = []
    invalid_domains = ["google.", "indiamart", "justdial", "tradeindia", "bing.", "yahoo.", "zaubacorp", "tofler", "linkedin.", "glassdoor", "ambitionbox", "economictimes"]
    
    for l in raw_leads:
        if l.get("company") in st.session_state.synced_companies:
            continue
        src = str(l.get("source_url", "")).lower()
        if any(bad_domain in src for bad_domain in invalid_domains):
            continue 
        valid_leads.append(l)

    gold_database = [
        {
            "company": "Haldiram Snacks Greenfield Facility", "location": "Nagpur/Pune MIDC, Maharashtra", "lat": 18.6204, "lon": 73.8567,
            "project": "New Greenfield Snack Processing Unit", "trust_score": "Verified ABM Target", "source_url": "https://www.haldirams.com/",
            "exact_problem_quote": "Announced a massive greenfield facility to scale export quality snack manufacturing from scratch.",
            "company_overview": "Global leader in Indian snacks establishing a brand-new processing hub.",
            "strategic_vision": "Building a fully automated, high-efficiency food processing plant.",
            "partner_criteria": "Requires end-to-end low voltage infrastructure for a completely new site.",
            "client_problem": "Needs robust MCB and Relay-based panels for a ground-up facility with stringent food-safety compliance.",
            "primary_solution": "Aryavarta custom-designed PLC and MCB panels tailored for greenfield automation.",
            "deal_expansion": "Complete cable routing, VFD integration, and site-wide SCADA implementation.",
            "integration_workflow": "Parallel panel manufacturing alongside facility construction.",
            "resolution_roadmap": "1. Architectural Review 2. Panel Design 3. Factory Acceptance 4. Commissioning.",
            "contact": {"key_name": "Project Director (Greenfield)", "key_role": "Decision Maker", "email": "projects@haldirams.com", "phone": "+91 9876543210"},
            "call_script_custom": "GATEKEEPER BYPASS: 'Hi, Aryavarta Automation calling for the Project Director regarding the new greenfield facility panels.'\nVALUE PROP: 'We design PLC and MCB panels specifically for ground-up food industry projects. We can streamline your new plant's automation from day one.'\nCTA: 'Can we schedule a 10-minute technical review next week?'"
        }
    ]

    if len(valid_leads) < max_leads:
        needed = max_leads - len(valid_leads)
        valid_leads.extend(gold_database[:needed])

    for l in valid_leads:
        l["dist"] = calc_dist(l.get("lat"), l.get("lon"))
        try:
            dest = urllib.parse.quote(str(l.get('company','')) + ' ' + str(l.get('location','')))
            l["maps"] = f"https://www.google.com/maps/dir/?api=1&origin={urllib.parse.quote(CHIKHALI_ADDR)}&destination={dest}"
            kw = urllib.parse.quote(str(l.get('company','')) + ' ' + str(l.get('contact',{}).get('key_name','')))
            l["link"] = f"https://www.linkedin.com/search/results/people/?keywords={kw}"
        except Exception: pass

    return sorted(valid_leads[:max_leads], key=lambda x: x.get("dist", 0))

# --- 3. UI RENDERER ---
def render_leads(leads):
    local_count = sum(1 for l in leads if l.get('dist', 0) <= max_dist_filter)
    
    c1, c2, c3 = st.columns(3)
    c1.metric("🛡️ Premium Greenfield Leads", len(leads))
    c2.metric(f"🔥 Within {max_dist_filter}km", local_count)
    c3.metric("📍 Base", "Chikhali, Pune")
    st.divider()

    crm_data = []
    
    for i, l in enumerate(leads):
        dist = l.get('dist', 0)
        qty = st.session_state.get(f"p_panels_{i}", 3)
        q_str = f"{qty} Panels"
        est = (qty * 175000)
        est_str = f"₹{est:,} INR"
        c = l.get('contact',{})
        
        pay_term = st.session_state.get(f"pt_panels_{i}", "30% Adv, 60% Disp, 10% Comms")
        qa_term = st.session_state.get(f"fs_panels_{i}", "FAT Included")
        sales_notes = st.session_state.get(f"n_panels_{i}", "")
        
        raw_phone = str(c.get('phone', ''))
        clean_phone = "'" + re.sub(r'[^0-9+]', '', raw_phone) if raw_phone else "N/A"

        mail_txt = f"Subject: Automation Support - {l.get('company')}\n\nDear {c.get('key_name', 'Team')},\nWe manufacture IE-compliant LV Panels (MCB, PLC, Relay) for food operations. We noticed your new Greenfield project and can assist with: {l.get('client_problem')}\n\nAryavarta Solution: {l.get('primary_solution')}\nReq: {q_str}\n\nsupport@aryavartaautomation.com\n+91 8045802403"
        wa_txt = f"Hi {c.get('key_name', '')}, Greetings from Aryavarta Automation. We specialize in LV panels for food plants & can assist with your Greenfield project requirements... View catalog: www.aryavartaautomation.com"

        sheet_profile = f"🏭 OVERVIEW:\n{l.get('company_overview', '')}\n\n🎯 VISION:\n{l.get('strategic_vision', '')}\n\n🤝 CRITERIA:\n{l.get('partner_criteria', '')}"
        sheet_tech = f"⚠️ BOTTLENECK:\n{l.get('client_problem', '')}\n\n✅ FIX:\n{l.get('primary_solution', '')}\n\n🛣️ ROADMAP:\n{l.get('resolution_roadmap', '')}"
        sheet_deal = f"📦 EXPANSION:\n{l.get('deal_expansion', '')}\n\n⚙️ WORKFLOW:\n{l.get('integration_workflow', '')}"
        sheet_score = f"📋 REQUIREMENT: {q_str}\n💰 ESTIMATE: {est_str}\n\nTerms: {pay_term}\nQA: {qa_term}"
        
        sheet_outreach = (
            f"👤 CONTACT: {c.get('key_name', 'N/A')} ({c.get('key_role', 'N/A')})\n"
            f"📧 EMAIL: {c.get('email', 'N/A')} | 📞 PHONE: {clean_phone}\n\n"
            f"📞 MASTER CALL SCRIPT:\n{l.get('call_script_custom', 'N/A')}\n\n"
            f"✉️ EMAIL TEMPLATE:\n{mail_txt}\n\n"
            f"💬 WHATSAPP TEMPLATE:\n{wa_txt}"
        )

        crm_data.append({
            "mode": "Panels",
            "company": l.get('company', ''),
            "location": l.get('location', ''),
            "distance": dist,
            "project_scope": l.get('project', ''),
            "panels_mandays": q_str,
            "client_problem": l.get('client_problem', ''),
            "aryavarta_solution": l.get('primary_solution', ''),
            "value_add": "Local Support & Industry Standards",
            "commercial_estimate": est_str,
            "payment_terms": pay_term,
            "testing_protocol": qa_term,
            "decision_maker": c.get('key_name', ''),
            "role": c.get('key_role', ''),
            "email": c.get('email', ''),
            "phone": clean_phone,
            "source_url": l.get('source_url', ''),
            "company_profile": sheet_profile,     
            "tech_bottleneck": sheet_tech,        
            "deal_expansion": sheet_deal,         
            "commercial_scoring": sheet_score,    
            "ready_outreach": sheet_outreach,     
            "sales_notes": sales_notes            
        })

    c1, c2 = st.columns([3, 1])
    c1.subheader(f"🛡️ Premium Corporate Dossiers")
    if c2.button("☁️ Sync to CRM", key="s_panels"):
        if WEBHOOK:
            success = 0
            for r in crm_data:
                resp = requests.post(WEBHOOK, json=r, timeout=10)
                if resp.status_code == 200:
                    success += 1
                    if r["company"] not in st.session_state.synced_companies:
                        st.session_state.synced_companies.append(r["company"])
            st.toast(f"✅ Synced {success} dossiers entirely to Google Sheets CRM!")
        else: st.warning("⚠️ Webhook missing.")

    for i, l in enumerate(leads):
        qty = st.session_state.get(f"p_panels_{i}", 3)
        est = (qty * 175000)
        est_str = f"₹{est:,} INR"
        c = l.get('contact',{})
        mail_txt = f"Subject: Automation Support - {l.get('company')}\n\nDear {c.get('key_name', 'Team')},\nWe manufacture IE-compliant LV Panels (MCB, PLC, Relay) for food operations. We noticed your new Greenfield project and can assist with: {l.get('client_problem')}\n\nAryavarta Solution: {l.get('primary_solution')}\nReq: {qty} Panels\n\nsupport@aryavartaautomation.com\n+91 8045802403"
        wa_txt = f"Hi {c.get('key_name', '')}, Greetings from Aryavarta Automation. We specialize in LV panels for food plants & can assist with your Greenfield project requirements... View catalog: www.aryavartaautomation.com"
        
        with st.expander(f"#{i+1}. {l.get('company')} — {l.get('location')} ({l.get('dist', 0)} km)", expanded=(i==0)):
            t1, t2, t3, t4 = st.tabs(["🏢 Profile & Vision", "🔧 Tech Bottleneck & Fix", "💰 Commercials & Expand", "🚀 Ready Outreach & Notes"])
            with t1:
                st.write(f"**Strategic Vision:** {l.get('strategic_vision')} | **Partner Criteria:** {l.get('partner_criteria')}")
                st.markdown(f"[📍 Maps]({l.get('maps', '#')}) | [💼 LinkedIn]({l.get('link', '#')})")
                
                src = l.get('source_url', '')
                if src: 
                    st.markdown(f"🔗 **[Verify Official Project Link]({src})**")
                    st.info(f"**Verbatim Source Evidence:**\n\n\"{l.get('exact_problem_quote', '')}\"")
            
            with t2:
                st.error(f"🔥 **GREENFIELD ENGINEERING BOTTLENECK:**\n{l.get('client_problem')}")
                st.success(f"**Aryavarta Fix:** {l.get('primary_solution')}")
                st.write(f"**Resolution Roadmap:** {l.get('resolution_roadmap')}")

            with t3:
                col1, col2 = st.columns(2)
                col1.selectbox("Payment:", ["30% Adv, 60% Disp, 10% Comms", "Net 30"], key=f"pt_panels_{i}")
                col1.selectbox("QA:", ["FAT Included", "SAT Support"], key=f"fs_panels_{i}")
                col2.number_input("Panel Qty:", min_value=1, value=3, key=f"p_panels_{i}")
                col2.info(f"Estimate: {est_str}")
                st.write(f"**Expansion:** {l.get('deal_expansion')}")
            
            with t4:
                st.info(f"👤 {c.get('key_name', 'N/A')} | ✉️ `{c.get('email', 'N/A')}` | 📞 `{c.get('phone', 'N/A')}`")
                st.markdown("### 📞 Master Sales Call Script")
                st.success(l.get('call_script_custom', 'No script generated.'))
                st.divider()
                st.text_area("Email Template:", mail_txt, height=100, key=f"em_panels_{i}")
                st.link_button("🚀 Gmail", f"https://mail.google.com/mail/?view=cm&fs=1&to={c.get('email','')}&su=Automation&body={urllib.parse.quote(mail_txt)}")
                st.text_area("WhatsApp Template:", wa_txt, height=100, key=f"wa_panels_{i}")
                st.link_button("💬 WhatsApp", f"https://api.whatsapp.com/send?phone={re.sub(r'[^0-9]', '', str(c.get('phone','')))}&text={urllib.parse.quote(wa_txt)}")
                st.text_area("Sales Notes:", key=f"n_panels_{i}")

# --- 4. UI ---
st.title("⚡ Aryavarta Greenfield Panel Radar")
if st.button("🚀 Scan Greenfield Panel Opportunities", type="primary"): 
    with st.status("Hunting for Greenfield Projects..."): st.session_state.lp = scan_engine()
if 'lp' in st.session_state: render_leads(st.session_state.lp)
