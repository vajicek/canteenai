import os
import json
import re
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, jsonify
from openai import OpenAI
from dotenv import load_dotenv
import httpx
from datetime import datetime

load_dotenv()

app = Flask(__name__)

CANTEENS = [
    {
        "id": "ecko",
        "name": "Éčko",
        "url": "https://www.prague-catering.cz/provozovny/Kantyna-ECKO/Denni-menu-kantyny-ECKO/",
    },
    {
        "id": "futurama",
        "name": "Futurama",
        "url": "https://www.prague-catering.cz/provozovny/jidelna-kantyna-praha/jidelna-denni-menu-praha-8/",
    },
    {
        "id": "rustonka",
        "name": "Rustonka",
        "url": "https://fastgoodrustonka.cz/nabidka.php?restaurace=rustonka",
        "scraper": "rustonka",
    },
    {
        "id": "pivokarlin",
        "name": "Pivokarlin",
        "url": "https://www.pivokarlin.cz/",
        "scraper": "pivokarlin",
    },
]


def get_canteen(canteen_id):
    for c in CANTEENS:
        if c["id"] == canteen_id:
            return c
    return CANTEENS[0]


def normalize_name(name):
    # Replace tabs/newlines and collapse runs of whitespace into a single space
    name = re.sub(r"\s+", " ", name).strip()
    # Normalize space before punctuation like commas
    name = re.sub(r"\s+([,;])", r"\1", name)
    # Add a space after a comma when missing (e.g. "masem,vejci" -> "masem, vejci")
    name = re.sub(r",(?=\S)", ", ", name)
    return name


