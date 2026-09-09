# Canteen Health Menu

A simple web app that scrapes daily menus from Prague Catering canteens (Éčko, Futurama), scores each *Hlavní jídlo* (main dish) by health using an LLM, and displays them ranked best-to-worst with brief nutritional positives/negatives.

## Features

- Scrapes main dishes from multiple canteens and merges them into one ranked list
- AI health scoring (1-10) with brief positives/negatives per dish
- Each item labelled with its source canteen
- Fallback keyword-based scoring when no API key is configured

## Supported canteens

- **Éčko** – Prague Catering (prague-catering.cz)
- **Futurama** – Prague Catering (prague-catering.cz)
- **Rustonka** – Fastgood (fastgoodrustonka.cz)

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

### OpenAI API Options

You can customize the OpenAI client with the following optional environment variables:

- **`OPENAI_MODEL`** – Model to use for scoring (default: `gpt-4o-mini`)
  ```
  OPENAI_MODEL=gpt-4o
  ```

- **`OPENAI_BASE_URL`** – Custom base URL for OpenAI-compatible APIs (e.g., Ollama, LM Studio, Azure OpenAI)
  ```
  OPENAI_BASE_URL=http://localhost:8000/v1
  ```

### Example configurations

**Using default OpenAI API:**
```
OPENAI_API_KEY=sk-your-key-here
```

**Using a different model:**
```
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4-turbo
```

**Using a local Ollama instance:**
```
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL=llama2
```

**Using Azure OpenAI:**
```
OPENAI_API_KEY=your-azure-key
OPENAI_BASE_URL=https://your-resource.openai.azure.com/openai/deployments/your-deployment/
OPENAI_MODEL=gpt-4
```

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

Add an entry to the `CANTEENS` list in `app.py`. For the Prague Catering format (a `<table class="dennimenu">` with a "Hlavní jídla" section), the default `scrape_menu` parser is used:

```python
CANTEENS = [
    {"id": "ecko", "name": "Éčko", "url": "https://..."},
]
```

For other site formats, provide a dedicated scraper function and reference it via the `scraper` field:

```python
CANTEENS = [
    {"id": "rustonka", "name": "Rustonka", "url": "https://...", "scraper": "rustonka"},
]
```

The Rustonka scraper reads the active day tab pane and keeps items from the sections `hotová jídla`, `TIP KUCHAŘE`, and `salát jako hlavní jídlo`.