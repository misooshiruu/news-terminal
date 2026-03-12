// Ticker full name lookup for hover tooltips
const TICKER_NAMES = {
    // Broad market
    'SPY': 'S&P 500 ETF',
    'SPX': 'S&P 500 Index',
    'QQQ': 'Nasdaq 100 ETF',
    'DIA': 'Dow Jones ETF',
    'IWM': 'Russell 2000 ETF',
    'VTI': 'Total Stock Market ETF',

    // Volatility
    'VIX': 'CBOE Volatility Index',
    'UVXY': 'Ultra VIX Short-Term ETF',

    // Commodities
    'CL': 'Crude Oil Futures',
    'GC': 'Gold Futures',
    'SI': 'Silver Futures',
    'NG': 'Natural Gas Futures',
    'HG': 'Copper Futures',
    'PL': 'Platinum Futures',
    'ZW': 'Wheat Futures',
    'ZC': 'Corn Futures',
    'ZS': 'Soybean Futures',

    // Currencies
    'DX': 'US Dollar Index',
    'DXY': 'US Dollar Index',
    'EURUSD': 'Euro / US Dollar',
    'USDJPY': 'US Dollar / Japanese Yen',
    'GBPUSD': 'British Pound / US Dollar',
    'USDCNH': 'US Dollar / Chinese Yuan',

    // Bonds / Rates
    'TLT': '20+ Year Treasury ETF',
    'TBT': 'Short 20+ Year Treasuries',
    'HYG': 'High Yield Corporate Bond ETF',
    'LQD': 'Investment Grade Bond ETF',
    'ZB': 'Treasury Bond Futures',
    'ZN': '10-Year Treasury Note Futures',
    'SHY': '1-3 Year Treasury ETF',
    'IEF': '7-10 Year Treasury ETF',

    // Crypto
    'BTC': 'Bitcoin',
    'ETH': 'Ethereum',
    'SOL': 'Solana',

    // Sector ETFs
    'XLE': 'Energy Sector ETF',
    'XLF': 'Financial Sector ETF',
    'XLK': 'Technology Sector ETF',
    'XLV': 'Healthcare Sector ETF',
    'XLI': 'Industrial Sector ETF',
    'XLP': 'Consumer Staples ETF',
    'XLY': 'Consumer Discretionary ETF',
    'XLU': 'Utilities Sector ETF',
    'XLB': 'Materials Sector ETF',
    'XLRE': 'Real Estate Sector ETF',
    'XLC': 'Communication Services ETF',
    'SMH': 'Semiconductor ETF',
    'XOP': 'Oil & Gas Exploration ETF',
    'KRE': 'Regional Banking ETF',
    'XHB': 'Homebuilders ETF',
    'XRT': 'Retail ETF',
    'IBB': 'Biotech ETF',

    // Major stocks
    'AAPL': 'Apple',
    'MSFT': 'Microsoft',
    'GOOGL': 'Alphabet (Google)',
    'AMZN': 'Amazon',
    'TSLA': 'Tesla',
    'NVDA': 'NVIDIA',
    'META': 'Meta Platforms',
    'NFLX': 'Netflix',
    'AMD': 'Advanced Micro Devices',
    'INTC': 'Intel',

    // Financials
    'JPM': 'JPMorgan Chase',
    'BAC': 'Bank of America',
    'GS': 'Goldman Sachs',
    'MS': 'Morgan Stanley',
    'C': 'Citigroup',
    'WFC': 'Wells Fargo',

    // Consumer
    'WMT': 'Walmart',
    'COST': 'Costco',
    'TGT': 'Target',

    // Airlines
    'UAL': 'United Airlines',
    'DAL': 'Delta Air Lines',
    'AAL': 'American Airlines',
    'LUV': 'Southwest Airlines',
    'JETS': 'Airlines ETF',

    // Defense
    'LMT': 'Lockheed Martin',
    'RTX': 'RTX (Raytheon)',
    'NOC': 'Northrop Grumman',
    'GD': 'General Dynamics',
    'BA': 'Boeing',
    'ITA': 'Aerospace & Defense ETF',

    // Country / Region ETFs
    'EWZ': 'Brazil ETF',
    'FXI': 'China Large-Cap ETF',
    'EWJ': 'Japan ETF',
    'EFA': 'Developed International ETF',
    'EEM': 'Emerging Markets ETF',
    'EWY': 'South Korea ETF',
    'EWT': 'Taiwan ETF',
    'INDA': 'India ETF',
    'RSX': 'Russia ETF',
    'EIS': 'Israel ETF',

    // Energy
    'XOM': 'ExxonMobil',
    'CVX': 'Chevron',
    'OXY': 'Occidental Petroleum',
    'SLB': 'Schlumberger',
    'HAL': 'Halliburton',

    // Pharma / Health
    'JNJ': 'Johnson & Johnson',
    'PFE': 'Pfizer',
    'UNH': 'UnitedHealth',
    'LLY': 'Eli Lilly',
    'ABBV': 'AbbVie',

    // Agriculture / Food
    'DBA': 'Agriculture ETF',
    'MOO': 'Agribusiness ETF',
};