def scrape_menu(url):
    resp = requests.get(url, timeout=15)
    resp.encoding = resp.apparent_encoding
    soup = BeautifulSoup(resp.text, "html.parser")

    table = soup.find("table", class_="dennimenu")
    if not table:
        return []

    categories = {
        "polévk": "soup",
        "těstovin": "pasta",
        "pizza": "pizza",
        "hlavní jíd": "main",
        "salátový bar": "salad_bar",
        "bufet": "buffet",
        "teplý": "buffet",
    }

    # Non-menu strings to skip
    skip_strings = [
        "denní nabídka", "denní menu", "customer notice", "upozornění",
        "změna v položkách", "naše pokrmy", "bližší", "poloviční",
        "připraven", "doprodej", "pokud zůstáváte", "napište",
        "jméno", "telefon", "e-mail", "předmět", "text",
        "kontaktujte", "restpoint", "dag juscak", "sandra",
        "nastavení", "web:", "na košince", "tel.:",
        "our dishes may contain", "for half portion", "meals are sold",
        "výběr z míchaných", "selection of mixed", "hot, vegetables",
        "salad bar 100", "pizza 30 cm",
    ]

    # Category header words that should NOT be treated as items
    category_headers = ["polévk", "těstovin", "pizza", "hlavní jíd",
                        "salátový bar", "bufet", "teplý", "denní nabídka", "denní menu"]

    items = []
    current_category = ""
    seen_names = set()
    pending_price = ""
    prev_cell1 = ""

    rows = table.find_all("tr")
    for row in rows:
        cells = row.find_all(["td", "th"])
        if len(cells) < 1:
            continue

        cell1 = cells[0].get_text(strip=True)
        cell2 = cells[1].get_text(strip=True) if len(cells) > 1 else ""

        if not cell1:
            continue

        # Check if it's a category header
        cell1_lower = cell1.lower()
        is_category = False
        for cat_key, cat_val in categories.items():
            if cat_key in cell1_lower:
                current_category = cat_val
                is_category = True
                break

        if is_category:
            # The price might be in cell2 (e.g., "39 Kč" for soups)
            price_match = re.search(r"(\d+(?:/\d+)?)\s*Kč", cell2)
            if price_match:
                pending_price = price_match.group(0)
            continue

        # Skip known non-menu strings
        if any(s in cell1_lower for s in skip_strings):
            continue

        # Skip if it's just a category header name
        if cell1_lower in category_headers:
            continue

        # Skip price-only or portion-size rows
        if re.match(r"^\d+/\d+g$", cell1):
            pending_price = cell2 if "Kč" in cell2 else ""
            continue
        if re.match(r"^[\d/]+\s*Kč$", cell1):
            pending_price = cell1
            continue

        # Skip English translations (no Czech diacritics, relatively short)
        has_czech = bool(re.search(r"[čďěňřšťůžýáíéú]", cell1, re.IGNORECASE))
        if not has_czech and len(cell1) < 80:
            continue

        # Check if this is a price row (e.g., "Pizza 30 cm" with price in cell2)
        if "Kč" in cell2 and not "Kč" in cell1:
            # This is an item with price on same row
            clean_name = cell1
            price = re.search(r"(\d+(?:/\d+)?)\s*Kč", cell2)
            pending_price = price.group(0) if price else cell2

            # Extract allergens
            allergen_match = re.search(r"\s+((?:\d+,)*\d+)\s*$", clean_name)
            allergens = allergen_match.group(1) if allergen_match else ""
            clean_name = normalize_name(re.sub(r"\s+((?:\d+,)*\d+)\s*$", "", clean_name))

            if clean_name and clean_name not in seen_names and len(clean_name) > 3:
                cat = current_category or "other"
                # Only keep items from the "Hlavní jídla" (main dishes) section
                if cat != "main":
                    continue
                seen_names.add(clean_name)
                items.append({
                    "name": clean_name,
                    "category": cat,
                    "price": pending_price,
                    "allergens": allergens,
                })
            continue

        # It's an item row (name in cell1, possibly empty cell2)
        clean_name = cell1

        # Extract allergens from end (like "1,3,9")
        allergen_match = re.search(r"\s+((?:\d+,)*\d+)\s*$", clean_name)
        allergens = allergen_match.group(1) if allergen_match else ""
        clean_name = normalize_name(re.sub(r"\s+((?:\d+,)*\d+)\s*$", "", clean_name))

        if clean_name and clean_name not in seen_names and len(clean_name) > 3:
            seen_names.add(clean_name)
            # Use pending price from previous row
            price = pending_price
            if "Kč" not in price:
                price = ""

            cat = current_category or "other"
            # Only keep items from the "Hlavní jídla" (main dishes) section
            if cat != "main":
                continue

            # Auto-categorize if needed
            if cat == "other":
                cn = clean_name.lower()
                if any(w in cn for w in ["vývar", "polévka"]):
                    cat = "soup"
                elif any(w in cn for w in ["salát", "caesar"]):
                    cat = "salad"
                elif any(w in cn for w in ["tofu", "čočka", "nachos", "houby"]):
                    cat = "vegetarian"

            items.append({
                "name": clean_name,
                "category": cat,
                "price": price,
                "allergens": allergens,
            })

        # Reset pending price after using it
        if not cell2 or "Kč" not in cell2:
            pending_price = ""

    return items


