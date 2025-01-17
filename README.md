# Crypto Market Scanner

A real-time cryptocurrency market scanner that monitors multiple exchanges for high-demand trading pairs. The scanner analyzes volume and price movements to identify potentially interesting trading opportunities.

## Features

- Multi-exchange support (Binance, Bybit, KuCoin, etc.)
- Technical indicators (RSI, MACD)
- Volume and return analysis
- Automatic refresh every 15 minutes
- Interactive web interface
- Real-time data updates
- Configurable exchange selection

## Technical Stack

- Python 3.x
- Flask (Web Framework)
- CCXT (Cryptocurrency Exchange Trading Library)
- Pandas (Data Analysis)
- TA-Lib (Technical Analysis)
- Bootstrap 5 (UI Framework)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/crypto-scanner.git
cd crypto-scanner
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Start the Flask application:
```bash
python scanner.py
```

2. Open your web browser and navigate to:
```
http://localhost:5000
```

3. Select your preferred exchange from the dropdown menu and wait for the data to load.

## Features

- **Exchange Selection**: Choose from multiple popular cryptocurrency exchanges
- **Auto-Refresh**: Data automatically refreshes every 15 minutes
- **Manual Refresh**: Use the refresh button to update data on demand
- **Technical Indicators**: 
  - RSI (Relative Strength Index)
  - MACD (Moving Average Convergence Divergence)
- **Volume Analysis**: Compare current volume with historical averages
- **Return Analysis**: Analyze price movements and returns

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
