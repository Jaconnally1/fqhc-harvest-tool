#!/usr/bin/env python3
import re
import pandas as pd
import requests
import tldextract
import streamlit as st
from bs4 import BeautifulSoup
from io import BytesIO

st.title("FQHC Executive Roles Scraper")
st.markdown(
    """
    Upload a CSV of organizations (columns: 'Name' and optional 'Website').
    The app will visit key pages ('about', 'leadership', 'team', 'admin-team') 
    and extract names for the exact phrases: "Chief Financial Officer",
    "Human Resources Director", and "Chief Operating Officer".
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

paths = ['/', '/about', '/about-us', '/our-team', '/team', '/leadership', '/admin-team']

role_patterns = {
    'Chief Financial Officer': re.compile(r'([A-Z][a-z]+(?: [A-Z][a-z]+)+)\s*[-–:]?\s*Chief Financial Officer', re.IGNORECASE),
    'Human Resources Director': re.compile(r'([A-Z][a-z]+(?: [A-Z][a-z]+)+)\s*[-–:]?\s*Human Resources Director', re.IGNORECASE),
    'Chief Operating Officer': re.compile(r'([A-Z][a-z]+(?: [A-Z][a-z]+)+)\s*[-–:]?\s*Chief Operating Officer', re.IGNORECASE),
}

def extract_roles(text: str) -> dict:
    found = {role: '' for role in role_patterns}
    for role, pattern in role_patterns.items():
        m = pattern.search(text)
        if m:
            found[role] = m.group(1).strip()
    return found

results = []
progress = st.progress(0)
total = len(df)

for i, row in df.iterrows():
    domain = row['Domain'].rstrip('/')
    data = {role: '' for role in role_patterns}
    for path in paths:
        url = domain + path
        try:
            r = requests.get(url, timeout=5)
            if r.status_code != 200:
                continue
            roles_found = extract_roles(r.text)
            for role in data:
                if roles_found[role] and not data[role]:
                    data[role] = roles_found[role]
            if all(data.values()):
                break
        except requests.RequestException:
            continue
    entry = {'Center': row['Name'], 'Domain': domain}
    entry.update(data)
    results.append(entry)
    progress.progress((i + 1) / total)

out_df = pd.DataFrame(results)
st.write("### Executive roles extraction results:")
st.dataframe(out_df)

buffer = BytesIO()
out_df.to_excel(buffer, index=False, engine='openpyxl')
buffer.seek(0)
st.download_button(
    label="Download as Excel",
    data=buffer,
    file_name="new_appy_executives.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