def scrape_rustonka(url):
    resp = requests.get(url, timeout=15)
    resp.encoding = resp.apparent_encoding
    soup = BeautifulSoup(resp.text, "html.parser")

    # Sections that count as main dishes
    main_sections = ["hotová jídla", "tip kuchaře", "salát jako hlavní jídlo"]

    # Select today's (active) day tab pane that holds the canteen main-menu sections
    active_pane = None
    for pane in soup.find_all("div", class_="tab-pane"):
        cls = pane.get("class", [])
        if "in" not in cls or "active" not in cls:
            continue
        section_names = [
            normalize_name(h.find("div", class_="name").get_text(strip=True)).lower()
            for h in pane.find_all("div", class_="headline")
            if h.find("div", class_="name")
        ]
        if any(name in section_names for name in main_sections):
            active_pane = pane
            break
    if not active_pane:
        return []

    items = []
    current_section = ""
    seen_names = set()

    for elem in active_pane.find_all("div"):
        classes = elem.get("class") or []

        # Track current section from headline blocks
        if "headline" in classes and elem.parent and "tab-pane" in (elem.parent.get("class") or []):
            name_el = elem.find("div", class_="name")
            if name_el:
                current_section = normalize_name(name_el.get_text(strip=True)).lower()

        # Collect items inside a menu-items block
        if "item" in classes and elem.parent and "menu-items" in (elem.parent.get("class") or []):
            if current_section not in main_sections:
                continue

            name_el = elem.find("div", class_="name")
            price_el = elem.find("div", class_="price")
            if not name_el:
                continue

            clean_name = normalize_name(name_el.get_text(" ", strip=True))
            if not clean_name or len(clean_name) < 3 or clean_name in seen_names:
                continue
            if "Kč" in clean_name:
                continue

            seen_names.add(clean_name)
            price = price_el.get_text(strip=True) if price_el else ""
            match = re.match(r"^(\d+),-$", price)
            if match:
                price = f"{match.group(1)} Kč"

            allergens = ",".join(li.get_text(strip=True) for li in elem.select(".allergen li"))
            allergens = allergens.strip(",")

            items.append({
                "name": clean_name,
                "category": "main",
                "price": price,
                "allergens": allergens,
            })
    return items


def scrape_pivokarlin(url):
    resp = requests.get(url, timeout=15, verify=False)
    resp.encoding = resp.apparent_encoding
    soup = BeautifulSoup(resp.text, "html.parser")

    menu_elem = soup.find(id="menu")
    if not menu_elem:
        return []

    # Map Czech day names to weekday numbers
    day_names = ['Pondělí', 'Úterý', 'Středa', 'Čtvrtek', 'Pátek', 'Sobota', 'Neděle']
    today_weekday = datetime.now().weekday()  # 0=Monday, 6=Sunday
    today_name = day_names[today_weekday]

    # Find the vc_column-inner div for today
    # The div should have format: "DD.MĚSÍC ROKDay name" followed by menu items
    today_div = None
    all_divs = menu_elem.find_all('div', class_='vc_column-inner')
    
    for div in all_divs:
        # Get first nectar_food_menu_item to check if this div has items
        first_item = div.find('div', class_='nectar_food_menu_item')
        if not first_item:
            continue
        
        # Get the text at the start of the div
        text = div.get_text(strip=True)
        
        # Check if this div starts with a date pattern and contains today's day name
        # Pattern should be like "16.ZÁŘÍ2026Středa..."
        if today_name in text and any(month in text for month in ['ZÁŘÍ', 'ŘÍJEN', 'LISTOPAD', 'BŘEZ', 'DUBEN', 'KVĚTEN', 'June', 'ČERV']):
            # Make sure it's not the big header div (which would have way more items/text before the items)
            items_in_div = div.find_all('div', class_='nectar_food_menu_item')
            if len(items_in_div) <= 15:  # Lunch menu should have around 9 items
                today_div = div
                break

    if not today_div:
        return []

    # Extract all nectar_food_menu_item divs from today's div
    menu_items = today_div.find_all('div', class_='nectar_food_menu_item')

    items = []
    for menu_item in menu_items:
        # Get name
        name_elem = menu_item.find('div', class_='item_name')
        if not name_elem:
            continue
        
        name_text = name_elem.get_text(strip=True)
        if not name_text or len(name_text) < 3:
            continue

        # Extract allergens
        allergen_match = re.search(r'\s+([\d,]+)\s*$', name_text)
        allergens = allergen_match.group(1) if allergen_match else ""
        clean_name = re.sub(r'\s+[\d,]+\s*$', '', name_text)

        # Get price
        price_elem = menu_item.find('div', class_='item_price')
        price = price_elem.get_text(strip=True) if price_elem else ""

        if clean_name and len(clean_name) > 3:
            items.append({
                "name": clean_name,
                "category": "main",
                "price": price,
                "allergens": allergens,
            })

    return items


