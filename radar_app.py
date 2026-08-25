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
    max_leads = st.slider("Target Leads:", min_value=2, max_value=20, value=5, help="Select number of verified target leads to generate.")
    
    st.divider()
    max_dist_filter = st.slider("🎯 Max Distance Filter (km from Chikhali):", 50, 20000, 20000)
    test_mode = st.toggle("🧪 Zero-Quota Test Mode", value=True, help="Test UI, detailed breakdowns, CRM Sync & PDF without API quota.")

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

def search_news(q, mx=10):
    res = []
    try:
        with DDGS() as d:
            for r in d.news(q, max_results=mx): 
                res.append(f"Source: {r.get('source')} | Title: {r.get('title')} | URL: {r.get('url')} | Body: {r.get('body')}")
    except Exception: pass
    if not res:
        try:
            with DDGS() as d:
                for r in d.text(q, max_results=mx): 
                    res.append(f"Title: {r.get('title')} | URL: {r.get('href')} | Body: {r.get('body')}")
        except Exception: pass
    return res

def gen_pdf(l, mode, quote_text, bantscore, fatsat, pay_terms):
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
    c.drawString(40, 722, f"Verification: {l.get('trust_score')} - {l.get('credibility_proof')} | Deal Score: {bantscore}%")
    
    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, 695, "1. Client Operational Challenges:")
    c.setFont("Helvetica", 9)
    t1 = c.beginText(40, 680)
    t1.textLines(l.get('problem', ''))
    c.drawText(t1)

    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, 610, "2. Aryavarta Engineered Solution & Deliverables:")
    c.setFont("Helvetica", 9)
    t2 = c.beginText(40, 595)
    t2.textLines(f"- Scope: {l.get('offer')}\n- Commercial Estimate: {quote_text}\n- Commercial Terms: {pay_terms}\n- QA Protocol: {fatsat}")
    c.drawText(t2)

    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, 505, "3. 100% Problem Resolution Roadmap (Why Aryavarta):")
    c.setFont("Helvetica", 9)
    t3 = c.beginText(40, 490)
    t3.textLines(f"- {l.get('why_us')}\n- 100% Indian Electricity (IE) Rule compliance & local Chikhali engineering response.")
    c.drawText(t3)
    
    c.drawString(40, 95, "Authorized Engineering & Commercial Sign-off: Aryavarta Automation")
    c.drawString(40, 80, f"Source Ref: {l.get('source_url')} | support@aryavartaautomation.com | www.aryavartaautomation.com")
    c.save()
    return buf.getvalue()

