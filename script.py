import pandas as pd
import re, time, requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://www.butlersystem.com"
SHOP_URL = "https://www.butlersystem.com/supply-division"

HEADERS = {"User-Agent": "Mozilla/5.0"}

def scrape_categories():
    soup = get_soup(SHOP_URL)

    categories = []
    seen = set()

    category_names = {
        "Butler Maximum Cleaning Products",
        "Carpet Cleaning",
        "Upholstery Cleaning",
        "Deodorization and Restoration",
        "Deodorization & Restoration",
        "Hard Surface",
        "Hard Surface Cleaner",
        "Spot and Stain Removal Products",
        "Spot & Stain Removal Products",
        "Specialty Cleaning",
        "Accessories",
        "Accessories & Supplies",
        "Restoration Equipment",
        "Tools and Parts",
        "Tools & Parts",
        "Portable Equipment",
        "Tile and Hard Surface Equipment",
        "Tile & Hard Surface Equipment",
        "Hoses and Connectors",
        "Hoses & Connectors",
        "Butler System Accessories",
        "Butler System Replacement Parts",
        "Fittings and Connectors",
        "Fittings & Connectors",
        "Carpet Repair",
    }

    for a in soup.find_all("a", href=True):
        name = clean_text(a.get_text())
        href = make_absolute(a["href"])

        if not name: continue
        if name not in category_names: continue
        if href in seen: continue

        seen.add(href)

        image_url = None
        img = a.find("img")

        if img and img.get("src"):
            image_url = make_absolute(img.get("src"))

        if image_url is None and a.parent:
            nearby_img = a.parent.find("img")
            if nearby_img and nearby_img.get("src"):
                image_url = make_absolute(nearby_img.get("src"))

        categories.append({
            "Name": name,
            "URL": href,
            "Image": image_url
        })

    categories_df = pd.DataFrame(categories).drop_duplicates(subset=["URL"]).reset_index(drop=True)
    return categories_df


def scrape_product_links(category_name, category_url):
    soup = get_soup(category_url)

    product_links = []
    seen = set()

    for a in soup.find_all("a", href=True):
        link_text = clean_text(a.get_text())
        href = make_absolute(a["href"])

        if "View Details" in link_text and href not in seen:
            seen.add(href)
            product_links.append({
                "Category Name": category_name,
                "Product URL": href
            })

    if not product_links:
        for a in soup.find_all("a", href=True):
            href = make_absolute(a["href"])
            text = clean_text(a.get_text())

            if not href: continue
            if href == category_url: continue
            if BASE_URL not in href: continue

            if text and href not in seen:
                seen.add(href)
                product_links.append({
                    "Category Name": category_name,
                    "Product URL": href
                })

    return product_links


def extract_sku(soup):
    text = clean_text(soup.get_text("\n"))
    match = re.search(r"\b[A-Z0-9.\-]{5,}\b", text)

    return match.group(0) if match else None

def extract_prices(soup):
    text = clean_text(soup.get_text(" "))

    prices = re.findall(r"\$\d[\d,]*(?:\.\d{2})?", text)
    sale_price, listed_price = None, None

    if len(prices) >= 1:
        sale_price = prices[0]

    if len(prices) >= 2:
        listed_price = prices[1]

    return sale_price, listed_price

def extract_volume_pricing(soup):
    text = soup.get_text("\n")
    if "VOLUME SAVINGS" not in text.upper():
        return None

    lines = [clean_text(line) for line in text.splitlines() if clean_text(line)]
    volume_lines, capture = [], False

    for line in lines:
        upper_line = line.upper()

        if "VOLUME SAVINGS" in upper_line:
            capture = True
            volume_lines.append(line)
            continue

        if capture:
            if line in ["QTY:", "Go back"]:
                break

            volume_lines.append(line)

            if len(volume_lines) > 12:
                break

    if volume_lines:
        return " | ".join(volume_lines)

    return None

