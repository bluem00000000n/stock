-- SIGNAL FORGE ALERT SQLite Schema (v2.0)

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id TEXT UNIQUE NOT NULL,
    asset_type TEXT NOT NULL CHECK(asset_type IN ('COIN', 'STOCK_KR', 'STOCK_US')),
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL CHECK(direction IN ('LONG', 'SHORT')),
    strategy_id TEXT NOT NULL,
    strategy_name TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    price REAL NOT NULL,
    trigger_reason TEXT NOT NULL,
    indicators_json TEXT,
    source_url TEXT NOT NULL,
    score REAL DEFAULT 50.0,
    tier TEXT NOT NULL DEFAULT 'WATCH',
    invalidation_condition TEXT,
    first_detected_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('NEW', 'ALERTED', 'SKIPPED_DEDUP', 'FAILED', 'INVALIDATED')),
    is_mock INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_signals_dedup 
ON signals (symbol, strategy_id, direction, created_at);

CREATE INDEX IF NOT EXISTS idx_signals_created 
ON signals (created_at DESC);

CREATE TABLE IF NOT EXISTS alert_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'TELEGRAM',
    status TEXT NOT NULL CHECK(status IN ('SUCCESS', 'FAILED', 'MOCK')),
    response_msg TEXT,
    sent_at TEXT NOT NULL,
    FOREIGN KEY(signal_id) REFERENCES signals(signal_id)
);

CREATE INDEX IF NOT EXISTS idx_alert_history_signal 
ON alert_history (signal_id);

CREATE TABLE IF NOT EXISTS market_data_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    candle_timestamp INTEGER NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    source TEXT NOT NULL,
    UNIQUE(symbol, timeframe, candle_timestamp)
);

CREATE INDEX IF NOT EXISTS idx_candle_lookup 
ON market_data_cache (symbol, timeframe, candle_timestamp DESC);

CREATE TABLE IF NOT EXISTS community_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_platform TEXT NOT NULL,
    channel_name TEXT NOT NULL,
    post_id TEXT NOT NULL,
    post_url TEXT NOT NULL,
    author TEXT,
    raw_text TEXT NOT NULL,
    published_at TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    content_hash TEXT UNIQUE NOT NULL,
    mentioned_symbols TEXT,
    has_7d_surge_claim INTEGER DEFAULT 0,
    claimed_direction TEXT DEFAULT 'LONG',
    claimed_target_price REAL,
    is_promotional_scam INTEGER DEFAULT 0,
    sentiment_score REAL DEFAULT 0.0
);

CREATE INDEX IF NOT EXISTS idx_community_posts_collected 
ON community_posts (collected_at DESC);

CREATE TABLE IF NOT EXISTS signal_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id TEXT NOT NULL,
    evaluation_timeframe TEXT NOT NULL, -- e.g. "1h", "24h", "3d", "7d", "20d"
    entry_price REAL NOT NULL,
    evaluated_price REAL NOT NULL,
    return_pct REAL NOT NULL,
    max_favorable_excursion_pct REAL NOT NULL,
    max_adverse_excursion_pct REAL NOT NULL,
    hit_target INTEGER NOT NULL DEFAULT 0,
    evaluated_at TEXT NOT NULL,
    FOREIGN KEY(signal_id) REFERENCES signals(signal_id)
);

CREATE INDEX IF NOT EXISTS idx_signal_outcomes_signal 
ON signal_outcomes (signal_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_signal_outcomes_unique 
ON signal_outcomes (signal_id, evaluation_timeframe);

CREATE TABLE IF NOT EXISTS execution_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('SUCCESS', 'FAILURE', 'WARNING')),
    message TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_execution_logs_task 
ON execution_logs (task_name, created_at DESC);

-- ====================================================================
-- Live Compounding Paper Trading Tables (100만원 시작, Ultra Mode)
-- ====================================================================

CREATE TABLE IF NOT EXISTS compounding_portfolio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mode TEXT NOT NULL DEFAULT 'ULTRA', -- 'ULTRA', 'AGGRESSIVE', 'CONSERVATIVE'
    initial_capital_krw REAL NOT NULL DEFAULT 1000000.0,
    current_cash_krw REAL NOT NULL DEFAULT 1000000.0,
    equity_krw REAL NOT NULL DEFAULT 1000000.0,
    peak_equity_krw REAL NOT NULL DEFAULT 1000000.0,
    max_drawdown_pct REAL NOT NULL DEFAULT 0.0,
    total_trades INTEGER NOT NULL DEFAULT 0,
    winning_trades INTEGER NOT NULL DEFAULT 0,
    losing_trades INTEGER NOT NULL DEFAULT 0,
    total_net_pnl_krw REAL NOT NULL DEFAULT 0.0,
    total_fee_krw REAL NOT NULL DEFAULT 0.0,
    started_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS compounding_positions (
    position_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    asset_type TEXT NOT NULL CHECK(asset_type IN ('COIN', 'STOCK_KR', 'STOCK_US')),
    direction TEXT NOT NULL CHECK(direction IN ('LONG', 'SHORT')),
    strategy_id TEXT NOT NULL,
    strategy_name TEXT NOT NULL,
    signal_id TEXT,
    entry_price REAL NOT NULL,
    current_price REAL NOT NULL,
    quantity REAL NOT NULL,
    invested_krw REAL NOT NULL,
    stop_loss_price REAL NOT NULL,
    target_price REAL NOT NULL,
    trailing_stop_price REAL,
    highest_price REAL NOT NULL,
    lowest_price REAL NOT NULL,
    unrealized_pnl_pct REAL DEFAULT 0.0,
    unrealized_pnl_krw REAL DEFAULT 0.0,
    status TEXT NOT NULL CHECK(status IN ('OPEN', 'CLOSED')),
    entry_time TEXT NOT NULL,
    exit_time TEXT,
    exit_price REAL,
    exit_reason TEXT,
    realized_pnl_krw REAL,
    realized_pnl_pct REAL,
    fee_krw REAL DEFAULT 0.0
);

CREATE INDEX IF NOT EXISTS idx_compounding_positions_status
ON compounding_positions (status, entry_time DESC);

CREATE TABLE IF NOT EXISTS compounding_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_num INTEGER NOT NULL,
    position_id TEXT UNIQUE NOT NULL,
    symbol TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    direction TEXT NOT NULL,
    strategy_id TEXT NOT NULL,
    strategy_name TEXT NOT NULL,
    entry_time TEXT NOT NULL,
    exit_time TEXT NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL NOT NULL,
    quantity REAL NOT NULL,
    invested_krw REAL NOT NULL,
    exit_value_krw REAL NOT NULL,
    gross_pnl_pct REAL NOT NULL,
    fee_krw REAL NOT NULL,
    net_pnl_krw REAL NOT NULL,
    net_return_pct REAL NOT NULL,
    portfolio_ending_balance REAL NOT NULL,
    exit_reason TEXT NOT NULL,
    FOREIGN KEY(position_id) REFERENCES compounding_positions(position_id)
);

CREATE INDEX IF NOT EXISTS idx_compounding_trades_num
ON compounding_trades (trade_num ASC);

