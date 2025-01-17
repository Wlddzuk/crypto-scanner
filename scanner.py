"""
Cryptocurrency Market Scanner

This script implements a web-based cryptocurrency market scanner that monitors various exchanges
for high-demand trading pairs. It analyzes volume and price movements to identify potentially
interesting trading opportunities.

Features:
- Multiple exchange support
- Technical indicators (RSI, MACD)
- Automatic refresh
- Interactive web interface
- Volume and return analysis
"""

from flask import Flask, render_template_string, jsonify, request
import pandas as pd
from datetime import datetime
import os
import ccxt
import time
from typing import Dict, List, Optional
import ta  # Technical Analysis library
import logging

# Configure logging for the application
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CryptoScanner:
    """
    A class to scan cryptocurrency markets for high-demand trading pairs.
    
    This scanner analyzes trading pairs across different exchanges, looking for
    unusual volume and price movements that might indicate trading opportunities.
    """

    def __init__(self, exchange_id='bybit', base_currencies=['USDT']):
        """
        Initialize the CryptoScanner with specified exchange and base currencies.
        
        Args:
            exchange_id (str): The ID of the exchange to use (default: 'bybit')
            base_currencies (list): List of base currencies to scan for (default: ['USDT'])
        """
        self.exchange = getattr(ccxt, exchange_id)()
        self.exchange.load_markets()
        self.base_currencies = base_currencies
        self.logger = logging.getLogger(__name__)

    def get_ohlcv_data(self, symbol: str, timeframe='1d', limit=30) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV (Open, High, Low, Close, Volume) data for a trading pair.
        
        Args:
            symbol (str): Trading pair symbol (e.g., 'BTC/USDT')
            timeframe (str): Time period for each candle (default: '1d')
            limit (int): Number of candles to fetch (default: 30)
        
        Returns:
            Optional[pd.DataFrame]: DataFrame with OHLCV data and technical indicators,
                                  or None if there was an error
        """
        try:
            # Add rate limiting to avoid API restrictions
            time.sleep(self.exchange.rateLimit / 1000)  # Convert to seconds
            
            # Fetch OHLCV data from exchange
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # Calculate technical indicators
            df['rsi'] = ta.momentum.RSIIndicator(df['close']).rsi()
            df['macd'] = ta.trend.MACD(df['close']).macd()
            
            return df
        except Exception as e:
            self.logger.error(f"Error fetching data for {symbol}: {str(e)}")
            return None

    def calculate_daily_returns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate daily returns for each trading pair.
        
        Args:
            df (pd.DataFrame): DataFrame with OHLCV data
        
        Returns:
            pd.DataFrame: DataFrame with added daily return column
        """
        df['daily_return'] = (df['close'] - df['open']) / df['open']
        return df

    def calculate_metrics(self, df: pd.DataFrame, lookback=20) -> Dict:
        """
        Calculate various metrics for analysis including volume, returns, and technical indicators.
        
        Args:
            df (pd.DataFrame): DataFrame with OHLCV and technical indicator data
            lookback (int): Number of periods to look back for calculations (default: 20)
        
        Returns:
            Dict: Dictionary containing calculated metrics
        """
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

    def scan_markets(self, volume_mult=2.0, return_mult=2.0, lookback=20) -> pd.DataFrame:
        """
        Scan all markets for high-demand trading pairs.
        
        Identifies pairs with unusually high volume and returns compared to their
        recent historical data.
        
        Args:
            volume_mult (float): Multiplier for volume threshold (default: 2.0)
            return_mult (float): Multiplier for return threshold (default: 2.0)
            lookback (int): Number of periods to look back (default: 20)
        
        Returns:
            pd.DataFrame: DataFrame containing identified high-demand pairs
        """
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

            # Avoid division by zero with minimum thresholds
            volume_std = max(metrics['volume']['std'], metrics['volume']['mean'] * 0.01)
            return_std = max(metrics['return']['std'], abs(metrics['return']['mean']) * 0.01)

            volume_threshold = metrics['volume']['mean'] + volume_mult * volume_std
            return_threshold = metrics['return']['mean'] + return_mult * return_std

            # Check if the pair meets our criteria
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

# Initialize Flask application
app = Flask(__name__)

@app.route('/exchanges')
def get_exchanges():
    """
    Endpoint to get list of supported exchanges.
    
    Returns:
        JSON: List of supported cryptocurrency exchanges
    """
    # List of popular exchanges supported by ccxt
    exchanges = [
        'binance', 'bybit', 'kucoin', 'okx', 'huobi', 'kraken', 
        'bitfinex', 'gate', 'mexc', 'bitget'
    ]
    return jsonify(exchanges)

@app.route('/scan')
def scan():
    """
    Endpoint to perform market scan with specified exchange.
    
    Returns:
        JSON: Scan results or error message
    """
    try:
        exchange = request.args.get('exchange', 'bybit')  # Get exchange from query parameters
        scanner = CryptoScanner(exchange_id=exchange)
        results_df = scanner.scan_markets(volume_mult=2.0, return_mult=2.0, lookback=20)
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
            // Load available exchanges from the server
            async function loadExchanges() {
                try {
                    const response = await fetch('/exchanges');
                    const exchanges = await response.json();
                    const select = document.getElementById('exchangeSelect');
                    
                    // Populate exchange dropdown with available exchanges
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

            // Update the results table with new data
            function updateTable(data) {
                const tbody = document.querySelector('#resultsTable tbody');
                tbody.innerHTML = '';
                
                // Show message if no results found
                if (data.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="8" class="text-center">No cryptocurrencies meeting the criteria found.</td></tr>';
                    return;
                }
                
                // Create table rows for each result
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
                
                // Update last refresh timestamp
                document.getElementById('lastUpdate').textContent = 
                    `Last updated: ${new Date().toLocaleString()}`;
            }
            
            // Fetch and update market data
            async function refreshData() {
                const loading = document.getElementById('loading');
                const results = document.getElementById('results');
                const refreshButton = document.getElementById('refresh');
                const exchangeSelect = document.getElementById('exchangeSelect');
                
                // Show loading state and disable controls
                loading.style.display = 'block';
                results.style.display = 'none';
                refreshButton.disabled = true;
                exchangeSelect.disabled = true;
                
                try {
                    // Fetch data for selected exchange
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
                    // Restore UI state
                    loading.style.display = 'none';
                    results.style.display = 'block';
                    refreshButton.disabled = false;
                    exchangeSelect.disabled = false;
                }
            }
            
            // Initialize the page
            loadExchanges();
            
            // Set up event listeners
            document.getElementById('refresh').addEventListener('click', refreshData);
            document.getElementById('exchangeSelect').addEventListener('change', refreshData);
            
            // Initial data load
            refreshData();
            
            // Set up automatic refresh every 15 minutes
            setInterval(refreshData, 15 * 60 * 1000);
        </script>
    </body>
    </html>
    """

    return render_template_string(html)

if __name__ == '__main__':
    app.run(debug=True)
