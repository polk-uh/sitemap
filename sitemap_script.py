# for internal use only
import sys
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, quote
import pandas as pd
import time
from tqdm import tqdm
import os
from pathlib import Path

if len(sys.argv) != 2:
    print("Usage: python scriptname.py https://example.com/")
    sys.exit(1)

base_url = sys.argv[1]
visited = set()
url_data = []
crawl_queue = [(base_url, "ROOT")]

def get_title(soup):
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return "-"

def get_unique_filename(base_name="sitemap_output", ext="xlsx"):
    i = 1
    filename = f"{base_name}.{ext}"
    while os.path.exists(filename):
        filename = f"{base_name}_{i}.{ext}"
        i += 1
    return filename

def generate_mc_edit_url(modern_url):
    if modern_url.endswith('.pdf') or modern_url == "https://modern.web.uh.edu/financial":
        return "-"
    base_edit = "https://a.cms.omniupdate.com/11/#oucampus/uh/www/previewedit/"
    path = modern_url.replace("https://modern.web.uh.edu", "")
    if path == "":
        return ""
    return base_edit + quote(path.strip("/"), safe='') + "%2Findex.pcf"

print(f"Starting crawl on: {base_url}")

with tqdm(total=0, unit="page", dynamic_ncols=True) as pbar:
    while crawl_queue:
        url, parent_url = crawl_queue.pop(0)

        if url in visited or not url.startswith(base_url):
            continue
        visited.add(url)
        pbar.total = len(visited)
        pbar.update(1)
        pbar.set_description("Crawling")

        try:
            response = requests.get(url, timeout=5)
            if response.status_code != 200:
                continue

            soup = BeautifulSoup(response.text, 'html.parser')
            title = get_title(soup)

            file_extension = Path(urlparse(url).path).suffix.lower().lstrip('.') or 'pcf'

            url_data.append({
                "@uh.edu URL": url,
                "Redirects To": "-",
                "Title": title,
                "File Type": file_extension,
                "QAed?": "",
                "Looked at?": "",
                "Redirect?": "Verify" if "index.php" in url.lower() else "n/a",
                "Notes": "-",
            })

            for link in soup.find_all('a', href=True):
                next_url = urljoin(url, link['href'].split('#')[0])
                parsed = urlparse(next_url)
                clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if clean_url not in visited:
                    crawl_queue.append((clean_url, url))
            time.sleep(0.05)
        except Exception as e:
            pbar.write(f"Error: {url} — {e}")

# Convert to DataFrame
df = pd.DataFrame(url_data)
df = df.sort_values(by="@uh.edu URL", ignore_index=True)  # Sort A-Z by URL

# Add 'Modern URL' and 'MC Edit Page URL' columns
df['Modern URL'] = df['@uh.edu URL'].str.replace(
    "https://www.uh.edu/", "https://modern.web.uh.edu/", regex=False
)
df["MC Edit Page URL"] = df["Modern URL"].apply(generate_mc_edit_url)

output_filename = get_unique_filename()

# Write to Excel with formatting
with pd.ExcelWriter(output_filename, engine='xlsxwriter') as writer:
    df.to_excel(writer, index=False, sheet_name='Sitemap')
    workbook  = writer.book
    worksheet = writer.sheets['Sitemap']

    # Set column widths (Title = ~350px ≈ 50 chars wide, URLs = 30 chars)
    worksheet.set_column(df.columns.get_loc("Title"), df.columns.get_loc("Title"), 50)
    worksheet.set_column(df.columns.get_loc("@uh.edu URL"), df.columns.get_loc("@uh.edu URL"), 30)
    worksheet.set_column(df.columns.get_loc("Notes"), df.columns.get_loc("Notes"), 22)

    # Styles
    red_font = workbook.add_format({'font_color': 'red'})
    blue_font = workbook.add_format({'font_color': 'blue'})
    green_font = workbook.add_format({'font_color': 'green'})

    # Column indexes
    url_col = df.columns.get_loc("@uh.edu URL")
    filetype_col = df.columns.get_loc("File Type")
    mc_edit_col = df.columns.get_loc("MC Edit Page URL")

    for row_num, row in df.iterrows():
        excel_row = row_num + 1  # account for header

        filetype = row["File Type"]
        mc_edit_url = row["MC Edit Page URL"]

        # Write hyperlink for original @uh.edu URL
        worksheet.write_url(excel_row, url_col, row["@uh.edu URL"], string=row["@uh.edu URL"])

        # Write hyperlink for MC Edit URL (if any)
        if mc_edit_url:
            worksheet.write_url(excel_row, mc_edit_col, mc_edit_url, string=mc_edit_url)

        # Apply font color formatting based on file type
        if filetype == "pdf":
            for col_num in range(len(df.columns)):
                worksheet.write(excel_row, col_num, row.iloc[col_num], red_font)
        elif filetype == "php":
            worksheet.write(excel_row, filetype_col, filetype, green_font)
        elif filetype == "pcf":
            worksheet.write(excel_row, filetype_col, filetype, blue_font)

print(f"✔️  Crawl complete. Sitemap spreadsheet for {base_url} saved as {output_filename}")
