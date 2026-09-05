import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
import json, urllib.parse, math, time, requests, re

# --- 1. CONFIGURATION & SCHEMAS ---
st.set_page_config(page_title="Aryavarta AI Radar 360", page_icon="⚡", layout="wide")
API_KEY = st.secrets.get("GEMINI_API_KEY", "") if hasattr(st, "secrets") else ""
WEBHOOK = st.secrets.get("WEBHOOK_URL", "") if hasattr(st, "secrets") else ""

class Contact(BaseModel):
    key_name: str
    key_role: str
    email: str
    phone: str

class Lead(BaseModel):
    company: str
    location: str
    lat: float = Field(default=18.5204)
    lon: float = Field(default=73.8567)
    project: str
    trust_score: str
    source_url: str = Field(description="MUST be the direct URL to the specific news article, press release, or tender. NEVER a google.com search link.")
    exact_problem_quote: str = Field(description="A verbatim sentence from the source article proving they are currently expanding, upgrading, or facing downtime.")
    company_overview: str
    strategic_vision: str
    partner_criteria: str
    client_problem: str
    primary_solution: str
    deal_expansion: str
    integration_workflow: str
    resolution_roadmap: str
    contact: Contact
    call_script_custom: str

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
    models = ['gemini-1.5-pro', 'gemini-1.5-flash'] 
    err = ""
    bt = chr(96) * 3  
    
    for m in models:
        for _ in range(3):
            try:
                r = client.models.generate_content(
                    model=m, 
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=list[Lead],
                        tools=[{"google_search": {}}]
                    )
                )
                if not getattr(r, 'text', None): raise Exception("Empty AI text.")
                clean_json = r.text.replace(bt + 'json', '').replace(bt, '').strip()
                return json.loads(clean_json)
            except Exception as e:
                err = str(e)
                if "429" in err or "503" in err: time.sleep(5) 
                else: break 
    raise Exception(f"Google Cloud Error: {err}")

# --- 2. ENGINE ---
def scan_engine(mode):
    if test_mode: return []
    
    # THE FIX: Aggressive Intent-Scraping Prompt
    prompt = f"""ROLE: Elite B2B Intelligence AI. Target Market: Food/Beverage/Dairy/FMCG in {" and ".join(markets) if markets else "Local (Maharashtra)"}.
    ACTION REQUIRED: Use Google Search to find {max_leads} REAL manufacturing plants WITH ACTIVE, IMMEDIATE NEEDS. 
    
    CRITICAL QUALITY CONTROL:
    DO NOT just list random active factories. You MUST find companies actively facing problems, undergoing facility expansions, posting tenders/RFPs, or announcing maintenance/automation upgrades. 
    Search specifically for news combining the location with keywords like "plant expansion", "automation upgrade", "production halted", "electrical tender", or "maintenance shutdown".

    CRITICAL DIRECTIVES FOR SOURCE EVIDENCE:
    1. 'source_url' MUST be the exact, direct live web address of the news article, press release, or tender document. 
    2. ABSOLUTELY NO 'google.com/search' LINKS. Do not return generic search engine result pages.
    3. 'exact_problem_quote' MUST be a verbatim copy-pasted sentence directly from that article proving their active need/problem.
    
    Return ONLY a valid JSON array of these active-intent companies."""
    
    leads = []
    try: 
        leads = call_gemini(prompt)
    except Exception as e: 
        st.error(f"⚠️ Scan Failed. Please try clicking scan again. Details: {e}")
        return []

    if not leads:
        st.error("⚠️ AI could not find verified active expansion/downtime news right now. Please scan again.")
        return []

    for l in leads:
        l["dist"] = calc_dist(l.get("lat", 18.5204), l.get("lon", 73.8567))
        try:
            dest = urllib.parse.quote(str(l.get('company','')) + ' ' + str(l.get('location','')))
            l["maps"] = f"https://www.google.com/maps/dir/?api=1&origin={urllib.parse.quote(CHIKHALI_ADDR)}&destination={dest}"
            kw = urllib.parse.quote(str(l.get('company','')) + ' ' + str(l.get('contact',{}).get('key_name','')))
            l["link"] = f"https://www.linkedin.com/search/results/people/?keywords={kw}"
        except Exception: pass

    return sorted(leads, key=lambda x: x.get("dist", 0))

