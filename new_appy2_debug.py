#!/usr/bin/env python3
import re
import pandas as pd
import requests
import tldextract
import streamlit as st
from bs4 import BeautifulSoup
from io import StringIO, BytesIO

st.title("FQHC Executive Roles Scraper Debug")
st.markdown(
    """
    Upload a CSV with columns 'Name' and 'Website'.
    This debug app logs every URL tried and shows extraction details.
    """
)

uploaded_file = st.file_uploader("Choose CSV file", type="csv")
if not uploaded_file:
    st.info("Please upload a CSV file to debug.")
    st.stop()

df = pd.read_csv(uploaded_file)
st.write("### Centers to scrape:", df[['Name', 'Website']].fillna(""))

def get_domain(row):
    site = row.get('Website', '')
    if pd.notna(site) and site:
        ext = tldextract.extract(site)
        if ext.suffix:
            return f"https://{ext.domain}.{ext.suffix}"
    slug = re.sub(r'[^a-z0-9]+','-',row['Name'].lower()).strip('-')
    return f"https://{slug}.org"

df['Domain'] = df.apply(get_domain, axis=1)

paths = [
    '/', '/about', '/about-us', '/our-team', '/team',
    '/leadership', '/admin-team', '/info-center/about/leadership'
]

patterns = {
    'Human Resources Director': re.compile(r'([A-Z][a-z]+(?: [A-Z][a-z]+)+)\s*[-–,:]?\s*Human Resources Director', re.IGNORECASE),
    'Chief Financial Officer': re.compile(r'([A-Z][a-z]+(?: [A-Z][a-z]+)+)\s*[-–,:]?\s*Chief Financial Officer', re.IGNORECASE)
}

log_buf = StringIO()
results = []
for _, row in df.iterrows():
    name = row['Name']
    domain = row['Domain'].rstrip('/')
    log_buf.write(f"Scraping {name} ({domain})\n")
    hr = ''
    cfo = ''
    for path in paths:
        url = domain + path
        log_buf.write(f"  Trying URL: {url}\n")
        try:
            resp = requests.get(url, headers={'User-Agent':'Mozilla/5.0'}, timeout=5)
            log_buf.write(f"    Status: {resp.status_code}\n")
            if resp.status_code != 200:
                continue
            text = ' '.join(BeautifulSoup(resp.text,'html.parser').stripped_strings)
            if not hr:
                m = patterns['Human Resources Director'].search(text)
                if m:
                    hr = m.group(1)
                    log_buf.write(f"    Found HR Director: {hr}\n")
            if not cfo:
                m = patterns['Chief Financial Officer'].search(text)
                if m:
                    cfo = m.group(1)
                    log_buf.write(f"    Found CFO: {cfo}\n")
            if hr and cfo:
                break
        except Exception as e:
            log_buf.write(f"    Error: {e}\n")
    results.append({'Name':name, 'HR Director':hr, 'CFO':cfo})
    log_buf.write("---\n")

st.write("### Debug Log")
st.text(log_buf.getvalue())

out_df = pd.DataFrame(results)
st.write("### Extraction Results")
st.dataframe(out_df)

buffer = BytesIO()
out_df.to_excel(buffer, index=False, engine='openpyxl')
buffer.seek(0)
st.download_button(
    label="Download Results",
    data=buffer,
    file_name="debug_executives.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
