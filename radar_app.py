import streamlit as st
from google import genai
from google.genai import types
import json, urllib.parse, math, time, pandas as pd, requests, re
from ddgs import DDGS
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
    if not WEBHOOK: WEBHOOK = st.text_input("Sheets Webhook (Optional):", type="password").strip()
    markets = st.multiselect("Scan Radius:", ["Local (Maharashtra)", "National (India)", "Global Export"], default=["Local (Maharashtra)"])
    max_leads = st.slider("Target Leads:", 2, 8, 4)
    
    st.divider()
    max_dist_filter = st.slider("🎯 Max Distance Filter (km from Chikhali):", 50, 20000, 20000, help="Filter out leads further than this distance.")
    test_mode = st.toggle("🧪 Zero-Quota Test Mode", value=True, help="Test UI, payment terms, FAT/SAT & WhatsApp without API quota.")

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
            for r in d.news(q, max_results=mx): res.append(f"Source: {r.get('source')} | Title: {r.get('title')} | URL: {r.get('url')} | Body: {r.get('body')}")
    except Exception: pass
    if not res:
        try:
            with DDGS() as d:
                for r in d.text(q, max_results=mx): res.append(f"Title: {r.get('title')} | URL: {r.get('href')} | Body: {r.get('body')}")
        except Exception: pass
    return res

def gen_pdf(l, mode, quote_text, bantscore, fatsat, pay_terms):
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(40, 805, f"ARYAVARTA AUTOMATION - {mode.upper()} PROPOSAL")
    c.setFont("Helvetica", 10)
    c.drawString(40, 785, "Gat No. 1610, Dehu Alandi Rd, Chikhali, Pune-411062 | GST: 27ABOFA4930E1ZH | Ph: 08045802403")
    c.setStrokeColorRGB(0.7, 0.7, 0.7)
    c.line(40, 775, 555, 775)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, 750, f"Client: {l.get('company')} | Location: {l.get('location')} ({l.get('dist')} km)")
    c.setFont("Helvetica", 10)
    c.drawString(40, 730, f"Project Scope: {l.get('project')} | Deal Success Score: {bantscore}%")
    c.drawString(40, 710, f"Verification Proof: {l.get('credibility_proof')}")
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, 680, "Commercial Terms, Estimate & Quality Assurance:")
    c.setFont("Helvetica", 10)
    text = c.beginText(40, 660)
    text.textLines(f"- Scope / Deliverables: {l.get('offer')}\n- Problem Solved: {l.get('problem')}\n- {quote_text}\n- Commercial Terms: {pay_terms}\n- Quality Protocol: {fatsat}\n- Service SLA: Guaranteed dispatch & support directly from Chikhali, Pune.")
    c.drawText(text)
    
    c.drawString(40, 120, "Authorized Engineering & Commercial Sign-off:")
    c.drawString(40, 100, "Aryavarta Automation Sales & Engineering Team")
    c.drawString(40, 85, f"Source Reference: {l.get('source_url')} | www.aryavartaautomation.com")
    c.save()
    return buf.getvalue()

