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

### Quick install (as a systemd service)

The easiest way to install and run canteenai as a system service:

```bash
git clone https://github.com/vajicek/canteenai.git
cd canteenai
sudo ./install.sh
```

The installer will:
- Create a system user (`canteenai`)
- Install the app to `/opt/canteenai`
- Set up the Python virtual environment
- Create `.env` configuration file
- Install and start the systemd service

After installation, configure your API key:

```bash
sudo nano /opt/canteenai/.env
```

Add your OpenAI settings and save. The service will automatically reload with the new configuration.

### Manual installation (development)

For development or if you prefer manual setup:

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

## Running as a systemd service

To run the app as a system service with automatic restarts:

### 1. Create a system user (one-time setup)

```bash
sudo useradd -r -s /bin/bash canteenai
```

### 2. Install the app to `/opt/canteenai`

```bash
sudo mkdir -p /opt/canteenai
sudo cp -r . /opt/canteenai/
sudo chown -R canteenai:canteenai /opt/canteenai
```

### 3. Set up environment

Create `/opt/canteenai/.env` with your configuration:

```bash
sudo nano /opt/canteenai/.env
```

Add your OpenAI settings:

```
OPENAI_API_KEY=sk-your-key-here
OPENAI_BASE_URL=  # Optional
OPENAI_MODEL=     # Optional
```

### 4. Install the systemd service

```bash
sudo cp canteenai.service /etc/systemd/system/
sudo systemctl daemon-reload
```

### 5. Start the service

```bash
sudo systemctl start canteenai
sudo systemctl enable canteenai  # Enable on boot
```

### 6. Check status and logs

```bash
sudo systemctl status canteenai
sudo journalctl -u canteenai -f  # Follow logs
```

### Service management commands

```bash
sudo systemctl start canteenai     # Start
sudo systemctl stop canteenai      # Stop
sudo systemctl restart canteenai   # Restart
sudo systemctl status canteenai    # Check status
sudo journalctl -u canteenai -n 50 # View last 50 logs
```

The app will be available at `http://localhost:5000` and will automatically restart on failure.

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