def call_gemini(prompt):
    for i in range(2):
        try:
            r = client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=types.GenerateContentConfig(response_mime_type="application/json"))
            return json.loads(r.text)
        except Exception as e:
            if ("429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)) and i == 0:
                st.toast("⏳ Quota cooldown. Auto-waiting 20s...")
                time.sleep(20)
            else: raise e

# --- 2. ENGINE ---
def scan_engine(mode):
    if test_mode:
        time.sleep(0.3)
        if mode == "panels":
            mock_companies = [
                ("Praj Industries Ltd", "Bio-Ethanol Plant Automation & Power Distribution Setup", "Bhosari MIDC, Pune", 18.6270, 73.8340, 
                 "Custom MCC, PCC, and VFD control panels complete with sundry cabling accessories (cable trays, glands, lugs, ferrules, terminal blocks) tailored for hazardous continuous processing environments.", 
                 "Experiencing severe power factor penalties, unoptimized motor load synchronization, and harmonic distortion across distillation drives causing recurring thermal trips and process downtime.", 
                 "Aryavarta delivers a 100% resolved power distribution setup: custom heavy-gauge IE-compliant panels engineered 9 km away in Chikhali, integrated with tuned harmonic filters, active APFC banks, and on-site FAT load testing to completely eliminate power factor penalties and nuisance tripping.", 
                 "info@praj.net", "+91 20 7180 2000", "www.praj.net"),
                ("Thermax Ltd", "Industrial Boiler Automation & Control Overhaul", "Chinchwad MIDC, Pune", 18.6445, 73.8055, 
                 "Turnkey PLC automation control panels, customized flame-proof junction boxes, and temperature transmitter integration.", 
                 "Frequent boiler tripping due to aging manual switchgear and lack of automated PID burner loop controls, degrading energy efficiency.", 
                 "Aryavarta guarantees 100% stability by replacing manual switchgear with automated PLC/SCADA control panels, precision transmitter calibration, and comprehensive interlock testing before handover.", 
                 "enquiry@thermaxglobal.com", "+91 20 6605 1200", "thermaxglobal.com")
            ]
        else:
            mock_companies = [
                ("Tata Motors Ltd", "Assembly Line Maintenance Overhaul & Drive Commissioning", "Chakan MIDC, Pune", 18.7500, 73.8500, 
                 "Certified senior Electrical & Instrumentation (E&I) Site Engineers equipped for high-speed PLC drive synchronization, busbar torque testing, sensor loop calibration, and 24/7 breakdown troubleshooting.", 
                 "Tight 72-hour scheduled plant shutdown window where uncalibrated sensor drift, communication bus faults, or drive parameter mismatches risk causing catastrophic assembly line restart delays.", 
                 "Aryavarta's engineers solve 100% of this challenge through a 4-step on-site execution: (1) Pre-shutdown Megger insulation & busbar torque audits, (2) 4-20mA loop calibration and sensor validation, (3) Real-time VFD drive parameter tuning & Profinet communication verification, and (4) Full-load trial run supervision with zero delay from our Chikhali hub.", 
                 "maintenance@tatamotors.com", "+91 20 6613 1111", "tatamotors.com"),
                ("Larsen & Toubro (L&T)", "Substation Switchgear & Instrumentation Commissioning", "Talegaon MIDC, Pune", 18.7320, 73.6760, 
                 "Deploying certified E&I testing and commissioning engineers with primary/secondary injection kits, insulation testers, and high-voltage calibration tools.", 
                 "Stringent Third-Party Inspection (TPI) deadlines and complex CT/PT wiring interlocks risking client penalties and handover rejection.", 
                 "Aryavarta engineers guarantee 100% error-free commissioning: conducting end-to-end scheme testing, secondary injection checks, relay coordination curve verification, and compiling complete TPI-ready test reports for immediate sign-off.", 
                 "infodesk@larsentoubro.com", "+91 22 6752 5656", "larsentoubro.com")
            ]
        
        leads = []
        for i in range(min(max_leads, len(mock_companies))):
            comp, proj, loc, lat, lon, off, prob, why, em, ph, wb = mock_companies[i]
            d = calc_dist(lat, lon)
            leads.append({
                "company": comp, "project": proj, "location": loc, "lat": lat, "lon": lon,
                "trust_score": "99% Verified (Industrial Notice)", "credibility_proof": "Verified Manufacturing Plant Operation",
                "source_name": "Maharashtra Industrial News", "source_url": f"https://{wb}",
                "source_title": f"{comp} Project Expansion & Upgrade",
                "offer": off, "problem": prob, "why_us": why, "dist": d,
                "maps": build_maps_url(comp, loc),
                "link": f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(comp + ' procurement maintenance')}",
                "contact": {"key_name": "Plant Head / Procurement Lead", "key_role": "Decision Maker", "email": em, "phone": ph, "website": wb}
            })
        leads.sort(key=lambda x: x["dist"])
        return leads

    q_map = {
        "panels": {
            "Local (Maharashtra)": "manufacturing plant expansion factory setup MIDC Pune Maharashtra electrical panel requirement",
            "National (India)": "new manufacturing plant commissioning industrial project factory setup India electrical panels",
            "Global Export": "water treatment industrial plant factory setup Middle East Africa electrical distribution panel"
        },
        "services": {
            "Local (Maharashtra)": "plant shutdown maintenance commissioning electrical instrumentation MIDC Pune Maharashtra",
            "National (India)": "electrical instrumentation site engineer maintenance plant shutdown contract India",
            "Global Export": "instrumentation maintenance commissioning site engineer project Middle East plant overhaul"
        }
    }[mode]

    raw_news = []
    fetch_per_market = max(5, math.ceil((max_leads * 2) / len(markets)))
    for m in markets: 
        raw_news.extend(search_news(q_map[m], mx=fetch_per_market))
    
    if not raw_news: return []

    focus = "supply of electrical panels (MCC, PCC, VFD, APFC) & sundry materials" if mode=="panels" else "certified Electrical & Instrumentation (E&I) Site Engineers for plant shutdown, testing, and commissioning"
    analysis_prompt = f"""
    Select up to {max_leads} distinct, verified real corporate industrial projects from: {json.dumps(raw_news)}.
    Output a JSON list of objects with exact keys: company, project, location, lat, lon, trust_score, credibility_proof, offer, problem, why_us, source_url, source_title, source_name.
    
    DETAILED TECHNICAL REQUIREMENTS:
    - "project": State the plant project name and physical scope.
    - "problem": Describe in specific detail the exact electrical, operational, or downtime bottlenecks the client faces (e.g., sensor calibration drift, drive trips, tight shutdown windows, wiring errors, harmonic issues).
    - "offer": Detail the complete technical deliverables from Aryavarta Automation ({focus}).
    - "why_us": For E&I Site Engineers, explain explicitly in a clear, 100% problem-solving roadmap HOW our engineers completely eliminate the client's problem (e.g., pre-commissioning loop checks, relay/drive parameterization, torque audits, calibration, 24/7 site supervision, and rapid dispatch from Chikhali, Pune). For Panel Manufacturing, detail the exact fabrication quality, FAT testing, and proximity advantage that solves their power bottleneck 100%.
    - lat, lon: Approximate geographical coordinates.
    """
    try: 
        base_leads = call_gemini(analysis_prompt)
    except Exception: 
        st.error("❌ Quota limit reached. Switch to Test Mode in sidebar.")
        st.stop()

    contact_map = {l['company']: " ".join(search_news(f"{l['company']} {l['location']} corporate office email phone contact director", mx=2)) for l in base_leads}
    try: 
        all_c = call_gemini(f"Extract real contacts from: {json.dumps(contact_map)}. Return JSON dict mapped by company name: website, email, phone, key_name, key_role.")
    except Exception: 
        all_c = {}

    leads = []
    for l in base_leads:
        l["dist"] = calc_dist(float(l.get("lat", PUNE_COORDS["lat"])), float(l.get("lon", PUNE_COORDS["lon"])))
        l["maps"] = build_maps_url(l['company'], l['location'])
        l["link"] = f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(l['company'] + ' (maintenance OR procurement OR plant head)')}"
        c_i = all_c.get(l['company'], {})
        l["contact"] = {
            "website": c_i.get("website", l.get("source_url", "www.indiamart.com")),
            "email": c_i.get("email", "procurement@" + re.sub(r'https?://(www\.)?', '', l.get('source_url', 'company.com')).split('/')[0]),
            "phone": c_i.get("phone", "+91 20 2740 0000"),
            "key_name": c_i.get("key_name", "Plant Procurement Head"),
            "key_role": c_i.get("key_role", "Decision Maker")
        }
        leads.append(l)

    leads.sort(key=lambda x: x["dist"])
    return leads[:max_leads]

