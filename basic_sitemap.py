# general purpose sitemap generator for a single domain
import sys
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
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

def get_unique_filename(base_name="basic_sitemap_output", ext="xlsx"):
    i = 1
    filename = f"{base_name}.{ext}"
    while os.path.exists(filename):
        filename = f"{base_name}_{i}.{ext}"
        i += 1
    return filename

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
                "URL": url,
                "Redirects To": "-",
                "Title": title,
                "File Type": file_extension,
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
df = df.sort_values(by="URL", ignore_index=True)  # Sort A-Z by URL

output_filename = get_unique_filename()

# Write to Excel with formatting
with pd.ExcelWriter(output_filename, engine='xlsxwriter') as writer:
    df.to_excel(writer, index=False, sheet_name='Sitemap')
    workbook  = writer.book
    worksheet = writer.sheets['Sitemap']

    # Set column widths (Title = ~350px ≈ 50 chars wide, URLs = 30 chars)
    worksheet.set_column(df.columns.get_loc("Title"), df.columns.get_loc("Title"), 50)
    worksheet.set_column(df.columns.get_loc("URL"), df.columns.get_loc("URL"), 30)
    worksheet.set_column(df.columns.get_loc("Notes"), df.columns.get_loc("Notes"), 22)

    # Styles
    red_font = workbook.add_format({'font_color': 'red'})
    blue_font = workbook.add_format({'font_color': 'blue'})
    green_font = workbook.add_format({'font_color': 'green'})

    # Column indexes
    url_col = df.columns.get_loc("URL")
    filetype_col = df.columns.get_loc("File Type")

    for row_num, row in df.iterrows():
        excel_row = row_num + 1  # account for header

        filetype = row["File Type"]

        # Write hyperlink for original URL
        worksheet.write_url(excel_row, url_col, row["URL"], string=row["URL"])

        # Apply font color formatting based on file type
        if filetype == "pdf":
            for col_num in range(len(df.columns)):
                worksheet.write(excel_row, col_num, row.iloc[col_num], red_font)
        elif filetype == "php":
            worksheet.write(excel_row, filetype_col, filetype, green_font)
        elif filetype == "pcf":
            worksheet.write(excel_row, filetype_col, filetype, blue_font)

print(f"✔️  Crawl complete. General use sitemap spreadsheet for {base_url} saved as {output_filename}")