def extract_description(soup):
    lines = [clean_text(line) for line in soup.get_text("\n").splitlines()]
    lines = [line for line in lines if line]

    ignore_words = {
        "QTY:",
        "Go back",
        "Download SDS Sheet",
        "Product Categories"
    }

    description_parts = []

    for line in lines:
        if line in ignore_words: continue

        if re.fullmatch(r"\$\d[\d,]*(?:\.\d{2})?", line): continue
        if re.fullmatch(r"[A-Z0-9.\-]{5,}", line): continue

        if "VOLUME SAVINGS" in line.upper(): continue

        if len(line) > 40:
            description_parts.append(line)

    if description_parts:
        return " ".join(description_parts[:8])

    return None

def extract_all_images(soup, current_url):
    images = []
    seen = set()

    for img in soup.find_all("img"):
        src = img.get("src")
        if not src:
            continue

        img_url = urljoin(current_url, src)

        if img_url not in seen:
            seen.add(img_url)
            images.append(img_url)

    return images

def extract_sds_link(soup, current_url):
    for a in soup.find_all("a", href=True):
        text = clean_text(a.get_text()).lower()
        href = a["href"]

        if "sds" in text or "sds" in href.lower():
            return urljoin(current_url, href)

    return None

def extract_product_options(soup):
    options = []

    for select in soup.find_all("select"):
        option_values = []
        for option in select.find_all("option"):
            value = clean_text(option.get_text())
            if value:
                option_values.append(value)

        if option_values:
            options.append(" / ".join(option_values))

    if options:
        return " | ".join(options)

    return None

def extract_product_name(soup):
    h1 = soup.find("h1")
    if h1:
        return clean_text(h1.get_text())

    if soup.title:
        title = clean_text(soup.title.get_text())
        return title

    return None


def scrape_product(category_name, product_url):
    try:
        soup = get_soup(product_url)

        product_name = extract_product_name(soup)
        sku = extract_sku(soup)
        sale_price, listed_price = extract_prices(soup)
        volume_pricing = extract_volume_pricing(soup)
        product_options = extract_product_options(soup)
        description = extract_description(soup)
        images = extract_all_images(soup, product_url)
        sds_sheet = extract_sds_link(soup, product_url)

        return {
            "Category Name": category_name, "Product Name": product_name, "SKU": sku, 
            "Volume Pricing": volume_pricing, "Product Options": product_options, 
            "Sale Price": sale_price, "Listed Price": listed_price,  "URL": product_url,
            "Description": description, "Images": images, "SDS Sheet": sds_sheet
        }

    except Exception as e:
        print("Error scraping product:", product_url)
        print(e)

        return {
            "Category Name": category_name, "Product Name": None,
            "SKU": None, "Volume Pricing": None, "Product Options": None,
            "Sale Price": None, "Listed Price": None, "URL": product_url,
            "Description": None, "Images": [], "SDS Sheet": None
        }


def get_soup(url):
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    return BeautifulSoup(response.text, "html.parser")

def clean_text(text):
    if text is None:
        return ""
    
    return " ".join(text.strip().split())

def make_absolute(url):
    if not url:
        return None
    
    return urljoin(BASE_URL, url)



def scrape():
    categories_df = scrape_categories()
    all_product_links = []

    for _, row in categories_df.iterrows():
        category_name = row["Name"]
        category_url = row["URL"]

        # print("Scraping category:", category_name)
        links = scrape_product_links(category_name, category_url)
        all_product_links.extend(links)

        # time.sleep(1)

    product_links_df = pd.DataFrame(all_product_links).drop_duplicates(subset=["Product URL"]).reset_index(drop=True)
    all_products = []

    for _, row in product_links_df.iterrows():
        category_name = row["Category Name"]
        product_url = row["Product URL"]

        # print("Scraping product:", product_url)
        product_data = scrape_product(category_name, product_url)
        all_products.append(product_data)

        # time.sleep(1)

    products_df = pd.DataFrame(all_products)
    return categories_df, products_df


if __name__ == "__main__":
    categories_df, products_df = scrape()

    print("\nCATEGORIES")
    print(categories_df.head())

    print("\nPRODUCTS")
    print(products_df.head())

    categories_df.to_excel("butler_categories.xlsx", index=False)
    products_df.to_excel("butler_products.xlsx", index=False)

    print("\nSaved:")
    print(" - butler_categories.xlsx")
    print(" - butler_products.xlsx")