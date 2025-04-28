#!/usr/bin/env python3
import re
import pandas as pd
import requests
import tldextract
import streamlit as st
from bs4 import BeautifulSoup
from io import BytesIO

# Streamlit App: Founding Year Scraper
st.title("FQHC Founding Year Scraper")
st.markdown(
    """
    Upload a CSV of FQHCs (columns 'Name' and optional 'Website').
    The app will visit each site's About/History pages and extract the founding year.
    """
)

# Upload CSV
uploaded_file = st.file_uploader("Choose CSV file", type="csv")
if not uploaded_file:
    st.info("Please upload a CSV file to begin.")
    st.stop()

# Load data
df = pd.read_csv(uploaded_file)
st.write("### Uploaded centers:", df.head())

# Helper functions
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

# Derive domains
df['Domain'] = df.apply(get_domain, axis=1)

# Pages to check for founding year
pages = ['/', '/about', '/about-us', '/our-story', '/history', '/who-we-are']

# Search patterns for year
patterns = [
    r'Founded\s+(?:in\s+)?(\d{4})',
    r'Estab(?:lished|lishment)\s+(?:in\s+)?(\d{4})',
    r'Since\s+(\d{4})',
]

def find_year(text: str) -> str:
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            year = int(m.group(1))
            if 1900 <= year <= pd.Timestamp.now().year:
                return str(year)
    return ""

def scrape_year(domain: str) -> str:
    for p in pages:
        url = domain.rstrip('/') + p
        try:
            r = requests.get(url, timeout=5)
            if r.status_code != 200:
                continue
            year = find_year(r.text)
            if year:
                return year
        except requests.RequestException:
            continue
    return ""

# Scrape all centers
results = []
progress = st.progress(0)
total = len(df)
for i, row in df.iterrows():
    year = scrape_year(row['Domain'])
    results.append({
        'Center': row['Name'],
        'Domain': row['Domain'],
        'Founding Year': year
    })
    progress.progress((i+1)/total)

# Display and download
out = pd.DataFrame(results)
st.write("### Founding Years:")
st.dataframe(out)

buffer = BytesIO()
out.to_excel(buffer, index=False, engine='openpyxl')
buffer.seek(0)
st.download_button(
    "Download as Excel",
    data=buffer,
    file_name="fqhc_founding_years.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
