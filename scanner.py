from flask import Flask, render_template_string, jsonify, request
import pandas as pd
from datetime import datetime
import os
import ccxt
import time
from typing import Dict, List, Optional
import ta
import logging
import telebot
import os



# Configure logging for the application
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Telegram bot


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

class CryptoScanner:
    def __init__(self, exchange_id='bybit', base_currencies=['USDT']):
        self.exchange = getattr(ccxt, exchange_id)()
        self.exchange.load_markets()
        self.base_currencies = base_currencies
        self.logger = logging.getLogger(__name__)

    def get_ohlcv_data(self, symbol: str, timeframe='1d', limit=30) -> Optional[pd.DataFrame]:
        try:
            time.sleep(self.exchange.rateLimit / 1000)
            
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            df['rsi'] = ta.momentum.RSIIndicator(df['close']).rsi()
            df['macd'] = ta.trend.MACD(df['close']).macd()
            
            return df
        except Exception as e:
            self.logger.error(f"Error fetching data for {symbol}: {str(e)}")
            return None

    def calculate_daily_returns(self, df: pd.DataFrame) -> pd.DataFrame:
        df['daily_return'] = (df['close'] - df['open']) / df['open']
        return df

    def calculate_metrics(self, df: pd.DataFrame, lookback=20) -> Dict:
        recent_data = df.iloc[-(lookback+1):-1]
        
        metrics = {
            'volume': {
                'mean': recent_data['volume'].mean(),
                'std': recent_data['volume'].std()
            },
            'return': {
                'mean': recent_data['daily_return'].mean(),
                'std': recent_data['daily_return'].std()
            },
            'rsi': {
                'current': recent_data['rsi'].iloc[-1],
                'mean': recent_data['rsi'].mean()
            },
            'macd': {
                'current': recent_data['macd'].iloc[-1],
                'mean': recent_data['macd'].mean()
            }
        }
        
        return metrics

    def format_telegram_message(self, results_df: pd.DataFrame) -> str:
        if results_df.empty:
            return "No high-demand cryptocurrencies found."
        
        message = "🔍 High-Demand Cryptocurrencies:\n\n"
        for _, row in results_df.iterrows():
            message += f"📊 {row['Symbol']}\n"
            message += f"Volume: {row['Current Volume']:,.0f} (Norm: {row['Normal Volume']:,.0f})\n"
            message += f"Return: {row['Current Return (%)']}% (Norm: {row['Normal Return (%)']}%)\n"
            message += f"RSI: {row['RSI']} | MACD: {row['MACD']}\n"
            message += f"Time: {row['Timestamp']}\n\n"
        return message

    def send_telegram_update(self, results_df: pd.DataFrame):
        try:
            message = self.format_telegram_message(results_df)
            bot.send_message(TELEGRAM_CHAT_ID, message, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error sending Telegram message: {str(e)}")

    def scan_markets(self, volume_mult=2.0, return_mult=2.0, lookback=20) -> pd.DataFrame:
        high_demand_pairs = []

        for symbol in self.exchange.symbols:
            if not any(base in symbol for base in self.base_currencies):
                continue

            self.logger.info(f"Scanning {symbol}...")
            df = self.get_ohlcv_data(symbol, limit=lookback+10)
            if df is None or len(df) < (lookback + 1):
                continue

            df = self.calculate_daily_returns(df)
            metrics = self.calculate_metrics(df, lookback=lookback)

            current_volume = df.iloc[-1]['volume']
            current_return = df.iloc[-1]['daily_return']
            current_rsi = df.iloc[-1]['rsi']
            current_macd = df.iloc[-1]['macd']

            volume_std = max(metrics['volume']['std'], metrics['volume']['mean'] * 0.01)
            return_std = max(metrics['return']['std'], abs(metrics['return']['mean']) * 0.01)

            volume_threshold = metrics['volume']['mean'] + volume_mult * volume_std
            return_threshold = metrics['return']['mean'] + return_mult * return_std

            if current_volume >= volume_threshold and current_return >= return_threshold:
                high_demand_pairs.append({
                    'Symbol': symbol,
                    'Current Volume': current_volume,
                    'Normal Volume': metrics['volume']['mean'],
                    'Current Return (%)': round(current_return * 100, 2),
                    'Normal Return (%)': round(metrics['return']['mean'] * 100, 2),
                    'RSI': round(current_rsi, 2),
                    'MACD': round(current_macd, 4),
                    'Timestamp': df.iloc[-1]['timestamp']
                })

        return pd.DataFrame(high_demand_pairs)

app = Flask(__name__)

@app.route('/exchanges')
def get_exchanges():
    exchanges = [
        'binance', 'bybit', 'kucoin', 'okx', 'huobi', 'kraken', 
        'bitfinex', 'gate', 'mexc', 'bitget'
    ]
    return jsonify(exchanges)

@app.route('/scan')
def scan():
    try:
        exchange = request.args.get('exchange', 'bybit')
        scanner = CryptoScanner(exchange_id=exchange)
        results_df = scanner.scan_markets(volume_mult=2.0, return_mult=2.0, lookback=20)
        
        # Send results to Telegram
        scanner.send_telegram_update(results_df)
        
        return jsonify(results_df.to_dict('records'))
    except Exception as e:
        logger.error(f"Error during scan: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/')
def index():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" 
              href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha3/dist/css/bootstrap.min.css">
        <title>Crypto Scanner Results</title>
        <style>
            body {
                padding: 20px;
                background-color: #f9f9f9;
            }
            .container {
                margin-top: 30px;
                background: white;
                border-radius: 10px;
                box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
                padding: 20px;
            }
            h1 {
                text-align: center;
                margin-bottom: 20px;
            }
            .loading {
                display: none;
                text-align: center;
                margin: 20px 0;
            }
            #controls {
                margin-bottom: 20px;
            }
            .table th {
                cursor: pointer;
            }
            #exchangeSelect {
                max-width: 200px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>High-Demand Cryptocurrencies</h1>
            
            <div id="controls" class="row align-items-center">
                <div class="col-md-4">
                    <div class="input-group">
                        <label class="input-group-text" for="exchangeSelect">Exchange:</label>
                        <select class="form-select" id="exchangeSelect">
                            <option value="" disabled>Loading exchanges...</option>
                        </select>
                    </div>
                </div>
                <div class="col-md-4">
                    <button id="refresh" class="btn btn-primary">
                        Refresh Data
                    </button>
                </div>
                <div class="col-md-4">
                    <span id="lastUpdate" class="text-muted"></span>
                </div>
            </div>
            
            <div id="loading" class="loading">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p>Scanning markets...</p>
            </div>
            
            <div id="results">
                <table id="resultsTable" class="table table-bordered table-hover">
                    <thead>
                        <tr>
                            <th>Symbol</th>
                            <th>Current Volume</th>
                            <th>Normal Volume</th>
                            <th>Current Return (%)</th>
                            <th>Normal Return (%)</th>
                            <th>RSI</th>
                            <th>MACD</th>
                            <th>Timestamp</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>
        
        <script>
            async function loadExchanges() {
                try {
                    const response = await fetch('/exchanges');
                    const exchanges = await response.json();
                    const select = document.getElementById('exchangeSelect');
                    
                    select.innerHTML = exchanges.map(exchange => 
                        `<option value="${exchange}" ${exchange === 'bybit' ? 'selected' : ''}>
                            ${exchange.toUpperCase()}
                        </option>`
                    ).join('');
                } catch (error) {
                    console.error('Error loading exchanges:', error);
                    alert('Error loading exchanges. Please refresh the page.');
                }
            }

            function updateTable(data) {
                const tbody = document.querySelector('#resultsTable tbody');
                tbody.innerHTML = '';
                
                if (data.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="8" class="text-center">No cryptocurrencies meeting the criteria found.</td></tr>';
                    return;
                }
                
                data.forEach(row => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td>${row.Symbol}</td>
                        <td>${row['Current Volume'].toLocaleString()}</td>
                        <td>${row['Normal Volume'].toLocaleString()}</td>
                        <td>${row['Current Return (%)']}</td>
                        <td>${row['Normal Return (%)']}</td>
                        <td>${row.RSI}</td>
                        <td>${row.MACD}</td>
                        <td>${new Date(row.Timestamp).toLocaleString()}</td>
                    `;
                    tbody.appendChild(tr);
                });
                
                document.getElementById('lastUpdate').textContent = 
                    `Last updated: ${new Date().toLocaleString()}`;
            }
            
            async function refreshData() {
                const loading = document.getElementById('loading');
                const results = document.getElementById('results');
                const refreshButton = document.getElementById('refresh');
                const exchangeSelect = document.getElementById('exchangeSelect');
                
                loading.style.display = 'block';
                results.style.display = 'none';
                refreshButton.disabled = true;
                exchangeSelect.disabled = true;
                
                try {
                    const exchange = exchangeSelect.value;
                    const response = await fetch(`/scan?exchange=${exchange}`);
                    const data = await response.json();
                    
                    if (response.ok) {
                        updateTable(data);
                    } else {
                        alert('Error fetching data: ' + data.error);
                    }
                } catch (error) {
                    alert('Error: ' + error.message);
                } finally {
                    loading.style.display = 'none';
                    results.style.display = 'block';
                    refreshButton.disabled = false;
                    exchangeSelect.disabled = false;
                }
            }
            
            loadExchanges();
            document.getElementById('refresh').addEventListener('click', refreshData);
            document.getElementById('exchangeSelect').addEventListener('change', refreshData);
            refreshData();
            setInterval(refreshData, 15 * 60 * 1000);
        </script>
    </body>
    </html>
    """

    return render_template_string(html)

if __name__ == '__main__':
    app.run(debug=True)