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
    max_leads = st.slider("Target Intelligence Profiles:", min_value=2, max_value=20, value=4)
    st.divider()
    max_dist_filter = st.slider("🎯 Max Distance Filter (km from Chikhali):", 50, 20000, 20000)
    test_mode = st.toggle("🧪 Zero-Quota Test Mode", value=True, help="Test without burning Gemini API quota.")

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
                res.append(f"Title: {r.get('title')} | URL: {r.get('href')} | Body: {r.get('body')}")
    except Exception: pass
    return res

def gen_pdf(l, mode, quote_text, fatsat, pay_terms):
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, 805, f"ARYAVARTA AUTOMATION - {mode.upper()} PROPOSAL")
    c.setFont("Helvetica", 9)
    c.drawString(40, 788, "Gat No. 1610, Dehu Alandi Rd, Chikhali, Pune-411062 | GST: 27ABOFA4930E1ZH | Ph: 08045802403")
    c.setStrokeColorRGB(0.7, 0.7, 0.7)
    c.line(40, 778, 555, 778)
    
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, 755, f"Client: {l.get('company')} | Location: {l.get('location')} ({l.get('dist')} km)")
    c.setFont("Helvetica", 9)
    c.drawString(40, 738, f"Project Scope: {l.get('project')}")
    
    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, 705, "1. Identified Client Bottlenecks & Operational Needs:")
    c.setFont("Helvetica", 9)
    t1 = c.beginText(40, 690)
    t1.textLines(l.get('client_problem', l.get('problem', '')))
    c.drawText(t1)

    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, 605, "2. Aryavarta Engineered Deliverables & Commercials:")
    c.setFont("Helvetica", 9)
    t2 = c.beginText(40, 590)
    t2.textLines(f"- Deliverables: {l.get('primary_solution', l.get('offer', ''))}\n- Multi-Product Add-ons: {l.get('deal_expansion', 'Panels, Sundries & E&I Support')}\n- Commercial Terms: {pay_terms} | QA Protocol: {fatsat}\n- Estimated Valuation: {quote_text}")
    c.drawText(t2)

    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, 490, "3. 100% Problem Resolution Roadmap:")
    c.setFont("Helvetica", 9)
    t3 = c.beginText(40, 475)
    t3.textLines(f"- Roadmap: {l.get('resolution_roadmap', l.get('why_us', ''))}\n- Standard: 100% IE Rule Compliance & Rapid Dispatch from Chikhali, Pune.")
    c.drawText(t3)
    
    c.drawString(40, 85, "Authorized Sign-off: Aryavarta Automation Sales & Operations")
    c.drawString(40, 70, f"Source Ref: {l.get('source_url')} | support@aryavartaautomation.com | www.aryavartaautomation.com")
    c.save()
    return buf.getvalue()