def call_gemini(prompt):
    for i in range(2):
        try:
            r = client.models.generate_content(model='gemini-3.6-flash', contents=prompt, config=types.GenerateContentConfig(response_mime_type="application/json"))
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
            return [{
                "company": "Praj Industries Ltd",
                "project": "Bio-Ethanol Plant Automation & Power Distribution Setup",
                "location": "Bhosari MIDC, Pune",
                "lat": 18.6270, "lon": 73.8340,
                "trust_score": "99% Verified (BSE Audited)",
                "credibility_proof": "Verified BSE Listed EPC Corporate Expansion",
                "source_name": "Industrial Times", "source_url": "https://www.praj.net",
                "source_title": "Pune Plant Expansion",
                "offer": "Custom MCC, PCC, and VFD control panels along with complete sundry materials (cable trays, glands, lugs, terminal blocks).",
                "problem": "High reactive power losses, disorganized motor control, and inefficient energy distribution across processing units.",
                "why_us": "Our manufacturing unit is located just 9 km away in Chikhali, Pune, ensuring fast dispatch, compliance with IE standards, and direct factory inspection.",
                "dist": calc_dist(18.6270, 73.8340),
                "maps": build_maps_url("Praj Industries", "Bhosari MIDC, Pune"),
                "link": f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote('Praj Industries procurement')}",
                "contact": {"key_name": "Procurement / Plant Head", "key_role": "Decision Maker", "email": "info@praj.net", "phone": "+91 20 7180 2000", "website": "www.praj.net"}
            }]
        else:
            return [{
                "company": "Tata Motors Ltd",
                "project": "Assembly Line Maintenance Overhaul & Drive Commissioning",
                "location": "Chakan MIDC, Pune",
                "lat": 18.7500, "lon": 73.8500,
                "trust_score": "99% Verified (Official Notice)",
                "credibility_proof": "Official Auto Plant Maintenance Notice",
                "source_name": "Auto Sector News", "source_url": "https://tatamotors.com",
                "source_title": "Tata Motors Chakan Plant Line Overhaul",
                "offer": "Deployment of certified Electrical & Instrumentation (E&I) Site Engineers for rapid on-site troubleshooting, testing, and commissioning.",
                "problem": "Critical risk of prolonged machinery downtime and wiring faults during scheduled assembly line shutdown.",
                "why_us": "Experienced E&I site engineers available for immediate, same-day dispatch directly from our Chikhali base with zero travel delay.",
                "dist": calc_dist(18.7500, 73.8500),
                "maps": build_maps_url("Tata Motors", "Chakan MIDC, Pune"),
                "link": f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote('Tata Motors plant maintenance')}",
                "contact": {"key_name": "Plant Electrical In-Charge", "key_role": "Maintenance Head", "email": "maintenance@tatamotors.com", "phone": "+91 20 6613 1111", "website": "tatamotors.com"}
            }]

    q_map = {
        "panels": {"Local (Maharashtra)": "manufacturing plant expansion factory setup Pune Maharashtra", "National (India)": "new manufacturing project factory setup India", "Global Export": "water treatment industrial plant Middle East Africa"},
        "services": {"Local (Maharashtra)": "plant shutdown maintenance commissioning electrical instrumentation Pune Maharashtra", "National (India)": "electrical instrumentation site engineer maintenance manpower contract India", "Global Export": "instrumentation maintenance commissioning site engineer project Middle East"}
    }[mode]

    raw_news = []
    for m in markets: raw_news.extend(search_news(q_map[m], mx=3))
    if not raw_news: return []

    focus = "supply of electrical panels (MCC, PCC, VFD, APFC) & sundry materials" if mode=="panels" else "certified Electrical & Instrumentation (E&I) Site Engineers for plant shutdown & testing"
    analysis_prompt = f"""
    Select up to {max_leads} verified real corporate projects from: {json.dumps(raw_news)}.
    Output JSON list of objects with exact keys: company, project, location, lat, lon, trust_score, credibility_proof, offer, problem, why_us, source_url, source_title, source_name.
    
    STRICT WRITING RULES FOR CLARITY AND PRECISION:
    - "offer": State precisely what Aryavarta provides in simple words. Keep it brief (max 15 words).
    - "problem": State the exact operational or power challenge. Keep it brief (max 15 words).
    - "why_us": State why Aryavarta is best based on location (Chikhali, Pune), IE compliance, or rapid response. Keep it brief (1-2 sentences).
    """
    try: base_leads = call_gemini(analysis_prompt)
    except Exception: st.error("❌ Quota limit. Use Test Mode."); st.stop()

    contact_map = {l['company']: " ".join(search_news(f"{l['company']} {l['location']} office email phone contact director", mx=2)) for l in base_leads}
    try: all_c = call_gemini(f"Extract real contacts from: {json.dumps(contact_map)}. Return JSON dict mapped by company name: website, email, phone, key_name, key_role.")
    except Exception: all_c = {}

    leads = []
    for l in base_leads:
        l["dist"] = calc_dist(float(l.get("lat", PUNE_COORDS["lat"])), float(l.get("lon", PUNE_COORDS["lon"])))
        l["maps"] = build_maps_url(l['company'], l['location'])
        l["link"] = f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(l['company'] + ' (maintenance OR procurement OR owner)')}"
        c_i = all_c.get(l['company'], {})
        l["contact"] = {"website": c_i.get("website", "Not found"), "email": c_i.get("email", "Not listed"), "phone": c_i.get("phone", "Not listed"), "key_name": c_i.get("key_name", "Not found"), "key_role": c_i.get("key_role", "Manager")}
        leads.append(l)

    leads.sort(key=lambda x: x["dist"])
    return leads

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

    c1, c2, c3 = st.columns([2, 1, 1])
    c1.subheader(f"🛡️ Active {'Panel Opportunities' if mode=='panels' else 'Site Engineer Opportunities'}")
    
    if c2.button(f"☁️ Sync to Drive CRM", key=f"s_{mode}") and WEBHOOK:
        if requests.post(WEBHOOK, json=filtered_leads).status_code == 200: st.toast("✅ Synced to Sheets!")
    
    df = pd.DataFrame([{
        "Company": l['company'], "Location": l['location'], "Distance (KM)": l['dist'], "Trust Score": l.get('trust_score', '98%'),
        "Project Scope": l['project'], "Offer": l['offer'], "Problem Solved": l['problem'], "Why Aryavarta": l['why_us'],
        "Contact Person": l['contact'].get('key_name'), "Role": l['contact'].get('key_role'),
        "Email": l['contact'].get('email'), "Phone": l['contact'].get('phone'), "Source URL": l['source_url']
    } for l in filtered_leads])
    c3.download_button("📥 Export CSV", df.to_csv(index=False).encode('utf-8'), f"Aryavarta_{mode}_Leads.csv", "text/csv", key=f"d_{mode}")

    map_df = pd.DataFrame([{"lat": float(l.get("lat", PUNE_COORDS["lat"])), "lon": float(l.get("lon", PUNE_COORDS["lon"]))} for l in filtered_leads] + [{"lat": PUNE_COORDS["lat"], "lon": PUNE_COORDS["lon"]}])
    st.map(map_df, zoom=6)

    for i, l in enumerate(filtered_leads):
        dist = l['dist']
        is_export = dist > 1500 or "Middle East" in l['location'] or "Africa" in l['location'] or "Export" in l['location']
        hotness = "🌍 Global Export" if is_export else ("🔥 Hot Lead (<50km)" if dist < 50 else "⚡ Warm Lead (<200km)")
        
        with st.expander(f"#{i+1}. {l['company']} — {l['location']} ({dist} km) | {hotness} | 🛡️ {l.get('trust_score', '98%')}", expanded=(i==0)):
            
            # Commercial Payment Milestones & Quality Assurance
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
                st.markdown(f"**📦 What We Offer:** {l['offer']}")
                st.markdown(f"**🔧 Problem Solved:** {l['problem']}")
                st.markdown(f"**🏆 Why Aryavarta Automation:** {l['why_us']}")
                st.markdown(f"[📍 Google Maps Route]({l['maps']}) | [💼 Search LinkedIn]({l['link']})")
                
                curr = "USD ($)" if is_export else "INR (₹)"
                if mode == "panels":
                    panel_count = st.number_input("Estimated Panels Required:", min_value=1, max_value=50, value=3, key=f"p_cnt_{i}")
                    est_val = panel_count * (2200 if is_export else 175000)
                    quote_text = f"Estimated Quantity: {panel_count} Panels | Budgetary Quote: { '$' if is_export else '₹' }{est_val:,} {curr} ({pay_terms})"
                else:
                    engineer_days = st.number_input("Required Man-Days on Site:", min_value=1, max_value=90, value=7, key=f"e_cnt_{i}")
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
                    pitch_msg = f"Hello {l['contact'].get('key_name', 'Team')},\n\nRegarding your {l['project']} in {l['location']}, Aryavarta Automation (Chikhali, Pune) specializes in {l['offer']} with 100% IE Rule compliance, {fatsat}, and flexible terms ({pay_terms}). ({quote_text}).\n\nPlease check our profile: www.aryavartaautomation.com"
                elif pitch_angle == "Urgent Breakdown / Shutdown Support":
                    pitch_msg = f"Hello {l['contact'].get('key_name', 'Team')},\n\nFor your upcoming shutdown/maintenance at {l['location']}, Aryavarta Automation provides certified E&I Site Engineers for rapid troubleshooting with zero travel delay from Pune.\n\nLet us know your dispatch requirements!"
                else:
                    pitch_msg = f"Hello {l['contact'].get('key_name', 'Team')},\n\nAryavarta Automation offers complete turnkey panel manufacturing and sundry supplies (cable trays, glands, lugs) with full factory warranty and transparent commercial milestones ({pay_terms}) for projects like your {l['project']}. ({quote_text}).\n\nLet's connect!"

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