# --- 3. UI RENDERER ---
def render_leads(leads, mode):
    filtered_leads = [l for l in leads if l['dist'] <= max_dist_filter]
    if not filtered_leads:
        st.warning(f"⚠️ No leads found within {max_dist_filter} km. Adjust distance filter in sidebar.")
        return

    hot_local_count = sum(1 for l in filtered_leads if l['dist'] < 50)
    
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("🛡️ Verified Opportunities", len(filtered_leads))
    kpi2.metric("🔥 Hot Local Leads (<50km)", hot_local_count)
    kpi3.metric("📍 Operational Base", "Chikhali, Pune")
    st.divider()

    crm_sync_data = []
    for i, l in enumerate(filtered_leads):
        dist = l['dist']
        is_export = dist > 1500 or "Middle East" in l['location'] or "Africa" in l['location']
        curr = "USD ($)" if is_export else "INR (₹)"
        
        p_cnt = st.session_state.get(f"p_cnt_{i}", 3)
        e_cnt = st.session_state.get(f"e_cnt_{i}", 7)
        qty_str = f"{p_cnt} Panels" if mode == "panels" else f"{e_cnt} Man-Days"
        est_val = (p_cnt * (2200 if is_export else 175000)) if mode == "panels" else (e_cnt * (150 if is_export else 6500))
        est_str = f"{ '$' if is_export else '₹' }{est_val:,} {curr}"
        
        pay_term = st.session_state.get(f"pt_{mode}_{i}", "30% Advance, 60% Dispatch, 10% Commissioning")
        fatsat_val = st.session_state.get(f"fs_{mode}_{i}", "Factory Acceptance Testing (FAT) Included")
        notes_val = st.session_state.get(f"notes_{mode}_{i}", "")
        
        crm_sync_data.append({
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mode": "Panel Manufacturing" if mode == "panels" else "E&I Site Engineering",
            "company": l['company'],
            "location": l['location'],
            "distance_km": dist,
            "project_scope": l['project'],
            "required_panels_or_mandays": qty_str,
            "client_problem_detailed": l['problem'],
            "aryavarta_solution_detailed": l['offer'],
            "value_add": l['why_us'],
            "commercial_estimate": est_str,
            "payment_terms": pay_term,
            "testing_protocol": fatsat_val,
            "contact_person": l['contact'].get('key_name'),
            "role": l['contact'].get('key_role'),
            "email": l['contact'].get('email'),
            "phone": l['contact'].get('phone'),
            "source_url": l['source_url'],
            "sales_notes": notes_val
        })

    c1, c2, c3 = st.columns([2, 1, 1])
    c1.subheader(f"🛡️ Active {len(filtered_leads)} {'Panel Opportunities' if mode=='panels' else 'Site Engineer Opportunities'}")
    
    if c2.button(f"☁️ Sync to Drive CRM", key=f"s_{mode}"):
        if WEBHOOK:
            try:
                res = requests.post(WEBHOOK, json=crm_sync_data, timeout=10)
                if res.status_code == 200:
                    st.toast("✅ Synced all detailed fields to Google Sheet CRM!")
                else:
                    st.error(f"❌ Webhook responded with status: {res.status_code}")
            except Exception as e:
                st.error(f"❌ Webhook Sync Error: {e}")
        else:
            st.warning("⚠️ Please provide your Google Sheets Webhook URL in the sidebar.")
    
    df = pd.DataFrame(crm_sync_data)
    c3.download_button("📥 Export Full CSV", df.to_csv(index=False).encode('utf-8'), f"Aryavarta_{mode}_Detailed_CRM.csv", "text/csv", key=f"d_{mode}")

    map_df = pd.DataFrame([{"lat": float(l.get("lat", PUNE_COORDS["lat"])), "lon": float(l.get("lon", PUNE_COORDS["lon"]))} for l in filtered_leads] + [{"lat": PUNE_COORDS["lat"], "lon": PUNE_COORDS["lon"]}])
    st.map(map_df, zoom=6)

    for i, l in enumerate(filtered_leads):
        dist = l['dist']
        is_export = dist > 1500 or "Middle East" in l['location'] or "Africa" in l['location'] or "Export" in l['location']
        hotness = "🌍 Global Export" if is_export else ("🔥 Hot Lead (<50km)" if dist < 50 else "⚡ Warm Lead (<200km)")
        
        with st.expander(f"#{i+1}. {l['company']} — {l['location']} ({dist} km) | {hotness} | 🛡️ {l.get('trust_score', '98%')}", expanded=(i==0)):
            
            st.markdown("#### 💼 Commercial Terms & Quality Protocol")
            tc1, tc2 = st.columns(2)
            with tc1:
                pay_terms = st.selectbox("Payment Milestone Terms:", ["30% Advance, 60% Dispatch, 10% Commissioning", "50% Advance, 50% Against Delivery", "Standard Corporate Net 30 Days"], key=f"pt_{mode}_{i}")
            with tc2:
                fatsat = st.selectbox("Testing & Inspection Standard:", ["Factory Acceptance Testing (FAT) Included", "Site Acceptance Testing (SAT) Support", "Third-Party Inspection (TPI) Ready"], key=f"fs_{mode}_{i}")

            st.markdown("#### ✅ Deal Readiness & Compliance Checklist")
            chk1, chk2, chk3 = st.columns(3)
            with chk1: c1_val = st.checkbox("Drawings / Specs Verified", key=f"c1_{mode}_{i}")
            with chk2: c2_val = st.checkbox("IE Standard Compliance", key=f"c2_{mode}_{i}")
            with chk3: c3_val = st.checkbox("Commercial Terms Aligned", key=f"c3_{mode}_{i}")
            
            st.markdown("#### 🎯 BANT Lead Qualification & Deal Success Score")
            bc1, bc2, bc3, bc4 = st.columns(4)
            with bc1: b_val = st.selectbox("Budget Verified?", ["High", "Medium", "Low"], key=f"b_{mode}_{i}")
            with bc2: a_val = st.selectbox("Authority Met?", ["Direct Decision Maker", "Influencer", "Gatekeeper"], key=f"a_{mode}_{i}")
            with bc3: n_val = st.selectbox("Need Urgency?", ["Immediate", "Moderate", "Exploring"], key=f"n_{mode}_{i}")
            with bc4: t_val = st.selectbox("Timeline?", ["< 1 Month", "1-3 Months", "> 3 Months"], key=f"t_{mode}_{i}")
            
            raw_score = 40
            if b_val == "High": raw_score += 15
            elif b_val == "Medium": raw_score += 8
            if a_val == "Direct Decision Maker": raw_score += 15
            elif a_val == "Influencer": raw_score += 8
            if n_val == "Immediate": raw_score += 15
            elif n_val == "Moderate": raw_score += 8
            if t_val == "< 1 Month": raw_score += 15
            elif t_val == "1-3 Months": raw_score += 8
            if c1_val: raw_score += 5
            if c2_val: raw_score += 5
            if c3_val: raw_score += 10
            
            score = min(raw_score, 100)
            st.progress(score / 100.0, text=f"🚀 Deal Success Probability: {score}%")
            st.divider()
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"### 🏢 {l['project']}")
                st.markdown(f"**📦 What We Offer:**\n{l['offer']}")
                st.markdown(f"**🔧 Client Operational Bottleneck:**\n{l['problem']}")
                st.markdown(f"**🏆 Why Aryavarta Automation (100% Problem-Solving Roadmap):**\n{l['why_us']}")
                st.markdown(f"[📍 Google Maps Route]({l['maps']}) | [💼 Search LinkedIn]({l['link']})")
                
                curr = "USD ($)" if is_export else "INR (₹)"
                if mode == "panels":
                    panel_count = st.number_input("Estimated Panels Required:", min_value=1, max_value=100, value=3, key=f"p_cnt_{i}")
                    est_val = panel_count * (2200 if is_export else 175000)
                    quote_text = f"Estimated Quantity: {panel_count} Panels | Budgetary Quote: { '$' if is_export else '₹' }{est_val:,} {curr} ({pay_terms})"
                else:
                    engineer_days = st.number_input("Required Man-Days on Site:", min_value=1, max_value=180, value=7, key=f"e_cnt_{i}")
                    est_val = engineer_days * (150 if is_export else 6500)
                    quote_text = f"Manpower Deployment: {engineer_days} Days | Estimated Service Quote: { '$' if is_export else '₹' }{est_val:,} {curr} ({pay_terms})"
                
                st.info(quote_text)
                
                pdf_bytes = gen_pdf(l, mode, quote_text, score, fatsat, pay_terms)
                st.download_button("📄 Download Custom Priced PDF", pdf_bytes, f"{l['company']}_Pitch.pdf", "application/pdf", key=f"pdf_{mode}_{i}")
            
            with col2:
                st.markdown("### 📞 Multi-Channel Outreach, Notes & Follow-up")
                st.info(f"**👤 Decision Maker:** {l['contact'].get('key_name')} ({l['contact'].get('key_role')})")
                st.write(f"**✉️ Email:** `{l['contact'].get('email')}` | **📞 Phone:** `{l['contact'].get('phone')}`")
                
                fc1, fc2 = st.columns(2)
                with fc1:
                    follow_date = st.date_input("📅 Follow-up Date:", key=f"date_{mode}_{i}")
                
                note_key = f"notes_{mode}_{i}"
                if note_key not in st.session_state: st.session_state[note_key] = ""
                st.session_state[note_key] = st.text_area("📝 Sales Action Notes:", value=st.session_state[note_key], key=f"ta_{mode}_{i}")

                pitch_angle = st.selectbox("🎯 Select Pitch Angle:", ["Standard Introduction & Profile", "Urgent Breakdown / Shutdown Support", "Turnkey Panel & Sundry Supply"], key=f"angle_{mode}_{i}")
                
                if pitch_angle == "Standard Introduction & Profile":
                    pitch_msg = f"Hello {l['contact'].get('key_name', 'Team')},\n\nRegarding your {l['project']} in {l['location']}:\n\nClient Bottleneck Identified: {l['problem']}\n\nAryavarta 100% Resolution: {l['why_us']}\n\nOur Scope: {l['offer']} ({quote_text}).\n\nPlease check our profile: www.aryavartaautomation.com"
                elif pitch_angle == "Urgent Breakdown / Shutdown Support":
                    pitch_msg = f"Hello {l['contact'].get('key_name', 'Team')},\n\nFor your shutdown at {l['location']}, Aryavarta Automation deploys certified E&I engineers to guarantee zero downtime.\n\nProblem Solved: {l['problem']}\n\nExecution Plan: {l['why_us']}\n\nLet us know your dispatch timeline!"
                else:
                    pitch_msg = f"Hello {l['contact'].get('key_name', 'Team')},\n\nAryavarta Automation offers complete turnkey panel manufacturing ({quote_text}) to eliminate: {l['problem']}.\n\nOur Technical Commitment: {l['why_us']} with {fatsat}.\n\nLet's connect!"

                clean_phone = re.sub(r'[^0-9]', '', str(l['contact'].get('phone', '')))
                wa_url = f"https://api.whatsapp.com/send?phone={clean_phone}&text={urllib.parse.quote(pitch_msg)}" if clean_phone else f"https://api.whatsapp.com/send?text={urllib.parse.quote(pitch_msg)}"
                
                subj = urllib.parse.quote(f"{'Panel Supply' if mode=='panels' else 'E&I Support'} - {l['company']}")
                em = l['contact'].get('email', '')
                gmail_url = f"https://mail.google.com/mail/?view=cm&fs=1&to={em if '@' in em else ''}&su={subj}&body={urllib.parse.quote(pitch_msg)}"
                
                b1, b2 = st.columns(2)
                b1.link_button("💬 WhatsApp Lead", wa_url, type="secondary")
                b2.link_button("🚀 Gmail Proposal", gmail_url, type="primary")