def call_gemini(prompt):
    for i in range(2):
        try:
            r = client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=types.GenerateContentConfig(response_mime_type="application/json"))
            return json.loads(r.text)
        except Exception as e:
            if ("429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)) and i == 0:
                time.sleep(15)
            else: raise e

# --- 2. ENGINE ---
def scan_engine(mode):
    if test_mode:
        time.sleep(0.3)
        if mode == "panels":
            mock = [{
                "company": "Praj Industries Ltd", "location": "Bhosari MIDC, Pune", "lat": 18.6270, "lon": 73.8340,
                "project": "Bio-Ethanol Distillation Line 3 Power Automation & Motor Control Setup",
                "trust_score": "99% Verified (BSE Audited)", "source_url": "https://www.praj.net",
                "company_overview": "Global bio-energy, industrial biotechnology, and process engineering solutions provider.",
                "strategic_vision": "Expanding sustainable ethanol capacity while standardizing automated power distribution to achieve zero thermal trips.",
                "partner_criteria": "Requires strict compliance with hazardous-area flameproof standards, verified FAT, and local vendor support in Pune.",
                "client_problem": "High reactive power losses, harmonic distortion from variable-speed agitators, and thermal overload on legacy switchgear.",
                "primary_solution": "Custom-engineered Motor Control Centers (MCC), Power Control Centers (PCC), and VFD Distribution Panels with active harmonic mitigation.",
                "deal_expansion": "Supply of hot-dip galvanized cable trays, explosion-proof glands, copper lugs, terminal blocks, digital power meters, and 2-year AMC.",
                "integration_workflow": "Direct floor-mounting in MCC room with bottom cable entry, interfacing with plant DCS via Modbus TCP.",
                "resolution_roadmap": "1. Site SLD harmonic audit, 2. Fabrication of IE-compliant panels in Chikhali, 3. Witnessed FAT load simulation, 4. 24-hour on-site energization.",
                "contact": {"key_name": "Rajesh Mandhare", "key_role": "Head of Electrical Procurement", "email": "rajesh.m@praj.net", "phone": "+91 20 7180 2000"},
                "mca_verified": True, "linkedin_verified": True, "gst_verified": True
            }]
        elif mode == "services":
            mock = [{
                "company": "Tata Motors Ltd", "location": "Chakan MIDC, Pune", "lat": 18.7500, "lon": 73.8500,
                "project": "EV Assembly Line Annual Shutdown & Drive Commissioning",
                "trust_score": "99% Verified (Automotive Leader)", "source_url": "https://www.tatamotors.com",
                "company_overview": "India's largest commercial and EV passenger vehicle manufacturer operating high-speed automated assembly lines.",
                "strategic_vision": "Scaling EV manufacturing cadence with zero tolerated downtime across robotic spot-welding and conveyor drive lines.",
                "partner_criteria": "Certified E&I engineers with proven expertise in multi-axis drive synchronization and round-the-clock shift support.",
                "client_problem": "Critical 72-hour scheduled shutdown window requiring 100% re-calibration of 40+ servo drives, busbar torque auditing, and Profinet bus validation.",
                "primary_solution": "Deployment of certified Senior E&I Site Engineers and Instrumentation Specialists equipped with calibrated diagnostic kits for 24/7 shutdown coverage.",
                "deal_expansion": "Supply of replacement sensor probes, terminal junctions, control relays, pre-assembled wire harnesses, and post-shutdown emergency retainers.",
                "integration_workflow": "On-site stationing alongside Tata maintenance managers for immediate fault-tree clearing and loop testing.",
                "resolution_roadmap": "1. Pre-shutdown Megger insulation checks, 2. 4-20mA sensor loop calibration, 3. VFD/Servo drive communication tuning, 4. Witnessed live conveyor trial runs.",
                "contact": {"key_name": "Satish Patil", "key_role": "Plant Maintenance Head", "email": "satish.patil@tatamotors.com", "phone": "+91 20 6613 1111"},
                "mca_verified": True, "linkedin_verified": True, "gst_verified": True
            }]
        else:
            mock = [{
                "company": "L&T Electrical & Automation", "location": "Talegaon MIDC, Pune", "lat": 18.7320, "lon": 73.6760,
                "project": "Strategic Subcontracting & Regional Panel Manufacturing Empanelment",
                "trust_score": "Verified Corporate Entity", "source_url": "https://www.larsentoubro.com",
                "company_overview": "Global EPC infrastructure conglomerate managing substation, electrification, and industrial projects.",
                "strategic_vision": "Developing a robust tier-2 vendor ecosystem around Pune corridor for fast-turnaround panel manufacturing and site manpower deployment.",
                "partner_criteria": "Reliable manufacturing facilities adhering strictly to IE rules, documented fabrication checklists, and transparent commercial terms.",
                "client_problem": "Facing peak-season subcontracting bottlenecks, vendor communication delays, and high logistics overhead from distant suppliers.",
                "primary_solution": "Long-term partnership as an Approved Regional Panel Builder and Certified E&I Manpower Provider directly from Chikhali, Pune.",
                "deal_expansion": "OEM assembly of customized feeder panels, batch supply of perforated cable trays and sundries, and dedicated site commissioning crews.",
                "integration_workflow": "Formal vendor empanelment enabling direct RFQ dispatch for upcoming national and global infrastructure tenders.",
                "resolution_roadmap": "1. Factory audit at Aryavarta's Chikhali facility, 2. Submission of technical compliance dossier, 3. Master Services Agreement sign-off.",
                "contact": {"key_name": "Rahul Deshmukh", "key_role": "Chief Project Procurement Director", "email": "rahul.d@larsentoubro.com", "phone": "+91 22 6752 5656"},
                "mca_verified": True, "linkedin_verified": True, "gst_verified": True
            }]
        
        leads = []
        for l in mock[:max_leads]:
            l["dist"] = calc_dist(l["lat"], l["lon"])
            l["maps"] = build_maps_url(l["company"], l["location"])
            l["link"] = f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(l['company'] + ' ' + l['contact']['key_name'])}"
            leads.append(l)
        return leads

    # Live Mode
    q_map = {
        "panels": {"Local (Maharashtra)": "manufacturing plant expansion MIDC Pune Maharashtra electrical panel requirement", "National (India)": "new manufacturing plant commissioning industrial project factory setup India electrical panels", "Global Export": "water treatment industrial plant factory setup Middle East Africa electrical distribution panel"},
        "services": {"Local (Maharashtra)": "plant shutdown maintenance commissioning electrical instrumentation MIDC Pune Maharashtra", "National (India)": "electrical instrumentation site engineer maintenance plant shutdown contract India", "Global Export": "instrumentation commissioning site engineer project Middle East plant overhaul"},
        "networking": {"Local (Maharashtra)": '(site:linkedin.com/company OR site:zaubacorp.com) ("Procurement" OR "EPC Contractor" OR "Project Director") "Automation" Pune', "National (India)": '(site:linkedin.com/company OR site:zaubacorp.com) ("Procurement Head" OR "Electrical Consultant") "Manufacturing" India', "Global Export": '(site:linkedin.com/company OR site:dnb.com) "Procurement Director" "Oil and Gas" OR "Water Treatment" Middle East'}
    }[mode]

    raw_data = []
    fetch_count = max(3, math.ceil(max_leads / len(markets)))
    for m in markets: raw_data.extend(search_news(q_map[m], mx=fetch_count))
    if not raw_data: return []

    analysis_prompt = f"""
    Analyze this industrial intelligence data: {json.dumps(raw_data)}.
    Extract up to {max_leads} verified real corporate targets. Output a JSON list of objects with exact keys:
    - company, location, lat (approx float), lon (approx float), project, trust_score, source_url
    - company_overview: Detailed overview of what they manufacture and their operational scale.
    - strategic_vision: Future business goals and expansion vision.
    - partner_criteria: What they look for in a vendor partner.
    - client_problem: In-depth technical breakdown of the operational/electrical bottleneck they face.
    - primary_solution: Specific deliverable from Aryavarta Automation (MCC, PCC, VFD, APFC panels, or certified E&I Site Engineers).
    - deal_expansion: Exhaustive list of complementary products/services to sell (Cable Trays, Glands, Lugs, Sensors, AMC, Wiring).
    - integration_workflow: How the client will install and use our products inside their plant.
    - resolution_roadmap: 4-step engineering roadmap showing how Aryavarta eliminates their bottleneck 100%.
    - contact: JSON object with key_name, key_role, email, phone, website.
    - mca_verified (bool), linkedin_verified (bool), gst_verified (bool)
    """
    try: base_leads = call_gemini(analysis_prompt)
    except Exception: st.error("❌ API limit reached. Use Test Mode in sidebar."); st.stop()

    leads = []
    for l in base_leads:
        l["dist"] = calc_dist(float(l.get("lat", PUNE_COORDS["lat"])), float(l.get("lon", PUNE_COORDS["lon"])))
        l["maps"] = build_maps_url(l['company'], l['location'])
        l["link"] = f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(l.get('company','') + ' ' + l.get('contact',{}).get('key_name',''))}"
        leads.append(l)

    leads.sort(key=lambda x: x["dist"])
    return leads[:max_leads]

