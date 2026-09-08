# Canteen Health Menu

A simple web app that scrapes daily menus from Prague Catering canteens (Éčko, Futurama), scores each *Hlavní jídlo* (main dish) by health using an LLM, and displays them ranked best-to-worst with brief nutritional positives/negatives.

## Features

- Scrapes main dishes from multiple canteens and merges them into one ranked list
- AI health scoring (1-10) with brief positives/negatives per dish
- Each item labelled with its source canteen
- Fallback keyword-based scoring when no API key is configured

## Requirements

- Python 3.10+
- [OpenAI API key](https://platform.openai.com/api-keys) (optional, for AI scoring)

## Installation

```bash
cd canteen-health-menu
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Create a `.env` file from the example and add your OpenAI API key:

```bash
cp .env.example .env
```

Edit `.env`:

```
OPENAI_API_KEY=sk-your-key-here
```

If no key is set, the app falls back to heuristic scoring (no AI call).

## Running

```bash
python app.py
```

Then open http://localhost:5000 in your browser.

## How it works

1. `GET /` serves the web UI
2. `GET /api/menu` scrapes all canteen menus, scores them via the OpenAI API (or heuristic fallback), and returns the ranked list
3. Each item includes: `name`, `category`, `price`, `allergens`, `canteen`, `health_score`, `positives`, `negatives`

## Adding a canteen

Add an entry to the `CANTEENS` list in `app.py`:

```python
CANTEENS = [
    {"id": "ecko", "name": "Éčko", "url": "https://..."},
    {"id": "futurama", "name": "Futurama", "url": "https://..."},
]
```

The scraper expects the site's `<table class="dennimenu">` structure and only keeps items from the "Hlavní jídla" section.