def score_items_with_ai(items):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return score_items_heuristic(items)

    menu_text = "\n".join(
        f"- {item['name']} [{item['category']}] (allergens: {item['allergens'] or 'unknown'})"
        for item in items
    )

    prompt = f"""You are a nutrition expert. Rate each menu item below on a health score from 1 (unhealthy) to 10 (very healthy), and give brief positives and negatives.

Consider: protein content, vegetable/fiber content, processing level, cooking method, calorie density, nutritional balance.
Menu items from a Czech canteen:

{menu_text}

Return ONLY a JSON object, one entry per item name, like:
{{"Item name": {{"score": 7, "positives": ["high protein", "lots of vegetables"], "negatives": ["high calorie", "heavy cream"]}}}}

Keep each positive/negative to 2-4 very short keywords/phrases.
No markdown, no explanation, just the JSON object."""

    print("=" * 60)
    print("PROMPT SENT TO AI:")
    print("=" * 60)
    print(prompt)
    print("=" * 60)

    try:
        text = _score_with_openai(prompt, api_key)

        print("=" * 60)
        print("AI MODEL OUTPUT:")
        print("=" * 60)
        print(text)
        print("=" * 60)

        # Strip markdown code fences if present
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*$", "", text)
        scores = json.loads(text)

        # Handle both simple {name: int} and enriched {name: {score, positives, negatives}} forms
        for item in items:
            entry = scores.get(item["name"], {})
            if isinstance(entry, dict):
                item["health_score"] = entry.get("score", 5)
                item["positives"] = entry.get("positives", [])
                item["negatives"] = entry.get("negatives", [])
            else:
                item["health_score"] = entry if isinstance(entry, int) else 5
                item["positives"] = []
                item["negatives"] = []

        return items
    except Exception as e:
        print(f"AI scoring failed, using heuristic: {e}")
        return score_items_heuristic(items)


def _score_with_openai(prompt, api_key):
    """Score items using OpenAI API."""
    base_url = os.environ.get("OPENAI_BASE_URL")
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    client_kwargs["http_client"] = httpx.Client(verify=False)
    client = OpenAI(**client_kwargs)

    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=10000,
    )
    return resp.choices[0].message.content.strip()


def score_items_heuristic(items):
    """Fallback heuristic scoring when no API key is available."""
    for item in items:
        score = 5
        name_lower = item["name"].lower()
        cat = item["category"]

        # Boost healthy items
        if any(w in name_lower for w in ["salát", "salad", "zelenin", "tofu", "čočka", "lentil"]):
            score += 2
        if "grilovan" in name_lower or "pečen" in name_lower and "brambor" not in name_lower:
            score += 1
        if cat == "vegetarian":
            score += 1
        if "vývar" in name_lower or "broth" in name_lower:
            score += 1

        # Penalize less healthy items
        if "špek" in name_lower or "klobás" in name_lower:
            score -= 2
        if "smažen" in name_lower or "fried" in name_lower:
            score -= 1
        if "smetana" in name_lower or "cream" in name_lower:
            score -= 1
        if "sýr" in name_lower and "salát" not in name_lower:
            score -= 1
        if "nachos" in name_lower:
            score -= 2
        if "pizza" in cat.lower():
            score -= 1

        item["health_score"] = max(1, min(10, score))
        item["positives"] = []
        item["negatives"] = []

    return items


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/menu")
def api_menu():
    all_items = []
    seen = set()
    for canteen in CANTEENS:
        try:
            if canteen.get("scraper") == "rustonka":
                items = scrape_rustonka(canteen["url"])
            elif canteen.get("scraper") == "pivokarlin":
                items = scrape_pivokarlin(canteen["url"])
            else:
                items = scrape_menu(canteen["url"])
            for item in items:
                key = item["name"].lower()
                if key in seen:
                    continue
                seen.add(key)
                item["canteen"] = canteen["name"]
                all_items.append(item)
        except Exception as e:
            print(f"Failed to scrape {canteen['name']}: {e}")

    all_items = score_items_with_ai(all_items)
    all_items.sort(key=lambda x: x["health_score"], reverse=True)
    return jsonify({"ok": True, "items": all_items})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