# --- 3. UI RENDERER ---
def render_leads(leads, mode):
    filtered_leads = [l for l in leads if l['dist'] <= max_dist_filter]
    if not filtered_leads:
        st.warning(f"⚠️ No targets found within {max_dist_filter} km.")
        return

    hot_local_count = sum(1 for l in filtered_leads if l['dist'] < 50)
    
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("🛡️ Verified Intelligence Profiles", len(filtered_leads))
    kpi2.metric("🔥 Local Ecosystem Partners (<50km)", hot_local_count)
    kpi3.metric("📍 Engineering Base", "Chikhali, Pune")
    st.divider()

    crm_sync_data = []
    for i, l in enumerate(filtered_leads):
        dist = l['dist']
        is_export = dist > 1500 or "Middle East" in l.get('location','') or "Africa" in l.get('location','')
        curr = "USD ($)" if is_export else "INR (₹)"
        
        p_cnt = st.session_state.get(f"p_cnt_{mode}_{i}", 3)
        e_cnt = st.session_state.get(f"e_cnt_{mode}_{i}", 7)
        qty_str = f"{p_cnt} Panels" if mode in ["panels", "networking"] else f"{e_cnt} Man-Days"
        est_val = (p_cnt * (2200 if is_export else 175000)) if mode in ["panels", "networking"] else (e_cnt * (150 if is_export else 6500))
        est_str = f"{ '$' if is_export else '₹' }{est_val:,} {curr}"
        
        pay_term = st.session_state.get(f"pt_{mode}_{i}", "30% Advance, 60% Dispatch, 10% Commissioning")
        fatsat_val = st.session_state.get(f"fs_{mode}_{i}", "Factory Acceptance Testing (FAT) Included")
        notes_val = st.session_state.get(f"notes_{mode}_{i}", "")
        
        crm_sync_data.append({
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "section": mode.capitalize(),
            "company": l.get('company'),
            "location": l.get('location'),
            "distance_km": dist,
            "project_scope": l.get('project'),
            "client_bottleneck": l.get('client_problem', l.get('problem')),
            "primary_solution": l.get('primary_solution', l.get('offer')),
            "deal_expansion": l.get('deal_expansion'),
            "resolution_roadmap": l.get('resolution_roadmap', l.get('why_us')),
            "commercial_estimate": est_str,
            "payment_milestones": pay_term,
            "testing_protocol": fatsat_val,
            "contact_person": l.get('contact', {}).get('key_name'),
            "role": l.get('contact', {}).get('key_role'),
            "email": l.get('contact', {}).get('email'),
            "phone": l.get('contact', {}).get('phone'),
            "source_reference": l.get('source_url'),
            "sales_notes": notes_val
        })

    c1, c2, c3 = st.columns([2, 1, 1])
    c1.subheader(f"🛡️ Active {len(filtered_leads)} 360° Corporate Dossiers")
    
    if c2.button(f"☁️ Sync to Sheets CRM", key=f"s_{mode}"):
        if WEBHOOK:
            try:
                res = requests.post(WEBHOOK, json=crm_sync_data, timeout=10)
                if res.status_code == 200: st.toast("✅ Synced 360° data to Google Sheet CRM!")
                else: st.error(f"❌ Webhook responded: {res.status_code}")
            except Exception as e: st.error(f"❌ Webhook Error: {e}")
        else: st.warning("⚠️ Webhook URL missing in sidebar.")
    
    df = pd.DataFrame(crm_sync_data)
    c3.download_button("📥 Export 360° CSV", df.to_csv(index=False).encode('utf-8'), f"Aryavarta_{mode}_360_CRM.csv", "text/csv", key=f"d_{mode}")

    for i, l in enumerate(filtered_leads):
        dist = l['dist']
        hotness = "🌍 Global" if dist > 1500 else ("🔥 Local (<50km)" if dist < 50 else "⚡ Regional")
        
        with st.expander(f"#{i+1}. {l.get('company')} — {l.get('location')} ({dist} km) | {hotness} | 🛡️ {l.get('trust_score', 'Verified')}", expanded=(i==0)):
            
            t_overview, t_tech, t_deal, t_comm, t_outreach = st.tabs([
                "🏢 Company Profile & Vision",
                "🔧 Technical Bottleneck & Fix",
                "📦 Deal Expansion & Sundries",
                "💰 Commercial Estimate & Scoring",
                "🚀 Ready Outreach (Email, WhatsApp, Call)"
            ])
            
            with t_overview:
                st.write(f"**Business & Manufacturing Function:**\n{l.get('company_overview')}")
                st.write(f"**Strategic Vision & Future Plans:**\n{l.get('strategic_vision')}")
                st.write(f"**What They Value in a Partner:**\n{l.get('partner_criteria')}")
                
                chk1, chk2, chk3 = st.columns(3)
                with chk1: st.checkbox("ZaubaCorp / MCA Active", value=l.get('mca_verified', True), key=f"mca_{mode}_{i}")
                with chk2: st.checkbox("LinkedIn Corporate Presence", value=l.get('linkedin_verified', True), key=f"lin_{mode}_{i}")
                with chk3: st.checkbox("GST / Registry Verified", value=l.get('gst_verified', True), key=f"gst_{mode}_{i}")
                st.markdown(f"[📍 Open Route on Google Maps]({l.get('maps')}) | [💼 Search Company on LinkedIn]({l.get('link')})")

            with t_tech:
                st.error(f"**Identified Client Bottleneck:**\n{l.get('client_problem', l.get('problem'))}")
                st.success(f"**Aryavarta Primary Deliverable:**\n{l.get('primary_solution', l.get('offer'))}")
                st.info(f"**100% Problem Resolution Roadmap:**\n{l.get('resolution_roadmap', l.get('why_us'))}")
                st.write(f"**On-Site Integration & Usage:**\n{l.get('integration_workflow')}")

            with t_deal:
                st.markdown(f"**360° Deal & Sundry Expansion Opportunities:**\n{l.get('deal_expansion')}")
                st.markdown("""
                * **Panels:** MCC, PCC, VFD Distribution, APFC Capacitor Banks, PLC/SCADA Automation Desks.
                * **Sundry Consumables:** GI Perforated/Ladder Cable Trays, Brass Cable Glands, Copper Lugs, Ferrules, Terminal Blocks.
                * **Site Services:** 4-20mA Sensor Loop Checks, Busbar Torque Testing, 24/7 Plant Shutdown Engineers.
                """)

            with t_comm:
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    pay_terms = st.selectbox("Payment Milestones:", ["30% Advance, 60% Against Proforma/FAT, 10% Post-Commissioning", "50% Advance, 50% Against Delivery", "Corporate Net 30 Days"], key=f"pt_{mode}_{i}")
                    fatsat = st.selectbox("Quality Assurance:", ["Factory Acceptance Testing (FAT) Included", "Site Acceptance Testing (SAT) Support", "Third-Party Inspection (TPI) Ready"], key=f"fs_{mode}_{i}")
                
                with col_c2:
                    curr = "USD ($)" if is_export else "INR (₹)"
                    if mode in ["panels", "networking"]:
                        p_cnt = st.number_input("Estimated Panels Required:", min_value=1, max_value=100, value=3, key=f"p_cnt_{mode}_{i}")
                        est_val = p_cnt * (2200 if is_export else 175000)
                        quote_text = f"Scope: {p_cnt} Units | Estimate: { '$' if is_export else '₹' }{est_val:,} {curr} ({pay_terms})"
                    else:
                        e_cnt = st.number_input("Required Site Engineer Man-Days:", min_value=1, max_value=180, value=7, key=f"e_cnt_{mode}_{i}")
                        est_val = e_cnt * (150 if is_export else 6500)
                        quote_text = f"Deployment: {e_cnt} Man-Days | Estimate: { '$' if is_export else '₹' }{est_val:,} {curr} ({pay_terms})"
                    st.info(f"**Budgetary Valuation:** {quote_text}")

                pdf_bytes = gen_pdf(l, mode, quote_text, fatsat, pay_terms)
                st.download_button("📄 Download Custom Priced PDF Proposal", pdf_bytes, f"{l.get('company')}_Proposal.pdf", "application/pdf", key=f"pdf_{mode}_{i}")

            with t_outreach:
                st.markdown("#### 🚀 Ready-to-Use Outreach Center")
                st.info(f"**👤 Decision Maker:** {l.get('contact',{}).get('key_name')} ({l.get('contact',{}).get('key_role')}) | **✉️ Email:** `{l.get('contact',{}).get('email')}` | **📞 Phone:** `{l.get('contact',{}).get('phone')}`")
                
                # Formulate Ready Messages
                corp_email = f"""Subject: Technical Vendor Empanelment & Automation Proposal - {l.get('company')}

Dear {l.get('contact',{}).get('key_name', 'Procurement Team')},

I hope this email finds you well.

I am writing to you from Aryavarta Automation (Chikhali, Pune). We specialize in manufacturing 100% Indian Electricity (IE) Rule-compliant Control Panels (MCC, PCC, VFD, APFC), supplying complete sundry consumables (Cable Trays, Glands, Lugs), and deploying certified Electrical & Instrumentation (E&I) Site Engineers.

Having reviewed {l.get('company')}'s plant operations and focus on {l.get('strategic_vision')[:60]}..., we understand the operational priority of addressing:
"{l.get('client_problem', l.get('problem'))}"

Aryavarta Automation provides a 100% resolved engineered solution:
• Primary Scope: {l.get('primary_solution', l.get('offer'))}
• Complementary Package: {l.get('deal_expansion')[:120]}...
• Quality Assurance: Full Factory Acceptance Testing ({fatsat}) with TPI readiness.
• Operational Advantage: Rapid engineering response and dispatch directly from our Chikhali, Pune facility.

We welcome the opportunity to submit our corporate profile for your Approved Vendor List (AVL) or review your active tender specifications.

Official Web Profile: https://www.aryavartaautomation.com/products.html
Direct Contact: +91 8045802403 | support@aryavartaautomation.com

Sincerely,
Sales & Engineering Operations
Aryavarta Automation (Pune)"""

                wa_msg = f"Hello {l.get('contact',{}).get('key_name', 'Sir/Madam')},\n\nGreetings from Aryavarta Automation (Chikhali, Pune).\n\nRegarding your plant operations at {l.get('location')}, we manufacture IE-compliant Control Panels (MCC/PCC/VFD) and deploy certified E&I Site Engineers specifically solving: {l.get('client_problem', l.get('problem'))[:90]}...\n\nWe provide complete turnkey packages including Cable Trays, Glands, and on-site FAT testing ({quote_text}).\n\nMay we share our technical catalog for your approved vendor list? www.aryavartaautomation.com"

                call_script = f"""**📞 30-Second Ready Cold Call Playbook:**
* **1. Introduction:** "Good morning {l.get('contact',{}).get('key_name', 'Sir')}, my name is [Your Name] calling from Aryavarta Automation in Pune."
* **2. The Hook:** "I'm reaching out because we support companies like {l.get('company')} in eliminating {l.get('client_problem', l.get('problem'))[:75]}... with custom IE-compliant panel fabrication and certified site engineers."
* **3. Value Proposition:** "We manufacture full MCC/PCC/VFD panels and provide complete sundry cable tray packages locally from Chikhali, meaning zero dispatch delays and immediate FAT inspection."
* **4. Call to Action (CTA):** "Can I send our technical catalog and vendor registration dossier to your email at {l.get('contact',{}).get('email')}?" """

                inmail_text = f"Hi {l.get('contact',{}).get('key_name', 'there')}, I lead technical partnerships at Aryavarta Automation (Pune). We manufacture IE-compliant Control Panels (MCC/VFD/APFC) and deploy E&I Site Engineers. Given your focus at {l.get('company')} on {l.get('strategic_vision')[:60]}..., I'd welcome the opportunity to connect and share our vendor profile: www.aryavartaautomation.com"

                # Render Tabbed Ready Communications
                o_em, o_wa, o_call, o_li = st.tabs(["📧 Ready-Made Email", "💬 Ready WhatsApp Message", "📞 Ready Call Script", "💼 LinkedIn InMail"])
                
                with o_em:
                    st.text_area("Copy-Paste Ready Email:", corp_email, height=220, key=f"em_txt_{mode}_{i}")
                    em_to = l.get('contact',{}).get('email','')
                    gmail_url = f"https://mail.google.com/mail/?view=cm&fs=1&to={em_to if '@' in em_to else ''}&su={urllib.parse.quote('Technical Vendor Empanelment - Aryavarta Automation')}&body={urllib.parse.quote(corp_email)}"
                    st.link_button("🚀 1-Click Send via Gmail", gmail_url, type="primary")
                
                with o_wa:
                    st.text_area("Copy-Paste Ready WhatsApp:", wa_msg, height=140, key=f"wa_txt_{mode}_{i}")
                    clean_phone = re.sub(r'[^0-9]', '', str(l.get('contact',{}).get('phone','')))
                    wa_url = f"https://api.whatsapp.com/send?phone={clean_phone}&text={urllib.parse.quote(wa_msg)}" if clean_phone else f"https://api.whatsapp.com/send?text={urllib.parse.quote(wa_msg)}"
                    st.link_button("💬 1-Click Send via WhatsApp", wa_url, type="secondary")
                
                with o_call:
                    st.markdown(call_script)
                
                with o_li:
                    st.text_area("Copy-Paste LinkedIn Connect Message:", inmail_text, height=100, key=f"li_txt_{mode}_{i}")
                    st.link_button("💼 Open LinkedIn Profile to Connect", l.get('link'))

                st.divider()
                st.session_state[f"notes_{mode}_{i}"] = st.text_area("📝 Internal Sales Notes / Meeting Log:", value=st.session_state.get(f"notes_{mode}_{i}", ""), key=f"ta_{mode}_{i}")

