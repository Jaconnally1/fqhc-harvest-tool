#!/usr/bin/env python3
import re
import pandas as pd
import requests
import tldextract
import streamlit as st
from bs4 import BeautifulSoup
from io import BytesIO

# Streamlit App: Leadership Scraper
st.title("FQHC Leadership Scraper")
st.markdown(
    """
    Upload a CSV of FQHCs (with columns 'Name' and optional 'Website').
    The app will visit each site's leadership pages and extract the names of any leadership team members found.
    """
)

# Upload CSV
uploaded_file = st.file_uploader("Choose CSV file", type="csv")
if not uploaded_file:
    st.info("Please upload a CSV file to begin.")
    st.stop()

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

# Leadership page paths to try
leadership_paths = ['/', '/about', '/about-us', '/our-team', '/team', '/leadership', '/about/leadership', '/who-we-are']

# Function to scrape leadership names from a page
def scrape_leadership_names(domain: str) -> list:
    names = []
    for path in leadership_paths:
        url = domain.rstrip('/') + path
        try:
            r = requests.get(url, timeout=5)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, 'html.parser')
            # Find a leadership header
            header = soup.find(lambda tag: tag.name in ['h1','h2','h3','h4'] and re.search(r'leadership|team|staff|board', tag.text, re.I))
            if not header:
                continue
            # Look for names in the next section
            section = header.find_next_sibling()
            if not section:
                section = header.parent
            # Collect potential names from <li>, <p>, <h3>
            for tag in section.find_all(['li','p','h3']):
                text = tag.get_text(separator=' ', strip=True)
                # Match typical name patterns (e.g. "Jane Doe")
                m = re.match(r'([A-Z][a-z]+(?: [A-Z][a-z]+)+)', text)
                if m:
                    names.append(m.group(1))
            if names:
                break
        except requests.RequestException:
            continue
    # Deduplicate
    return list(dict.fromkeys(names))

# Scrape all centers
results = []
progress = st.progress(0)
total = len(df)
for idx, row in df.iterrows():
    domain = row['Domain']
    leadership = scrape_leadership_names(domain)
    results.append({
        'Center': row['Name'],
        'Domain': domain,
        'Leadership': '; '.join(leadership)
    })
    progress.progress((idx + 1) / total)

# Show results
out_df = pd.DataFrame(results)
st.write("### Leadership extraction results:")
st.dataframe(out_df)

# Download button
buffer = BytesIO()
out_df.to_excel(buffer, index=False, engine='openpyxl')
buffer.seek(0)
st.download_button(
    label="Download as Excel",
    data=buffer,
    file_name="fqhc_leadership_contacts.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
