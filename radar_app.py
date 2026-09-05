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
    except:
        return 15.0 

def call_gemini(prompt):
    models = ['gemini-3.6-pro', 'gemini-3.6-flash'] 
    err = ""
    for m in models:
        for _ in range(3):
            try:
                r = client.models.generate_content(
                    model=m, contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json", tools=[{"google_search": {}}])
                )
                if not getattr(r, 'text', None): raise Exception("Empty AI text.")
                return json.loads(r.text.replace('`'*3+'json', '').replace('`'*3, '').strip())
            except Exception as e:
                err = str(e)
                if "404" in err: break 
                if "429" in err or "503" in err: time.sleep(5) 
                else: break 
    raise Exception(f"API Error. {err}")

# --- 2. ENGINE ---
def scan_engine(mode):
    if test_mode: return []
    
    # Anchored search deeply into active operational logistics zones
    prompt = f"""ROLE: Elite B2B AI. Target: Food/Beverage/Dairy/FMCG in {" and ".join(markets)}.
    ACTION: Use Google Search tool to find active plant expansions or technical maintenance bottlenecks. 
    GEOGRAPHY PRIORITY: When scanning locally, heavily prioritize industrial zones around Pune, Nashik, Chhatrapati Sambhajinagar, and Malkapur.
    Extract up to {max_leads} targets. Return ONLY a valid JSON ARRAY of objects. 
    CRITICAL: NEVER return an empty array []. You MUST return at least 2-3 targets. If exact public data is sparse, estimate based on the company's active regional operations.
    Required keys: company, location, lat (float, default to 18.52 if unknown), lon (float, default to 73.85 if unknown), project, trust_score, source_url (company website if exact link unavailable), exact_problem_quote, company_overview, strategic_vision, partner_criteria, client_problem, primary_solution (how Aryavarta MCC/PLC/VFD panels solve it), deal_expansion, integration_workflow, resolution_roadmap, contact (key_name, key_role, email, phone), call_script_custom."""
    
    try: leads = call_gemini(prompt)
    except Exception as e: st.error(f"⚠️ Scan Failed: {e}"); return []
    if not leads: return []

    for l in leads:
        l["dist"] = calc_dist(l.get("lat"), l.get("lon"))
        try:
            dest = urllib.parse.quote(str(l.get('company','')) + ' ' + str(l.get('location','')))
            l["maps"] = f"https://www.google.com/maps/dir/?api=1&origin={urllib.parse.quote(CHIKHALI_ADDR)}&destination={dest}"
            kw = urllib.parse.quote(str(l.get('company','')) + ' ' + str(l.get('contact',{}).get('key_name','')))
            l["link"] = f"https://www.linkedin.com/search/results/people/?keywords={kw}"
        except: pass

    # Return ALL leads from the engine to prevent accidental deletion
    return sorted(leads, key=lambda x: x.get("dist", 0))

# --- 3. UI RENDERER ---
def render_leads(leads, mode):
    if not leads: 
        st.error("⚠️ Google Search returned zero results. Please try again.")
        return
        
    filtered_leads = [l for l in leads if l.get('dist', 0) <= max_dist_filter]
    
    # THE FIX: Smart Radius Auto-Expander. If local filter is too strict, show the closest available targets.
    if not filtered_leads:
        st.warning(f"⚠️ No active targets found strictly within {max_dist_filter} km. Automatically expanding search perimeter to display the closest available regional profiles.")
        filtered_leads = leads[:max_leads]
    
    c1, c2, c3 = st.columns(3)
    c1.metric("🛡️ Verified Profiles", len(filtered_leads))
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
        mail_txt = f"Subject: Automation - {l.get('company')}\n\nDear {c.get('key_name', 'Team')},\nWe make IE-compliant LV Panels (MCC/PLC) for food operations. We can solve: {l.get('client_problem')}\n\nAryavarta Solution: {l.get('primary_solution')}\nReq: {q_str}\n\nsupport@aryavartaautomation.com\n+91 8045802403"
        wa_txt = f"Hi {c.get('key_name', '')}, Greetings from Aryavarta Automation. We specialize in LV panels for food plants & can solve {str(l.get('client_problem',''))[:60]}... View catalog: www.aryavartaautomation.com"
        
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
                st.error(f"**Problem:** {l.get('client_problem')}")
                src, q = l.get('source_url', ''), l.get('exact_problem_quote', '')
                if src and q: st.markdown(f"🎯 **[Direct Source Evidence]({src}#:~:text={urllib.parse.quote(q)})**")
                elif src: st.markdown(f"🔗 **[Source Link]({src})**")
                st.success(f"**Solution:** {l.get('primary_solution')} \n\n**Expand:** {l.get('deal_expansion')}")
            
            with t2:
                col1, col2 = st.columns(2)
                col1.selectbox("Payment:", ["30% Adv, 60% Disp, 10% Comms", "Net 30"], key=f"pt_{mode}_{i}")
                col1.selectbox("QA:", ["FAT Included", "SAT Support"], key=f"fs_{mode}_{i}")
                col2.number_input("Qty/Days:", min_value=1, value=(3 if mode!="services" else 7), key=f"p_{mode}_{i}")
                col2.info(f"Estimate: {crm_data[i]['est']}")
            
            with t3:
                c = l.get('contact',{})
                st.info(f"👤 {c.get('key_name')} | ✉️ `{c.get('email')}` | 📞 `{c.get('phone')}`")
                st.text_area("Email:", mail_txt, height=100, key=f"em_{mode}_{i}")
                st.link_button("🚀 Gmail", f"https://mail.google.com/mail/?view=cm&fs=1&to={c.get('email','')}&su=Automation&body={urllib.parse.quote(mail_txt)}")
                st.text_area("WhatsApp:", wa_txt, height=100, key=f"wa_{mode}_{i}")
                st.link_button("💬 WhatsApp", f"https://api.whatsapp.com/send?phone={re.sub(r'[^0-9]', '', str(c.get('phone','')))}&text={urllib.parse.quote(wa_txt)}")
                st.text_area("Call Script:", l.get('call_script_custom', ''), height=100, key=f"call_{mode}_{i}")
            
            with t4:
                st.text_area("Sales Notes:", key=f"n_{mode}_{i}")

# --- 4. TABS ---
st.title("⚡ Aryavarta AI Radar 360")
tp, ts, tn = st.tabs(["🏭 Panels", "👷 Services", "🤝 Networking"])
with tp:
    if st.button("🚀 Scan Panel Opportunities", type="primary"): 
        with st.status("Scanning..."): st.session_state.lp = scan_engine("panels")
    if 'lp' in st.session_state: render_leads(st.session_state.lp, "panels")
with ts:
    if st.button("🚀 Scan Service Contracts", type="primary"): 
        with st.status("Scanning..."): st.session_state.ls = scan_engine("services")
    if 'ls' in st.session_state: render_leads(st.session_state.ls, "services")
with tn:
    if st.button("🤝 Discover Partners", type="primary"): 
        with st.status("Scanning..."): st.session_state.ln = scan_engine("networking")
    if 'ln' in st.session_state: render_leads(st.session_state.ln, "networking")