# --- 4. MAIN APP ---
st.title("⚡ Aryavarta Global AI Radar Bulletproof")
st.caption("Base: Gat No. 1610, Dehu Alandi Rd, Chikhali, Pune-411062 | Panels • Sundry Materials • E&I Site Engineers")

tab_p, tab_s = st.tabs(["🏭 Panel Manufacturing & Sundry Supply", "👷 E&I Site Engineer Services"])

with tab_p:
    st.caption("Find verified plants needing VFD, MCC, PCC, APFC panels & sundry materials.")
    if st.button("🚀 Scan Verified Panel Opportunities", type="primary", key="bp"):
        with st.status("Scanning live industrial projects...", expanded=True) as s:
            leads = scan_engine("panels")
            if leads: st.session_state.p_leads = leads
            s.update(label="✅ Search Complete!", state="complete")
    if 'p_leads' in st.session_state: render_leads(st.session_state.p_leads, "panels")

with tab_s:
    st.caption("Find verified plant shutdowns, maintenance overhauls, and commissioning sites needing E&I site engineers.")
    if st.button("🚀 Scan Verified Site Engineer Contracts", type="primary", key="bs"):
        with st.status("Scanning live maintenance & commissioning contracts...", expanded=True) as s:
            leads = scan_engine("services")
            if leads: st.session_state.s_leads = leads
            s.update(label="✅ Search Complete!", state="complete")
    if 's_leads' in st.session_state: render_leads(st.session_state.s_leads, "services")