# --- 3. UI RENDERER ---
def render_leads(leads, mode):
    filtered_leads = [l for l in leads if l.get('dist', 0) <= max_dist_filter]
    
    if not filtered_leads:
        st.warning(f"⚠️ No active targets found strictly within {max_dist_filter} km. Expanding radius to show available profiles.")
        filtered_leads = leads[:max_leads]
    
    c1, c2, c3 = st.columns(3)
    c1.metric("🛡️ Active Intent Profiles", len(filtered_leads))
    c2.metric("🔥 Local (<50km)", sum(1 for l in filtered_leads if l['dist'] < 50))
    c3.metric("📍 Base", "Chikhali, Pune")
    st.divider()

    crm_data = []
    for i, l in enumerate(filtered_leads):
        dist, exp = l['dist'], l['dist'] > 1500
        qty = st.session_state.get(f"p_{mode}_{i}", 3 if mode!="services" else 7)
        q_str = f"{qty} Panels" if mode!="services" else f"{qty} Man-Days"
        est = (qty * (2200 if exp else 175000)) if mode!="services" else (qty * (150 if exp else 6500))
        est_str = f"{'$' if exp else '₹'}{est:,} {'USD' if exp else 'INR'}"
        
        c = l.get('contact',{})
        mail_txt = f"Subject: Automation Support - {l.get('company')}\n\nDear {c.get('key_name', 'Team')},\nWe manufacture IE-compliant LV Panels (MCC/PLC) for food operations. We noticed your recent operational updates and can directly solve: {l.get('client_problem')}\n\nAryavarta Solution: {l.get('primary_solution')}\nReq: {q_str}\n\nsupport@aryavartaautomation.com\n+91 8045802403"
        wa_txt = f"Hi {c.get('key_name', '')}, Greetings from Aryavarta Automation. We specialize in LV panels for food plants & can assist with {str(l.get('client_problem',''))[:60]}... View catalog: www.aryavartaautomation.com"
        
        crm_data.append({"company": l.get('company'), "location": l.get('location'), "dist": dist, "est": est_str, "contact": c.get('key_name'), "email": c.get('email'), "phone": c.get('phone')})

    c1, c2 = st.columns([3, 1])
    c1.subheader(f"🛡️ Active {len(filtered_leads)} Corporate Dossiers")
    if c2.button("☁️ Sync to CRM", key=f"s_{mode}"):
        if WEBHOOK:
            success = sum(1 for r in crm_data if requests.post(WEBHOOK, json=r, timeout=10).status_code == 200)
            st.toast(f"✅ Synced {success} dossiers!")
        else: st.warning("⚠️ Webhook missing.")

    for i, l in enumerate(filtered_leads):
        with st.expander(f"#{i+1}. {l.get('company')} — {l.get('location')} ({l['dist']} km)", expanded=(i==0)):
            t1, t2, t3, t4 = st.tabs(["🏢 Profile & Tech", "💰 Commercials", "🚀 Outreach", "📝 CRM Notes"])
            with t1:
                st.write(f"**Vision:** {l.get('strategic_vision')} | **Criteria:** {l.get('partner_criteria')}")
                st.markdown(f"[📍 Maps]({l.get('maps', '#')}) | [💼 LinkedIn]({l.get('link', '#')})")
                st.error(f"**Active Problem/Requirement:** {l.get('client_problem')}")
                
                src, q = l.get('source_url', ''), l.get('exact_problem_quote', '')
                
                # THE FIX: Prevents rendering highlight text if AI disobeys and gives a Google Search link
                if src and "google.com" in src.lower():
                    st.warning("⚠️ AI provided a generic search link instead of a direct article.")
                    st.markdown(f"🔗 **[View Search Results]({src})**")
                    st.info(f"**Extracted Data:**\n\n\"{q}\"")
                elif src and q:
                    words = q.split()
                    if len(words) >= 6:
                        prefix = urllib.parse.quote(' '.join(words[:3]))
                        suffix = urllib.parse.quote(' '.join(words[-3:]))
                        frag = f"{prefix},{suffix}"
                    else:
                        frag = urllib.parse.quote(q)
                        
                    st.markdown(f"🎯 **[Jump into Exact Paragraph on Source Article]({src}#:~:text={frag})**")
                    st.info(f"**Verbatim Source Evidence:**\n\n\"{q}\"")
                elif src: 
                    st.markdown(f"🔗 **[Source Link]({src})**")
                    
                st.success(f"**Solution:** {l.get('primary_solution')} \n\n**Expand:** {l.get('deal_expansion')}")
            
            with t2:
                col1, col2 = st.columns(2)
                col1.selectbox("Payment:", ["30% Adv, 60% Disp, 10% Comms", "Net 30"], key=f"pt_{mode}_{i}")
                col1.selectbox("QA:", ["FAT Included", "SAT Support"], key=f"fs_{mode}_{i}")
                col2.number_input("Qty/Days:", min_value=1, value=(3 if mode!="services" else 7), key=f"p_{mode}_{i}")
                col2.info(f"Estimate: {crm_data[i]['est']}")
            
            with t3:
                c = l.get('contact',{})
                st.info(f"👤 {c.get('key_name', 'N/A')} | ✉️ `{c.get('email', 'N/A')}` | 📞 `{c.get('phone', 'N/A')}`")
                
                st.markdown("### 📞 Master Sales Call Script")
                st.success(l.get('call_script_custom', 'No script generated.'))
                st.divider()
                
                st.text_area("Email:", mail_txt, height=100, key=f"em_{mode}_{i}")
                st.link_button("🚀 Gmail", f"https://mail.google.com/mail/?view=cm&fs=1&to={c.get('email','')}&su=Automation&body={urllib.parse.quote(mail_txt)}")
                st.text_area("WhatsApp:", wa_txt, height=100, key=f"wa_{mode}_{i}")
                st.link_button("💬 WhatsApp", f"https://api.whatsapp.com/send?phone={re.sub(r'[^0-9]', '', str(c.get('phone','')))}&text={urllib.parse.quote(wa_txt)}")
            
            with t4:
                st.text_area("Sales Notes:", key=f"n_{mode}_{i}")

# --- 4. TABS ---
st.title("⚡ Aryavarta AI Radar 360")
tp, ts, tn = st.tabs(["🏭 Panels", "👷 Services", "🤝 Networking"])
with tp:
    if st.button("🚀 Scan Panel Opportunities", type="primary"): 
        with st.status("Hunting for Active Projects..."): st.session_state.lp = scan_engine("panels")
    if 'lp' in st.session_state: render_leads(st.session_state.lp, "panels")
with ts:
    if st.button("🚀 Scan Service Contracts", type="primary"): 
        with st.status("Hunting for Active Projects..."): st.session_state.ls = scan_engine("services")
    if 'ls' in st.session_state: render_leads(st.session_state.ls, "services")
with tn:
    if st.button("🤝 Discover Partners", type="primary"): 
        with st.status("Hunting for Active Projects..."): st.session_state.ln = scan_engine("networking")
    if 'ln' in st.session_state: render_leads(st.session_state.ln, "networking")
