# CrowdWisdomTrading Predictions Agent

Backend Python project for short-horizon crypto direction prediction using an agent-based workflow.

This project was built for the CrowdWisdomTrading internship assessment and runs an end-to-end loop:

1. Search market context (Polymarket + Kalshi)
2. Fetch latest market data (BTC/ETH, up to 1000 candles)
3. Predict next move (UP/DOWN)
4. Apply Kelly-based risk sizing
5. Persist outcomes and feedback accuracy

---

## Features

- Python backend with structured multi-agent flow
- Hermes-agent dependency and agent-loop orchestration pattern
- OpenRouter integration with model fallback logic
- Apify integration path for market scraping
- Binance data ingestion for latest OHLCV candles
- Kronos adapter path with robust fallback prediction
- Kelly criterion risk management
- Feedback ledger with rolling accuracy
- Clear logging and graceful error handling

---

## Project Structure

```text
crown/
  agents/
    search_agent.py
    data_agent.py
    prediction_agent.py
    risk_agent.py
    feedback_agent.py
  services/
    apify_client.py
    market_sources.py
    binance_client.py
    kronos_adapter.py
    openrouter_client.py
    kelly.py
    hermes_loop.py
    logging_setup.py
  data/
    feedback.json
  config.py
  pipeline.py
  main.py
  requirements.txt
  .env.example
```

---

## Agent Flow

### 1) Search Agent
- Discovers BTC/ETH-related context from Polymarket and Kalshi
- Uses Apify/API loaders with safe fallback behavior

### 2) Data Agent
- Fetches latest OHLCV from Binance
- Default: `5m` interval, `1000` candles per symbol

### 3) Prediction Agent
- Produces `UP` / `DOWN` + confidence per symbol
- Tries Kronos adapter path when available
- Falls back to deterministic signal when unavailable
- Optional OpenRouter rationale enrichment

### 4) Risk Agent
- Converts confidence into position size via fractional Kelly
- Applies max position cap for conservative sizing

### 5) Feedback Agent
- Stores predictions in `data/feedback.json`
- Settles prior predictions on later runs
- Tracks rolling global and per-symbol accuracy

---
##Screenshots
<img width="1920" height="1020" alt="image" src="https://github.com/user-attachments/assets/82a1bd72-d357-4c60-8ec6-16d89209c234" />

## Requirements

- Python 3.11+ (3.12 also fine)
- Git
- Internet access for provider APIs

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

> If `pip.exe` is blocked by local policy, always use `python -m pip ...`.

---

## Environment Configuration

Create `.env` from `.env.example`:

```bash
copy .env.example .env
```

Set required keys:

```env
OPENROUTER_API_KEY=your_openrouter_key_here
APIFY_TOKEN=your_apify_token_here
```

Useful optional settings:

```env
LLM_MODEL=meta-llama/llama-3.1-8b-instruct:free
LLM_FALLBACK_MODELS=meta-llama/llama-3.1-8b-instruct:free,mistralai/mistral-7b-instruct:free
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
ENABLE_APIFY=true
ENABLE_KRONOS=true
KRONOS_REPO_PATH=C:/path/to/Kronos
ENABLE_LLM_REASONING=true
STRICT_INTEGRATIONS=false
KLINE_INTERVAL=5m
KLINE_LIMIT=1000
```

---

## Run

Basic run:

```bash
python main.py
```

Other options:

```bash
python main.py -i 5m
python main.py --log-file logs/run.log -l DEBUG
python main.py -q
```

---

## Example Output

During execution you should see:

- `Step 1/5 Search`
- `Step 2/5 Data`
- `Step 3/5 Prediction`
- `Step 4/5 Risk`
- `Step 5/5 Feedback`
- `=== Pipeline complete ===`

And summary lines like:

- `BTC -> DOWN -> confidence: ... -> position size: ...`
- `ETH -> UP/DOWN -> confidence: ... -> position size: ...`

---

## Assessment Mapping

This implementation covers the internship scope as follows:

- **Language: Python** -> complete backend in Python
- **Hermes agent framework** -> dependency included + agent loop architecture
- **OpenRouter provider** -> integrated in prediction rationale path with model fallback
- **Apify scraping** -> integrated provider path for market discovery
- **Polymarket + Kalshi (BTC/ETH)** -> handled in search stage
- **1000 bars data fetch** -> Binance OHLCV fetch with configurable limit (default 1000)
- **Kronos prediction path** -> adapter + optional local repo integration
- **Kelly risk management** -> implemented in dedicated risk layer
- **Feedback loop** -> persistent settlement and rolling accuracy ledger
- **Logging/error handling** -> structured logs and non-breaking fallbacks

---

## Demo Checklist (for submission video)

1. Show project root and `.env` (hide secret values)
2. Run `python main.py`
3. Show all 5 pipeline steps in logs
4. Show `--- Results ---` block
5. Open `data/feedback.json` and show settled rows + accuracy

---

## Security Notes

- Never commit `.env`
- Rotate tokens immediately if exposed
- Keep `.env.example` with placeholders only

---

## Submission Checklist

- Repository link (GitHub/GitLab)
- APIFY token used (as requested)
- Short working demo video
- Email to `gilad@crowdwisdomtrading.com`

