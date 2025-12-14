# TokenBrain

AI-powered Solana token risk analyzer Telegram bot.

## Overview

TokenBrain analyzes Solana tokens and explains risks in simple terms.
Send a token address to the bot and get:

- **Risk Level**: HIGH / MEDIUM / LOW
- **Summary**: Brief explanation of the token
- **Reasons**: Why this risk level was assigned
- **Recommendation**: AVOID / CAUTION / OK

## Quick Start

### Prerequisites

- Python 3.11+
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)

### Local Setup

```bash
# Clone the repository
git clone <repository-url>
cd tokenBrain

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your TELEGRAM_BOT_TOKEN

# Run the bot
python -m bot.main
```

### Docker Setup

```bash
# Build image
docker build -t tokenbrain-bot .

# Run container
docker run --env-file .env tokenbrain-bot
```

## Configuration

All settings are in `.env` file:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | - | Bot token from @BotFather |
| `ENVIRONMENT` | No | development | development / production |
| `USE_MOCK_SERVICES` | No | true | Use mock APIs (no real data) |
| `LOG_LEVEL` | No | INFO | DEBUG / INFO / WARNING / ERROR |
| `API_TIMEOUT_SECONDS` | No | 10 | API request timeout |

For production with real APIs, also set:
- `HELIUS_API_KEY` - [Helius](https://helius.dev/) for on-chain token data
- `OPENROUTER_API_KEY` - [OpenRouter](https://openrouter.ai/) for LLM (Claude)
- `LLM_MODEL` - LLM model to use (default: `anthropic/claude-3.5-sonnet`)

## Project Structure

```
tokenBrain/
├── bot/
│   ├── config/          # Settings management
│   ├── core/            # Models, protocols, exceptions
│   ├── services/        # Business logic
│   │   ├── token_data/  # Data fetching
│   │   ├── risk/        # Risk calculation
│   │   └── explain/     # LLM explanations
│   ├── handlers/        # Telegram handlers
│   ├── middleware/      # Error handling, logging
│   ├── templates/       # Message templates
│   └── utils/           # Validators, formatters
├── tests/               # Pytest tests
├── Dockerfile
├── requirements.txt
└── README.md
```

## Architecture

The bot follows **Clean Architecture** principles:

1. **TokenDataAggregator** - Fetches token data from providers
2. **RiskService** - Calculates risk level using heuristics
3. **ExplainService** - Generates explanations via LLM
4. **AnalyzerOrchestrator** - Coordinates the flow

### Risk Calculation Rules

| Risk | Conditions |
|------|------------|
| HIGH | Liquidity < $20k OR Age < 7 days OR Top10 > 60% OR Mint authority exists OR Freeze authority exists OR Top1 holder > 50% |
| MEDIUM | Liquidity 20k-80k OR Age 7-30 days |
| LOW | Liquidity > $80k AND Age > 30 days AND Top10 <= 60% AND No mint/freeze authority |

**Note**: Unknown values (liquidity, age) don't trigger HIGH risk automatically.

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=bot --cov-report=html

# Run specific test file
pytest tests/test_validators.py -v
```

## Development

### Adding a New Data Provider

1. Create class in `bot/services/token_data/`
2. Implement `TokenDataProvider` protocol
3. Update `ServiceFactory` to use it

### Adding a New LLM Provider

1. Create class in `bot/services/explain/`
2. Implement `LLMProvider` protocol
3. Update `ServiceFactory` to use it

## Disclaimer

TokenBrain does not provide financial advice.
Always do your own research before investing.

## License

MIT
