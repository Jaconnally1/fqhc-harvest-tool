
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup
import tldextract
import streamlit as st
from io import BytesIO

# Title
st.title("FQHC HR Director Scraper")

st.markdown("""
Upload your FQHC list (CSV with columns 'Name' and optional 'Website'), then click **Run** to scrape HR Director names and emails.
""")

uploaded_file = st.file_uploader("Choose CSV file", type="csv")
if uploaded_file:
    df = pd.read_csv(uploaded_file)
    st.write("Preview of uploaded data:", df.head())

    if st.button("Run Harvest"):
        # Derive domain
        def guess_domain(name):
            slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
            return f"https://{slug}.org"

        def extract_domain(website):
            ext = tldextract.extract(website)
            if ext.suffix:
                return f"https://{ext.domain}.{ext.suffix}"
            return None

        def get_domain(row):
            if pd.notna(row.get('Website')):
                d = extract_domain(row['Website'])
                if d:
                    return d
            return guess_domain(row['Name'])

        df['Domain'] = df.apply(get_domain, axis=1)

        paths = ['/', '/about', '/about-us', '/our-team', '/team', '/leadership', '/staff']
        results = []

        progress = st.progress(0)
        total = len(df)

        for idx, row in df.iterrows():
            domain = row['Domain']
            hr_name = ""
            hr_email = ""

            # try leadership pages
            for p in paths:
                try:
                    r = requests.get(domain + p, timeout=5)
                    if r.status_code == 200 and re.search(r'HR Director', r.text, re.I):
                        soup = BeautifulSoup(r.text, 'html.parser')
                        tag = soup.find(text=re.compile(r'HR Director', re.I))
                        if tag:
                            text = tag.parent.get_text(" ", strip=True)
                            m = re.match(r'(.+?)(?:\s*[-–])', text)
                            if m:
                                hr_name = m.group(1).strip()
                        mailto = soup.find('a', href=re.compile(r'mailto:', re.I))
                        if mailto:
                            em = re.search(r'mailto:([^?]+)', mailto['href'])
                            if em:
                                hr_email = em.group(1)
                        break
                except requests.RequestException:
                    continue

            # fallback: scan homepage for hr@ or jobs@
            if not hr_email:
                try:
                    r = requests.get(domain, timeout=5)
                    if r.status_code == 200:
                        soup = BeautifulSoup(r.text, 'html.parser')
                        for a in soup.find_all('a', href=re.compile(r'mailto:', re.I)):
                            email = re.search(r'mailto:([^?]+)', a['href']).group(1)
                            if re.search(r'\b(hr|jobs)@', email, re.I):
                                hr_email = email
                                break
                except requests.RequestException:
                    pass

            results.append({
                'Name': row['Name'],
                'Domain': domain,
                'HR Director': hr_name,
                'HR Email': hr_email
            })

            progress.progress((idx + 1) / total)

        out_df = pd.DataFrame(results)
        st.write("Scraping complete. Preview:")
        st.dataframe(out_df)

        # Provide download
        towrite = BytesIO()
        out_df.to_excel(towrite, index=False, engine='openpyxl')
        towrite.seek(0)
        st.download_button(
            label="Download as Excel",
            data=towrite,
            file_name="fqhc_hr_contacts.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