# --- 4. MAIN APP TABS ---
st.title("⚡ Aryavarta Global AI Radar Enterprise 360")
st.caption("Base: Gat No. 1610, Dehu Alandi Rd, Chikhali, Pune-411062 | Control Panels • Sundry Materials • E&I Site Engineers • Strategic Networking")

tab_p, tab_s, tab_n = st.tabs([
    "🏭 Active Deals (Panels & Sundries)", 
    "👷 Active Deals (E&I Site Services)", 
    "🤝 Strategic Networking & Partner Circles"
])

with tab_p:
    st.caption("Identify verified plant expansions requiring MCC, PCC, VFD, APFC panels, cable trays, and sundry supplies.")
    if st.button("🚀 Scan Verified Panel Opportunities", type="primary", key="bp"):
        with st.status("Scanning live industrial projects & generating 360° dossiers...", expanded=True) as s:
            st.session_state.p_leads = scan_engine("panels")
            s.update(label="✅ Panel Intelligence Complete!", state="complete")
    if 'p_leads' in st.session_state: render_leads(st.session_state.p_leads, "panels")

with tab_s:
    st.caption("Identify verified plant shutdowns, overhauls, and commissioning contracts requiring certified E&I Site Engineers.")
    if st.button("🚀 Scan Verified Site Engineer Contracts", type="primary", key="bs"):
        with st.status("Scanning live shutdown & maintenance contracts...", expanded=True) as s:
            st.session_state.s_leads = scan_engine("services")
            s.update(label="✅ Service Intelligence Complete!", state="complete")
    if 's_leads' in st.session_state: render_leads(st.session_state.s_leads, "services")

with tab_n:
    st.caption("Discover legitimate EPC Contractors, OEM Builders, and Procurement Directors for recurring vendor empanelment.")
    if st.button("🤝 Discover Verified Networking Partners", type="primary", key="bn"):
        with st.status("Scanning verified corporate directories & LinkedIn ecosystems...", expanded=True) as s:
            st.session_state.n_leads = scan_engine("networking")
            s.update(label="✅ Strategic Networking Dossiers Complete!", state="complete")
    if 'n_leads' in st.session_state: render_leads(st.session_state.n_leads, "networking")
