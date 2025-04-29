#!/usr/bin/env python3
import re
import pandas as pd
import requests
import tldextract
import streamlit as st
from bs4 import BeautifulSoup
from io import BytesIO

st.title("FQHC Executive Roles Scraper (Enhanced)")
st.markdown(
    """
    Upload a CSV of organizations (columns: 'Name' and optional 'Website').
    The app visits multiple paths—including extra leadership paths—
    and extracts exact-role titles:
    - Chief Financial Officer
    - Human Resources Director
    - Chief Operating Officer
    """
)

uploaded_file = st.file_uploader("Choose CSV file", type="csv")
if not uploaded_file:
    st.info("Please upload a CSV file to begin.")
    st.stop()

df = pd.read_csv(uploaded_file)
st.write("### Uploaded organizations:", df.head())

def guess_domain(name: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    return f"https://{slug}.org"

def extract_domain(website: str) -> str:
    ext = tldextract.extract(website)
    if ext.suffix:
        return f"https://{ext.domain}.{ext.suffix}"
    return None

def get_domain(row) -> str:
    site = row.get('Website', '')
    if pd.notna(site) and site:
        d = extract_domain(site)
        if d:
            return d
    return guess_domain(row['Name'])

df['Domain'] = df.apply(get_domain, axis=1)

paths = [
    '/', '/about', '/about-us', '/our-team', '/team', '/leadership',
    '/admin-team', '/info-center/about/leadership', '/info-center/about', '/info'
]

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

role_patterns = {
    'Chief Financial Officer': re.compile(
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*[-–,:]?\s*Chief Financial Officer', re.IGNORECASE
    ),
    'Human Resources Director': re.compile(
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*[-–,:]?\s*Human Resources Director', re.IGNORECASE
    ),
    'Chief Operating Officer': re.compile(
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*[-–,:]?\s*Chief Operating Officer', re.IGNORECASE
    ),
}

def extract_roles(text: str) -> dict:
    visible = ' '.join(BeautifulSoup(text, 'html.parser').stripped_strings)
    found = {role: '' for role in role_patterns}
    for role, pat in role_patterns.items():
        m = pat.search(visible)
        if m:
            found[role] = m.group(1)
    return found

results = []
progress = st.progress(0)
total = len(df)

for idx, row in df.iterrows():
    domain = row['Domain'].rstrip('/')
    data = {role: '' for role in role_patterns}
    for path in paths:
        url = domain + path
        try:
            resp = requests.get(url, headers=HEADERS, timeout=5)
            if resp.status_code != 200:
                continue
            roles = extract_roles(resp.text)
            for role in data:
                if not data[role] and roles[role]:
                    data[role] = roles[role]
            if all(data.values()):
                break
        except Exception:
            continue
    entry = {'Center': row['Name'], 'Domain': domain}
    entry.update(data)
    results.append(entry)
    progress.progress((idx + 1) / total)

out_df = pd.DataFrame(results)
st.write("### Executive roles extraction results:")
st.dataframe(out_df)

buffer = BytesIO()
out_df.to_excel(buffer, index=False, engine='openpyxl')
buffer.seek(0)
st.download_button(
    label="Download as Excel",
    data=buffer,
    file_name="new_appy2_executives.xlsx",
    mime="application/vnd.openxmlformats-officedocument-spreadsheetml.sheet"
)
