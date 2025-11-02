//+------------------------------------------------------------------+
//|                                              FiveMinScalper.mq5 |
//|                                  5-Minute Scalping Strategy EA |
//|                                Based on 4-Hour Candle Breakouts |
//+------------------------------------------------------------------+
#property copyright "FiveMinScalper"
#property link      ""
#property version   "1.00"
#property strict

//--- Input Parameters
input group "=== Strategy Settings ==="
input double   EntryOffsetPercent = 0.01;      // Entry offset from 4H high/low (%)
input double   StopLossOffsetPercent = 0.02;   // Stop-loss offset from 4H high/low (%)
input double   RiskRewardRatio = 2.0;          // Risk to Reward Ratio (1:X)

input group "=== Risk Management ==="
input double   RiskPercentPerTrade = 1.0;      // Risk per trade (% of balance)
input double   MaxLotSize = 10.0;              // Maximum lot size
input double   MinLotSize = 0.01;              // Minimum lot size

input group "=== Trailing Stop ==="
input bool     UseTrailingStop = false;        // Enable trailing stop
input double   TrailingStopTriggerRR = 1.5;    // Activate trailing at R:R ratio
input double   TrailingStopDistance = 50.0;    // Trailing stop distance (points)

input group "=== Trading Hours ==="
input bool     UseTradingHours = false;        // Enable trading hours filter
input int      StartHour = 0;                  // Trading start hour
input int      EndHour = 23;                   // Trading end hour

input group "=== Advanced Settings ==="
input bool     UseBreakeven = true;            // Move SL to breakeven
input double   BreakevenTriggerRR = 1.0;       // Trigger breakeven at RR ratio
input bool     UseOnly00UTCCandle = true;      // Use only first 4H candle of day (chart shows 04:00)
input int      MagicNumber = 123456;           // Magic number for orders
input string   TradeComment = "5MinScalper";   // Trade comment

input group "=== Logging Settings ==="
input bool     EnableDetailedLogging = true;   // Enable detailed logging
input bool     LogToFile = true;               // Write logs to file
input bool     LogToConsole = true;            // Print logs to console
input bool     ExportCandleData = false;       // Export candle data to CSV for verification

input group "=== Debug Settings ==="
input bool     LogActiveTradesEvery5Min = true; // Log all active trades every 5-min candle

input group "=== Symbol-Specific Optimization ==="
input bool     UseSymbolSpecificSettings = true; // Auto-adjust parameters based on symbol
input string   ManualSymbolCategory = "AUTO";    // Manual override: AUTO, MAJOR_FOREX, MINOR_FOREX, METALS, INDICES, CRYPTO

input group "=== Adaptive Filter System ==="
input bool     UseAdaptiveFilters = true;       // Enable adaptive filter system
input int      AdaptiveLossTrigger = 3;         // Consecutive losses to activate filters (auto-adjusted per symbol)
input int      AdaptiveWinRecovery = 2;         // Consecutive wins to deactivate filters (auto-adjusted per symbol)
input bool     StartWithFiltersEnabled = false; // Start with filters enabled (true) or disabled (false)

input group "=== Volume Confirmation ==="
input double   BreakoutVolumeMaxMultiplier = 1.0; // Max volume for initial breakout (weak breakout = good)
input double   ReversalVolumeMinMultiplier = 1.5; // Min volume for reversal (strong reversal = good)
input int      VolumeAveragePeriod = 20;        // Period for volume moving average

input group "=== Divergence Confirmation ==="
input bool     RequireBothIndicators = false;   // Require BOTH RSI and MACD divergence (stricter)
input int      RSI_Period = 14;                 // RSI period
input int      MACD_Fast = 12;                  // MACD fast EMA period
input int      MACD_Slow = 26;                  // MACD slow EMA period
input int      MACD_Signal = 9;                 // MACD signal period
input int      DivergenceLookback = 20;         // Candles to look back for swing points

input group "=== Visual Settings ==="
input bool     ShowLevelsOnChart = true;       // Draw levels on chart
input color    Color4HHigh = clrDodgerBlue;    // 4H High line color
input color    Color4HLow = clrDodgerBlue;     // 4H Low line color
input color    ColorBuyEntry = clrLime;        // Buy entry line color
input color    ColorSellEntry = clrRed;        // Sell entry line color
input int      LineWidth = 2;                  // Line width
input ENUM_LINE_STYLE LineStyle = STYLE_SOLID; // Line style

//+------------------------------------------------------------------+
//| Symbol Category Enumeration                                       |
//+------------------------------------------------------------------+
enum ENUM_SYMBOL_CATEGORY
{
   SYMBOL_MAJOR_FOREX,    // Major Forex Pairs (EUR/USD, GBP/USD, USD/JPY, etc.)
   SYMBOL_MINOR_FOREX,    // Minor Forex Pairs (EUR/GBP, AUD/NZD, etc.)
   SYMBOL_EXOTIC_FOREX,   // Exotic Forex Pairs (USD/TRY, EUR/ZAR, etc.)
   SYMBOL_METALS,         // Precious Metals (Gold, Silver, etc.)
   SYMBOL_INDICES,        // Stock Indices (S&P500, NASDAQ, DAX, etc.)
   SYMBOL_CRYPTO,         // Cryptocurrencies (BTC/USD, ETH/USD, etc.)
   SYMBOL_COMMODITIES,    // Commodities (Oil, Gas, etc.)
   SYMBOL_UNKNOWN         // Unknown/Unclassified
};

//+------------------------------------------------------------------+
//| Symbol-Specific Parameter Set                                     |
//+------------------------------------------------------------------+
struct SymbolParameters
{
   // Volume parameters
   double breakoutVolumeMax;      // Max volume multiplier for breakout
   double reversalVolumeMin;      // Min volume multiplier for reversal
   int    volumeAveragePeriod;    // Volume average period

   // Divergence parameters
   int    rsiPeriod;              // RSI period
   int    macdFast;               // MACD fast EMA
   int    macdSlow;               // MACD slow EMA
   int    macdSignal;             // MACD signal
   int    divergenceLookback;     // Divergence lookback period

   // Adaptive trigger parameters
   int    adaptiveLossTrigger;    // Losses to activate filters
   int    adaptiveWinRecovery;    // Wins to deactivate filters
};

//--- Global Variables
datetime g_last4HCandleTime = 0;               // Last processed 4H candle time (for trading)
datetime g_lastSeen4HCandleTime = 0;           // Last seen 4H candle time (including skipped ones)
datetime g_last5MinCandleTime = 0;             // Last processed 5-min candle time
datetime g_processed04CandleTime = 0;          // Opening time of first 4H candle of day (iTime returns open time, chart shows close time)
double   g_4HHigh = 0;                         // 4H candle high (SELL breakout level)
double   g_4HLow = 0;                          // 4H candle low (BUY breakout level)
bool     g_buyOrderPlaced = false;             // Buy order status
bool     g_sellOrderPlaced = false;            // Sell order status
int      g_logFileHandle = INVALID_HANDLE;     // Log file handle
datetime g_lastLogTime = 0;                    // Last log timestamp
bool     g_tradingAllowedToday = false;        // Trading allowed after new 4H candle processed

// False breakout tracking for BUY signal
bool     g_buyBreakoutConfirmed = false;       // 5min candle closed below 4H Low
bool     g_buyReversalConfirmed = false;       // 5min candle closed above 4H Low after breakout
datetime g_buyBreakoutCandleTime = 0;          // Time of the breakout candle

// False breakout tracking for SELL signal
bool     g_sellBreakoutConfirmed = false;      // 5min candle closed above 4H High
bool     g_sellReversalConfirmed = false;      // 5min candle closed below 4H High after breakout
datetime g_sellBreakoutCandleTime = 0;         // Time of the breakout candle

// Volume confirmation tracking
long     g_buyBreakoutVolume = 0;              // Volume of the BUY breakout candle (should be LOW)
long     g_buyReversalVolume = 0;              // Volume of the BUY reversal candle (should be HIGH)
long     g_sellBreakoutVolume = 0;             // Volume of the SELL breakout candle (should be LOW)
long     g_sellReversalVolume = 0;             // Volume of the SELL reversal candle (should be HIGH)
double   g_averageVolume = 0;                  // Average volume over reference period
bool     g_buyBreakoutVolumeOK = false;        // BUY breakout has LOW volume (weak = good)
bool     g_buyReversalVolumeOK = false;        // BUY reversal has HIGH volume (strong = good)
bool     g_sellBreakoutVolumeOK = false;       // SELL breakout has LOW volume (weak = good)
bool     g_sellReversalVolumeOK = false;       // SELL reversal has HIGH volume (strong = good)

// Divergence confirmation tracking
int      g_rsiHandle = INVALID_HANDLE;         // RSI indicator handle
int      g_macdHandle = INVALID_HANDLE;        // MACD indicator handle
bool     g_buyDivergenceOK = false;            // BUY breakout shows bullish divergence (weak momentum = good)
bool     g_sellDivergenceOK = false;           // SELL breakout shows bearish divergence (weak momentum = good)

// Adaptive filter system tracking
bool     g_adaptiveModeActive = false;         // Is adaptive mode currently active?
int      g_consecutiveLosses = 0;              // Current consecutive loss count
int      g_consecutiveWins = 0;                // Current consecutive win count (when adaptive mode is active)
bool     g_originalVolumeConfirmation = false; // Original/starting volume confirmation state
bool     g_originalDivergenceConfirmation = false; // Original/starting divergence confirmation state
ulong    g_lastClosedTicket = 0;               // Last closed trade ticket (to avoid double-counting)

// Working filter variables (can be modified by adaptive system)
bool     g_activeVolumeConfirmation = false;   // Current active volume confirmation setting
bool     g_activeDivergenceConfirmation = false; // Current active divergence confirmation setting

// Symbol-specific optimization
ENUM_SYMBOL_CATEGORY g_symbolCategory = SYMBOL_UNKNOWN; // Detected symbol category
SymbolParameters     g_symbolParams;           // Active symbol-specific parameters
SymbolParameters     g_defaultParams;          // Default parameters from inputs

// Breakeven tracking to prevent redundant checks
ulong    g_breakevenSetTickets[];              // Array of tickets that already have breakeven set

// Trailing stop tracking
ulong    g_trailingStopActiveTickets[];        // Array of tickets with trailing stop activated

// Cached symbol properties (initialized once in OnInit for performance)
double   g_symbolPoint = 0;                    // Symbol point size
int      g_symbolDigits = 0;                   // Symbol digits
double   g_symbolTickValue = 0;                // Symbol tick value
double   g_symbolMinLot = 0;                   // Minimum lot size
double   g_symbolMaxLot = 0;                   // Maximum lot size
double   g_symbolLotStep = 0;                  // Lot step size

// Chart object tracking for efficient management
string   g_chartObjects[];                     // Array of chart objects created by EA

//+------------------------------------------------------------------+
//| Position information structure for caching                       |
//+------------------------------------------------------------------+
struct PositionInfo
{
   ulong             ticket;
   ENUM_POSITION_TYPE type;
   double            volume;
   double            openPrice;
   double            currentPrice;
   double            sl;
   double            tp;
   double            profit;
   datetime          openTime;
   double            risk;
   double            currentPnL;
   double            currentRR;
};

//+------------------------------------------------------------------+
//| Helper function to get position info (reduces redundant queries) |
//+------------------------------------------------------------------+
bool GetPositionInfo(int index, PositionInfo &info)
{
   ulong ticket = PositionGetTicket(index);
   if(ticket <= 0)
      return false;

   if(PositionGetString(POSITION_SYMBOL) != _Symbol)
      return false;

   if(PositionGetInteger(POSITION_MAGIC) != MagicNumber)
      return false;

   // Fill structure with all position data in one go
   info.ticket = ticket;
   info.type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
   info.volume = PositionGetDouble(POSITION_VOLUME);
   info.openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
   info.sl = PositionGetDouble(POSITION_SL);
   info.tp = PositionGetDouble(POSITION_TP);
   info.profit = PositionGetDouble(POSITION_PROFIT);
   info.openTime = (datetime)PositionGetInteger(POSITION_TIME);

   // Calculate current price based on position type
   info.currentPrice = (info.type == POSITION_TYPE_BUY) ?
                       SymbolInfoDouble(_Symbol, SYMBOL_BID) :
                       SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   // Calculate risk and P&L
   info.risk = MathAbs(info.openPrice - info.sl);
   info.currentPnL = (info.type == POSITION_TYPE_BUY) ?
                     (info.currentPrice - info.openPrice) :
                     (info.openPrice - info.currentPrice);
   info.currentRR = (info.risk > 0) ? (info.currentPnL / info.risk) : 0;

   return true;
}

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   LogMessage("=== FiveMinScalper EA Initialized ===");
   LogMessage("Symbol: " + _Symbol);
   LogMessage("Timeframe: " + EnumToString(PERIOD_CURRENT));
   LogMessage("Entry Offset: " + DoubleToString(EntryOffsetPercent, 2) + "%");
   LogMessage("Stop-Loss Offset: " + DoubleToString(StopLossOffsetPercent, 2) + "%");
   LogMessage("Risk/Reward Ratio: 1:" + DoubleToString(RiskRewardRatio, 2));
   LogMessage("Risk Per Trade: " + DoubleToString(RiskPercentPerTrade, 2) + "%");
   LogMessage("Use Breakeven: " + (UseBreakeven ? "Yes" : "No"));
   if(UseBreakeven)
      LogMessage("Breakeven Trigger: " + DoubleToString(BreakevenTriggerRR, 2) + " R:R");
   LogMessage("Use Trailing Stop: " + (UseTrailingStop ? "Yes" : "No"));
   if(UseTrailingStop)
   {
      LogMessage("Trailing Stop Trigger: " + DoubleToString(TrailingStopTriggerRR, 2) + " R:R");
      LogMessage("Trailing Stop Distance: " + DoubleToString(TrailingStopDistance, 0) + " points");
   }
   LogMessage("Use Only First 4H Candle: " + (UseOnly00UTCCandle ? "Yes (chart shows 04:00, opens 00:00-closes 04:00 UTC)" : "No"));
   LogMessage("Trading Hours Filter: " + (UseTradingHours ? "Enabled" : "Disabled"));
   if(UseTradingHours)
   {
      LogMessage("Trading Hours: " + IntegerToString(StartHour) + ":00 - " + IntegerToString(EndHour) + ":00");
   }
   LogMessage("Magic Number: " + IntegerToString(MagicNumber));
   LogMessage("Account Balance: " + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2));
   LogMessage("Account Currency: " + AccountInfoString(ACCOUNT_CURRENCY));

   // Validate inputs
   if(RiskPercentPerTrade <= 0 || RiskPercentPerTrade > 100)
   {
      LogMessage("ERROR: Risk percent must be between 0 and 100");
      return(INIT_PARAMETERS_INCORRECT);
   }

   if(RiskRewardRatio <= 0)
   {
      LogMessage("ERROR: Risk/Reward ratio must be positive");
      return(INIT_PARAMETERS_INCORRECT);
   }

   // Cache symbol properties for performance optimization
   g_symbolPoint = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   g_symbolDigits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   g_symbolTickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   g_symbolMinLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   g_symbolMaxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   g_symbolLotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   LogMessage("Symbol properties cached:");
   LogMessage("  Point: " + DoubleToString(g_symbolPoint, _Digits));
   LogMessage("  Digits: " + IntegerToString(g_symbolDigits));
   LogMessage("  Tick Value: " + DoubleToString(g_symbolTickValue, 2));
   LogMessage("  Min Lot: " + DoubleToString(g_symbolMinLot, 2));
   LogMessage("  Max Lot: " + DoubleToString(g_symbolMaxLot, 2));
   LogMessage("  Lot Step: " + DoubleToString(g_symbolLotStep, 2));

   // Store default parameters from inputs
   g_defaultParams.breakoutVolumeMax = BreakoutVolumeMaxMultiplier;
   g_defaultParams.reversalVolumeMin = ReversalVolumeMinMultiplier;
   g_defaultParams.volumeAveragePeriod = VolumeAveragePeriod;
   g_defaultParams.rsiPeriod = RSI_Period;
   g_defaultParams.macdFast = MACD_Fast;
   g_defaultParams.macdSlow = MACD_Slow;
   g_defaultParams.macdSignal = MACD_Signal;
   g_defaultParams.divergenceLookback = DivergenceLookback;
   g_defaultParams.adaptiveLossTrigger = AdaptiveLossTrigger;
   g_defaultParams.adaptiveWinRecovery = AdaptiveWinRecovery;

   // Apply symbol-specific parameters (or use defaults if disabled)
   ApplySymbolParameters();

   // Use symbol-specific parameters if enabled, otherwise use defaults
   if(UseSymbolSpecificSettings)
   {
      // Symbol-specific parameters are now active in g_symbolParams
      LogMessage("Using symbol-specific optimized parameters");
   }
   else
   {
      // Copy default parameters to symbol parameters
      g_symbolParams = g_defaultParams;
      LogMessage("Using default input parameters (symbol-specific optimization disabled)");
   }

   // Initialize RSI and MACD indicators (always needed for adaptive system)
   // Use symbol-specific parameters for indicator initialization
   LogMessage("Initializing divergence indicators with symbol-specific parameters...");

   // Create RSI indicator on 5-minute timeframe using symbol-specific period
   g_rsiHandle = iRSI(_Symbol, PERIOD_M5, g_symbolParams.rsiPeriod, PRICE_CLOSE);
   if(g_rsiHandle == INVALID_HANDLE)
   {
      LogMessage("ERROR: Failed to create RSI indicator");
      return(INIT_FAILED);
   }

   // Create MACD indicator on 5-minute timeframe using symbol-specific parameters
   g_macdHandle = iMACD(_Symbol, PERIOD_M5, g_symbolParams.macdFast, g_symbolParams.macdSlow, g_symbolParams.macdSignal, PRICE_CLOSE);
   if(g_macdHandle == INVALID_HANDLE)
   {
      LogMessage("ERROR: Failed to create MACD indicator");
      return(INIT_FAILED);
   }

   LogMessage("Divergence indicators initialized successfully");
   LogMessage("  RSI Period: " + IntegerToString(g_symbolParams.rsiPeriod));
   LogMessage("  MACD: " + IntegerToString(g_symbolParams.macdFast) + ", " + IntegerToString(g_symbolParams.macdSlow) + ", " + IntegerToString(g_symbolParams.macdSignal));
   LogMessage("  Divergence Lookback: " + IntegerToString(g_symbolParams.divergenceLookback) + " candles");
   LogMessage("  Require Both Indicators: " + (RequireBothIndicators ? "Yes" : "No"));

   // Initialize filter settings for adaptive system
   // Store the starting state as the "original" state to restore to
   g_originalVolumeConfirmation = StartWithFiltersEnabled;
   g_originalDivergenceConfirmation = StartWithFiltersEnabled;
   g_activeVolumeConfirmation = StartWithFiltersEnabled;
   g_activeDivergenceConfirmation = StartWithFiltersEnabled;

   if(UseAdaptiveFilters)
   {
      LogMessage("Adaptive Filter System: ENABLED");
      LogMessage("  Loss Trigger: " + IntegerToString(g_symbolParams.adaptiveLossTrigger) + " consecutive losses (symbol-optimized)");
      LogMessage("  Win Recovery: " + IntegerToString(g_symbolParams.adaptiveWinRecovery) + " consecutive wins (symbol-optimized)");
      LogMessage("  Starting State: Filters " + (StartWithFiltersEnabled ? "ENABLED" : "DISABLED"));
      LogMessage("  When filters activate: Volume AND Divergence confirmation required");
      LogMessage("  When filters deactivate: Return to starting state (" + (StartWithFiltersEnabled ? "Enabled" : "Disabled") + ")");
   }
   else
   {
      LogMessage("Adaptive Filter System: DISABLED");
      LogMessage("  Filters permanently: " + (StartWithFiltersEnabled ? "ENABLED" : "DISABLED"));
   }

   LogMessage("Initialization successful - EA is ready to trade");

   // Initialize with current 4H candle on startup
   datetime current4HTime = iTime(_Symbol, PERIOD_H4, 0);
   if(current4HTime > 0)
   {
      int candleIndex = 1; // Start with last closed candle
      bool foundValidCandle = false;

      // If first 4H candle filter is enabled, search for it
      // NOTE: iTime() returns OPENING time. Chart displays CLOSING time.
      // First 4H candle: opens 00:00, closes 04:00 (chart shows 04:00)
      if(UseOnly00UTCCandle)
      {
         LogMessage("Searching for first 4H candle of day (opens 00:00, closes 04:00, chart shows 04:00)...");

         // Search backwards up to 24 hours (6 x 4H candles)
         for(int i = 1; i <= 6; i++)
         {
            datetime candleTime = iTime(_Symbol, PERIOD_H4, i);  // Returns opening time
            MqlDateTime timeStruct;
            TimeToStruct(candleTime, timeStruct);

            if(timeStruct.hour == 4)  // Opening time is 00:00 (chart displays 04:00 as closing time)
            {
               candleIndex = i;
               foundValidCandle = true;
               LogMessage("Found first 4H candle at index " + IntegerToString(i));
               LogMessage("Opening time (iTime): " + TimeToString(candleTime, TIME_DATE|TIME_MINUTES) + " UTC");
               LogMessage("Closing time (chart): 04:00 UTC");
               break;
            }
         }

         if(!foundValidCandle)
         {
            LogMessage("No first 4H candle found in last 24 hours - waiting for next one");
            LogMessage("EA will not trade until a valid 4H candle is processed");
         }
      }
      else
      {
         // No filter - use the last closed candle
         foundValidCandle = true;
         LogMessage("Processing last closed 4H candle (no time filter)...");
      }

      if(foundValidCandle)
      {
         // Initialize both tracking variables
         g_last4HCandleTime = current4HTime;
         g_lastSeen4HCandleTime = current4HTime;

         // Process the found candle
         g_4HHigh = iHigh(_Symbol, PERIOD_H4, candleIndex);
         g_4HLow = iLow(_Symbol, PERIOD_H4, candleIndex);
         double open = iOpen(_Symbol, PERIOD_H4, candleIndex);
         double close = iClose(_Symbol, PERIOD_H4, candleIndex);
         long volume4H = iVolume(_Symbol, PERIOD_H4, candleIndex);
         datetime closedCandleTime = iTime(_Symbol, PERIOD_H4, candleIndex);

         // Store opening time of first 4H candle (iTime returns opening time)
         if(UseOnly00UTCCandle)
         {
            g_processed04CandleTime = closedCandleTime;  // Stores opening time (00:00)
         }

         MqlDateTime timeStruct;
         TimeToStruct(closedCandleTime, timeStruct);

         double range = g_4HHigh - g_4HLow;
         string candleType = (close > open) ? "Bullish" : (close < open) ? "Bearish" : "Doji";

         LogMessage("========================================");
         LogMessage("=== 4H CANDLE ANALYSIS (STARTUP) ===");
         LogMessage("Closed at: " + TimeToString(closedCandleTime, TIME_DATE|TIME_MINUTES) + " UTC");
         LogMessage("Candle Type: " + candleType);
         LogMessage("Open: " + DoubleToString(open, _Digits));
         LogMessage("High: " + DoubleToString(g_4HHigh, _Digits));
         LogMessage("Low: " + DoubleToString(g_4HLow, _Digits));
         LogMessage("Close: " + DoubleToString(close, _Digits));
         LogMessage("Range: " + DoubleToString(range, _Digits) + " (" + DoubleToString(range / g_4HLow * 100, 2) + "%)");
         LogMessage("Volume: " + IntegerToString(volume4H));

         LogMessage("--- False Breakout Strategy ---");
         LogMessage("NOW USING 4H CANDLE: " + TimeToString(closedCandleTime, TIME_DATE|TIME_MINUTES) + " UTC");
         LogMessage("BUY Signal: Wait for 5min close BELOW " + DoubleToString(g_4HLow, _Digits) + ", then close ABOVE it");
         LogMessage("SELL Signal: Wait for 5min close ABOVE " + DoubleToString(g_4HHigh, _Digits) + ", then close BELOW it");

         // Reset order flags and breakout tracking
         g_buyOrderPlaced = false;
         g_sellOrderPlaced = false;
         g_buyBreakoutConfirmed = false;
         g_buyReversalConfirmed = false;
         g_buyBreakoutCandleTime = 0;
         g_sellBreakoutConfirmed = false;
         g_sellReversalConfirmed = false;
         g_sellBreakoutCandleTime = 0;

         // Reset volume tracking
         g_buyBreakoutVolume = 0;
         g_buyReversalVolume = 0;
         g_sellBreakoutVolume = 0;
         g_sellReversalVolume = 0;
         g_averageVolume = 0;
         g_buyBreakoutVolumeOK = false;
         g_buyReversalVolumeOK = false;
         g_sellBreakoutVolumeOK = false;
         g_sellReversalVolumeOK = false;
         g_buyDivergenceOK = false;
         g_sellDivergenceOK = false;

         // Check if we're in the restricted trading period (00:00-08:00 UTC)
         if(IsInCandleFormationPeriod())
         {
            g_tradingAllowedToday = false;
            LogMessage("TRADING SUSPENDED - EA started during restricted period (00:00-08:00 UTC)");
            LogMessage("Trading will begin at 08:00 UTC after both 4H candles have closed");
         }
         else
         {
            // Enable trading after processing new 4H candle
            g_tradingAllowedToday = true;
            LogMessage("TRADING ENABLED - New 4H candle processed on startup");
         }

         LogMessage("Order flags and breakout tracking reset - Ready to monitor for false breakout signals");

         // Draw levels on chart
         if(ShowLevelsOnChart)
         {
            DrawLevelsOnChart();
         }

         LogMessage("========================================");
      }
   }
   else
   {
      LogMessage("Waiting for 4H candle data...");
   }

   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   LogMessage("=== FiveMinScalper EA Stopped ===");
   LogMessage("Reason Code: " + IntegerToString(reason));

   string reasonText = "";
   switch(reason)
   {
      case REASON_PROGRAM: reasonText = "EA was stopped by user"; break;
      case REASON_REMOVE: reasonText = "EA was removed from chart"; break;
      case REASON_RECOMPILE: reasonText = "EA was recompiled"; break;
      case REASON_CHARTCHANGE: reasonText = "Chart symbol or period changed"; break;
      case REASON_CHARTCLOSE: reasonText = "Chart was closed"; break;
      case REASON_PARAMETERS: reasonText = "Input parameters changed"; break;
      case REASON_ACCOUNT: reasonText = "Account changed"; break;
      case REASON_TEMPLATE: reasonText = "Template changed"; break;
      case REASON_INITFAILED: reasonText = "Initialization failed"; break;
      case REASON_CLOSE: reasonText = "Terminal closing"; break;
      default: reasonText = "Unknown reason";
   }

   LogMessage("Reason: " + reasonText);
   LogMessage("Total open positions: " + IntegerToString(PositionsTotal()));

   // Release indicator handles
   if(g_rsiHandle != INVALID_HANDLE)
   {
      IndicatorRelease(g_rsiHandle);
      g_rsiHandle = INVALID_HANDLE;
   }

   if(g_macdHandle != INVALID_HANDLE)
   {
      IndicatorRelease(g_macdHandle);
      g_macdHandle = INVALID_HANDLE;
   }

   // Remove all chart objects created by this EA
   DeleteAllChartObjects();

   // Close log file if open
   if(g_logFileHandle != INVALID_HANDLE)
   {
      FileClose(g_logFileHandle);
      g_logFileHandle = INVALID_HANDLE;
   }
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Only run main logic when a new 5-minute candle has closed
   if(IsNew5MinCandle())
   {
      LogMessage("=== NEW 5-MIN CANDLE CLOSED ===");

      // Check if we've crossed midnight (00:00 UTC) - disable trading until new 4H candle
      MqlDateTime currentTime;
      TimeToStruct(TimeCurrent(), currentTime);

      static int lastDay = -1;

      // If it's a new day and we haven't processed a 4H candle yet today
      if(lastDay != -1 && currentTime.day != lastDay && g_tradingAllowedToday)
      {
         g_tradingAllowedToday = false;
         LogMessage("========================================");
         LogMessage("*** MIDNIGHT CROSSED - TRADING SUSPENDED ***");
         LogMessage("Current time: " + TimeToString(TimeCurrent(), TIME_DATE|TIME_MINUTES) + " UTC");
         LogMessage("Trading will resume after new 4H candle is processed");
         LogMessage("========================================");
      }

      lastDay = currentTime.day;

      // Check if new 4H candle has formed (only once per 5-min candle)
      if(IsNew4HCandle())
      {
         Process4HCandle();
      }

      // Verify we have valid 4H data (safety check - only when filter is enabled)
      if(UseOnly00UTCCandle && g_4HHigh > 0 && g_4HLow > 0 && g_processed04CandleTime > 0)
      {
         // Find the most recent 00:00 UTC candle
         datetime latest00Candle = Find00UTCCandle();

         // Only update if we found a newer 00:00 candle than what we're currently using
         if(latest00Candle > g_processed04CandleTime && latest00Candle > 0)
         {
            LogMessage("========================================");
            LogMessage("*** NEW 00:00 UTC CANDLE AVAILABLE ***");
            LogMessage("Currently using: " + TimeToString(g_processed04CandleTime, TIME_DATE|TIME_MINUTES) + " UTC");
            LogMessage("Latest available: " + TimeToString(latest00Candle, TIME_DATE|TIME_MINUTES) + " UTC");
            LogMessage("Updating to latest 00:00 UTC candle (closes at 04:00)...");

            // Find and update with the latest 00:00 candle
            int candleIndex = Find00UTCCandleIndex();
            if(candleIndex > 0)
            {
               g_last4HCandleTime = iTime(_Symbol, PERIOD_H4, 0);
               g_processed04CandleTime = latest00Candle;
               Update4HData(candleIndex);
            }
         }
      }

      // Check for entry signals
      MonitorEntries();

      // Clean up closed positions from breakeven tracking list
      CleanupClosedPositions();

      // Check for closed positions and update adaptive filter system
      CheckForClosedPositions();
   }

   // Manage open positions (only if breakeven or trailing stop is enabled and there are positions)
   // This runs on every tick for precise adjustments
   if((UseBreakeven || UseTrailingStop) && PositionsTotal() > 0)
   {
      ManageOpenPositions();
   }
}

//+------------------------------------------------------------------+
//| Check if a new 5-minute candle has formed                       |
//+------------------------------------------------------------------+
bool IsNew5MinCandle()
{
   datetime current5MinTime = iTime(_Symbol, PERIOD_M5, 0);

   if(current5MinTime != g_last5MinCandleTime)
   {
      if(g_last5MinCandleTime != 0)  // Skip the first call on initialization
      {
         if(EnableDetailedLogging)
         {
            LogMessage("New 5-min candle closed at: " + TimeToString(current5MinTime, TIME_DATE|TIME_MINUTES));
         }

         g_last5MinCandleTime = current5MinTime;
         return true;
      }
      else
      {
         // First initialization - just set the time
         g_last5MinCandleTime = current5MinTime;
         return false;
      }
   }

   return false;
}

//+------------------------------------------------------------------+
//| Check if a new 4-hour candle has formed                         |
//+------------------------------------------------------------------+
bool IsNew4HCandle()
{
   datetime current4HTime = iTime(_Symbol, PERIOD_H4, 0);

   // Check if we've seen a new 4H candle (different from last seen)
   if(current4HTime != g_lastSeen4HCandleTime && g_lastSeen4HCandleTime != 0)
   {
      datetime closedCandleTime = iTime(_Symbol, PERIOD_H4, 1);
      MqlDateTime timeStruct;
      TimeToStruct(closedCandleTime, timeStruct);

      LogMessage("=== NEW 4H CANDLE DETECTED ===");
      LogMessage("Closed candle time: " + TimeToString(closedCandleTime, TIME_DATE|TIME_MINUTES) + " UTC (Hour: " + IntegerToString(timeStruct.hour) + ")");
      LogMessage("Current candle time: " + TimeToString(current4HTime, TIME_DATE|TIME_MINUTES) + " UTC");
      LogMessage("Last seen time: " + TimeToString(g_lastSeen4HCandleTime, TIME_DATE|TIME_MINUTES) + " UTC");
      LogMessage("Last processed time: " + TimeToString(g_last4HCandleTime, TIME_DATE|TIME_MINUTES) + " UTC");

      // Update last seen time (even if we skip this candle)
      g_lastSeen4HCandleTime = current4HTime;

      // If filter is enabled, only process first 4H candle of day
      // NOTE: iTime() returns opening time (00:00), chart displays closing time (04:00)
      if(UseOnly00UTCCandle)
      {
         // Check if the closed candle opened at 00:00 UTC (first 4H candle)
         if(timeStruct.hour != 0)
         {
            LogMessage("SKIPPING: Candle opening hour is " + IntegerToString(timeStruct.hour) + ":00 UTC");
            LogMessage("Only processing first 4H candle (opens 00:00, chart shows 04:00)");
            LogMessage("Updated g_lastSeen4HCandleTime but NOT g_last4HCandleTime");
            return false;
         }
         else
         {
            LogMessage("PROCESSING: First 4H candle of day detected");
            LogMessage("Opening time: 00:00 UTC, Closing time: 04:00 UTC (shown on chart)");
         }
      }
      else
      {
         LogMessage("PROCESSING: No time filter - This candle will be processed");
      }

      return true;
   }

   return false;
}

//+------------------------------------------------------------------+
//| Process new 4-hour candle                                        |
//+------------------------------------------------------------------+
void Process4HCandle()
{
   // Get the closed 4H candle (index 1)
   g_4HHigh = iHigh(_Symbol, PERIOD_H4, 1);
   g_4HLow = iLow(_Symbol, PERIOD_H4, 1);
   double open = iOpen(_Symbol, PERIOD_H4, 1);
   double close = iClose(_Symbol, PERIOD_H4, 1);
   long volume4H = iVolume(_Symbol, PERIOD_H4, 1);
   g_last4HCandleTime = iTime(_Symbol, PERIOD_H4, 0);

   // Store the opening time of the first 4H candle we're using
   // NOTE: iTime() returns opening time (00:00), chart displays closing time (04:00)
   datetime closedCandleTime = iTime(_Symbol, PERIOD_H4, 1);
   if(UseOnly00UTCCandle)
   {
      g_processed04CandleTime = closedCandleTime;  // Stores opening time (00:00)
   }

   MqlDateTime timeStruct;
   TimeToStruct(closedCandleTime, timeStruct);

   double range = g_4HHigh - g_4HLow;
   string candleType = (close > open) ? "Bullish" : (close < open) ? "Bearish" : "Doji";

   LogMessage("========================================");
   LogMessage("=== 4H CANDLE ANALYSIS ===");
   LogMessage("Closed at: " + TimeToString(closedCandleTime, TIME_DATE|TIME_MINUTES) + " UTC");
   LogMessage("Candle Type: " + candleType);
   LogMessage("Open: " + DoubleToString(open, _Digits));
   LogMessage("High: " + DoubleToString(g_4HHigh, _Digits));
   LogMessage("Low: " + DoubleToString(g_4HLow, _Digits));
   LogMessage("Close: " + DoubleToString(close, _Digits));
   LogMessage("Range: " + DoubleToString(range, _Digits) + " (" + DoubleToString(range / g_4HLow * 100, 2) + "%)");
   LogMessage("Volume: " + IntegerToString(volume4H));

   LogMessage("--- False Breakout Strategy ---");
   LogMessage("NOW USING 4H CANDLE: " + TimeToString(closedCandleTime, TIME_DATE|TIME_MINUTES) + " UTC");
   LogMessage("BUY Signal: Wait for 5min close BELOW " + DoubleToString(g_4HLow, _Digits) + ", then close ABOVE it");
   LogMessage("SELL Signal: Wait for 5min close ABOVE " + DoubleToString(g_4HHigh, _Digits) + ", then close BELOW it");

   // Reset order flags and breakout tracking
   g_buyOrderPlaced = false;
   g_sellOrderPlaced = false;
   g_buyBreakoutConfirmed = false;
   g_buyReversalConfirmed = false;
   g_buyBreakoutCandleTime = 0;
   g_sellBreakoutConfirmed = false;
   g_sellReversalConfirmed = false;
   g_sellBreakoutCandleTime = 0;

   // Reset volume tracking
   g_buyBreakoutVolume = 0;
   g_buyReversalVolume = 0;
   g_sellBreakoutVolume = 0;
   g_sellReversalVolume = 0;
   g_averageVolume = 0;
   g_buyBreakoutVolumeOK = false;
   g_buyReversalVolumeOK = false;
   g_sellBreakoutVolumeOK = false;
   g_sellReversalVolumeOK = false;
   g_buyDivergenceOK = false;
   g_sellDivergenceOK = false;

   // Check if we're in the restricted trading period (00:00-08:00 UTC)
   if(IsInCandleFormationPeriod())
   {
      g_tradingAllowedToday = false;
      LogMessage("TRADING SUSPENDED - Restricted trading period (00:00-08:00 UTC)");
      LogMessage("Trading will resume at 08:00 UTC after both 4H candles have closed");
   }
   else
   {
      // Enable trading after processing new 4H candle
      g_tradingAllowedToday = true;
      LogMessage("TRADING ENABLED - New 4H candle processed and closed");
   }

   LogMessage("Order flags and breakout tracking reset - Ready to monitor for entries");

   // Clear tracking lists for new trading day
   ClearBreakevenList();
   ClearTrailingStopList();

   // Draw levels on chart
   if(ShowLevelsOnChart)
   {
      DrawLevelsOnChart();
   }

   LogMessage("========================================");
}

//+------------------------------------------------------------------+
//| Monitor entry levels and execute trades                          |
//+------------------------------------------------------------------+
void MonitorEntries()
{
   // Skip if no 4H candle has been processed yet
   if(g_last4HCandleTime == 0 || g_4HHigh == 0 || g_4HLow == 0)
   {
      if(EnableDetailedLogging)
         LogMessage("MonitorEntries: Waiting for 4H candle data");
      return;
   }

   // Check if we're in the restricted trading period (00:00-08:00 UTC)
   if(IsInCandleFormationPeriod())
   {
      if(EnableDetailedLogging)
         LogMessage("MonitorEntries: Trading suspended - Restricted period (00:00-08:00 UTC)");
      return;
   }

   // Check if we've passed midnight and need a new 4H candle
   if(!g_tradingAllowedToday)
   {
      LogMessage("MonitorEntries: Trading suspended - waiting for new 4H candle after midnight");
      return;
   }

   // Check trading hours
   if(UseTradingHours && !IsWithinTradingHours())
   {
      if(EnableDetailedLogging)
         LogMessage("MonitorEntries: Outside trading hours - skipping");
      return;
   }

   // Get the CLOSED 5-minute candle (index 1)
   double candle5mClose = iClose(_Symbol, PERIOD_M5, 1);
   double candle5mHigh = iHigh(_Symbol, PERIOD_M5, 1);
   double candle5mLow = iLow(_Symbol, PERIOD_M5, 1);
   double candle5mOpen = iOpen(_Symbol, PERIOD_M5, 1);
   datetime candle5mTime = iTime(_Symbol, PERIOD_M5, 1);

   // Enhanced logging to debug candle data
   if(EnableDetailedLogging)
   {
      LogMessage("=== ANALYZING CLOSED CANDLE (Index 1) ===");
      LogMessage("Candle Time: " + TimeToString(candle5mTime, TIME_DATE|TIME_MINUTES));
      LogMessage("Open: " + DoubleToString(candle5mOpen, _Digits));
      LogMessage("High: " + DoubleToString(candle5mHigh, _Digits));
      LogMessage("Low: " + DoubleToString(candle5mLow, _Digits));
      LogMessage("Close: " + DoubleToString(candle5mClose, _Digits));
      LogMessage("4H High: " + DoubleToString(g_4HHigh, _Digits) + " | 4H Low: " + DoubleToString(g_4HLow, _Digits));

      // Show comparison
      if(candle5mClose < g_4HLow)
         LogMessage(">>> Candle closed BELOW 4H Low (Potential BUY breakout)");
      else if(candle5mClose > g_4HHigh)
         LogMessage(">>> Candle closed ABOVE 4H High (Potential SELL breakout)");
      else
         LogMessage(">>> Candle closed INSIDE 4H range");

      // Show last 3 candles for context
      LogMessage("--- Last 3 Candles for Context ---");
      for(int i = 1; i <= 3; i++)
      {
         datetime t = iTime(_Symbol, PERIOD_M5, i);
         double o = iOpen(_Symbol, PERIOD_M5, i);
         double h = iHigh(_Symbol, PERIOD_M5, i);
         double l = iLow(_Symbol, PERIOD_M5, i);
         double c = iClose(_Symbol, PERIOD_M5, i);

         string status = "";
         if(c < g_4HLow)
            status = " [BELOW 4H Low]";
         else if(c > g_4HHigh)
            status = " [ABOVE 4H High]";
         else
            status = " [INSIDE range]";

         LogMessage("Candle[" + IntegerToString(i) + "] " + TimeToString(t, TIME_DATE|TIME_MINUTES) +
                    " | O:" + DoubleToString(o, _Digits) +
                    " H:" + DoubleToString(h, _Digits) +
                    " L:" + DoubleToString(l, _Digits) +
                    " C:" + DoubleToString(c, _Digits) + status);
      }
   }

   // Export candle data to CSV for verification
   if(ExportCandleData)
   {
      ExportCandleToCSV(candle5mTime, candle5mOpen, candle5mHigh, candle5mLow, candle5mClose);
   }

   // Log active trades every 5-min candle
   if(LogActiveTradesEvery5Min)
   {
      LogActiveTrades();
   }

   // Track BUY signal (false breakout below 4H Low, then reversal above)
   bool canCheckBuySignal = !g_buyOrderPlaced && !HasOpenPosition(ORDER_TYPE_BUY);

   if(EnableDetailedLogging)
   {
      LogMessage("--- BUY Signal Check ---");
      LogMessage("g_buyOrderPlaced: " + (g_buyOrderPlaced ? "TRUE" : "FALSE"));
      LogMessage("HasOpenPosition(BUY): " + (HasOpenPosition(ORDER_TYPE_BUY) ? "TRUE" : "FALSE"));
      LogMessage("Can check BUY signal: " + (canCheckBuySignal ? "YES" : "NO"));
   }

   if(canCheckBuySignal)
   {
      // Step 1 & 2: Check if 5-min candle closed BELOW 4H Low (breakout confirmation)
      if(!g_buyBreakoutConfirmed && candle5mClose < g_4HLow)
      {
         LogMessage("*** BUY BREAKOUT DETECTED ***");
         LogMessage("5-min candle closed BELOW 4H Low");
         LogMessage("Candle Time: " + TimeToString(candle5mTime, TIME_DATE|TIME_MINUTES));
         LogMessage("Candle OHLC: O=" + DoubleToString(candle5mOpen, _Digits) +
                    " H=" + DoubleToString(candle5mHigh, _Digits) +
                    " L=" + DoubleToString(candle5mLow, _Digits) +
                    " C=" + DoubleToString(candle5mClose, _Digits));
         LogMessage("Candle Close: " + DoubleToString(candle5mClose, _Digits) + " | 4H Low: " + DoubleToString(g_4HLow, _Digits));
         LogMessage("Breakout Distance: " + DoubleToString(g_4HLow - candle5mClose, _Digits) + " points");

         // Check volume confirmation if enabled - want LOW volume on breakout
         bool volumeOK = true;
         if(g_activeVolumeConfirmation)
         {
            LogMessage("--- Checking Breakout Volume (Want LOW) ---");

            // Get volume of the breakout candle (index 1 = last closed candle)
            g_buyBreakoutVolume = GetCandleVolume(1);

            // Calculate average volume using symbol-specific period
            g_averageVolume = CalculateAverageVolume(g_symbolParams.volumeAveragePeriod);

            // Check if breakout volume is LOW (weak breakout = good for false breakout strategy)
            // Use symbol-specific threshold
            g_buyBreakoutVolumeOK = IsBreakoutVolumeLow(g_buyBreakoutVolume, g_averageVolume, g_symbolParams.breakoutVolumeMax);

            volumeOK = g_buyBreakoutVolumeOK;
         }
         else
         {
            LogMessage("Volume confirmation disabled - accepting breakout");
            g_buyBreakoutVolumeOK = true;
         }

         // Check divergence confirmation if volume is OK
         bool divergenceOK = true;
         if(volumeOK && g_activeDivergenceConfirmation)
         {
            LogMessage("--- Checking Divergence (Want Bullish) ---");

            bool rsiDivergence = DetectBullishRSIDivergence();
            bool macdDivergence = DetectBullishMACDDivergence();

            // Determine if divergence requirement is met
            if(RequireBothIndicators)
            {
               // Strict mode: require BOTH RSI and MACD divergence
               divergenceOK = (rsiDivergence && macdDivergence);
               g_buyDivergenceOK = divergenceOK;

               if(divergenceOK)
                  LogMessage("BOTH RSI and MACD show bullish divergence - CONFIRMED");
               else
                  LogMessage("Divergence requirement NOT met (need both RSI and MACD)");
            }
            else
            {
               // Lenient mode: require EITHER RSI or MACD divergence
               divergenceOK = (rsiDivergence || macdDivergence);
               g_buyDivergenceOK = divergenceOK;

               if(divergenceOK)
                  LogMessage("At least one indicator shows bullish divergence - CONFIRMED");
               else
                  LogMessage("No divergence detected on either RSI or MACD");
            }
         }
         else if(!g_activeDivergenceConfirmation)
         {
            LogMessage("Divergence confirmation disabled - accepting breakout");
            g_buyDivergenceOK = true;
         }

         // Only confirm breakout if BOTH volume and divergence are OK
         if(volumeOK && divergenceOK)
         {
            g_buyBreakoutConfirmed = true;
            g_buyBreakoutCandleTime = candle5mTime;
            LogMessage("*** BUY BREAKOUT CONFIRMED (Low Volume + Bullish Divergence) ***");
            LogMessage("Waiting for reversal back above 4H Low...");
         }
         else
         {
            if(!volumeOK)
            {
               LogMessage("*** BUY BREAKOUT REJECTED - Volume Too High ***");
               LogMessage("Strong breakout likely to continue - not ideal for false breakout");
            }
            if(!divergenceOK)
            {
               LogMessage("*** BUY BREAKOUT REJECTED - No Bullish Divergence ***");
               LogMessage("Strong momentum suggests true breakout - not ideal for reversal");
            }

            LogMessage("Resetting to wait for next breakout opportunity");
            // Reset flags so we can check for another breakout
            g_buyBreakoutConfirmed = false;
            g_buyBreakoutVolumeOK = false;
            g_buyDivergenceOK = false;
         }
      }
      else if(!g_buyBreakoutConfirmed && EnableDetailedLogging)
      {
         LogMessage("BUY Breakout NOT confirmed: Close (" + DoubleToString(candle5mClose, _Digits) +
                    ") >= 4H Low (" + DoubleToString(g_4HLow, _Digits) + ")");
      }

      // Step 3 & 4: Check if 5-min candle closed ABOVE 4H Low (reversal confirmation)
      if(g_buyBreakoutConfirmed && !g_buyReversalConfirmed && candle5mClose > g_4HLow)
      {
         LogMessage("*** BUY REVERSAL DETECTED ***");
         LogMessage("5-min candle closed ABOVE 4H Low after breakout");
         LogMessage("Candle Time: " + TimeToString(candle5mTime, TIME_DATE|TIME_MINUTES));
         LogMessage("Candle OHLC: O=" + DoubleToString(candle5mOpen, _Digits) +
                    " H=" + DoubleToString(candle5mHigh, _Digits) +
                    " L=" + DoubleToString(candle5mLow, _Digits) +
                    " C=" + DoubleToString(candle5mClose, _Digits));
         LogMessage("Candle Close: " + DoubleToString(candle5mClose, _Digits) + " | 4H Low: " + DoubleToString(g_4HLow, _Digits));
         LogMessage("Reversal Distance: " + DoubleToString(candle5mClose - g_4HLow, _Digits) + " points");

         // Check reversal volume confirmation if enabled - want HIGH volume on reversal
         bool reversalVolumeOK = true;
         if(g_activeVolumeConfirmation)
         {
            LogMessage("--- Checking Reversal Volume (Want HIGH) ---");

            // Get volume of the reversal candle (index 1 = last closed candle)
            g_buyReversalVolume = GetCandleVolume(1);

            // Reuse average volume if already calculated, otherwise calculate it
            if(g_averageVolume <= 0)
            {
               g_averageVolume = CalculateAverageVolume(g_symbolParams.volumeAveragePeriod);
            }

            // Check if reversal volume is HIGH (strong reversal = good confirmation)
            // Use symbol-specific threshold
            g_buyReversalVolumeOK = IsReversalVolumeHigh(g_buyReversalVolume, g_averageVolume, g_symbolParams.reversalVolumeMin);

            reversalVolumeOK = g_buyReversalVolumeOK;
         }
         else
         {
            LogMessage("Volume confirmation disabled - accepting reversal");
            g_buyReversalVolumeOK = true;
         }

         // Only confirm reversal if volume is HIGH (or volume check is disabled)
         if(!reversalVolumeOK)
         {
            LogMessage("*** BUY REVERSAL REJECTED - Volume Too Low ***");
            LogMessage("Weak reversal lacks conviction - not ideal for trade");
            LogMessage("Resetting to wait for next opportunity");
            // Reset flags so we can check for another breakout
            g_buyBreakoutConfirmed = false;
            g_buyReversalConfirmed = false;
            g_buyBreakoutVolumeOK = false;
            g_buyReversalVolumeOK = false;
            g_buyDivergenceOK = false;
            return;
         }

         g_buyReversalConfirmed = true;

         // Find the LOWEST low among the LATEST 10 candles within breakout-to-reversal range
         // Use the LATER of: (1) 10 candles back, or (2) breakout time
         // This ensures we analyze up to 10 candles but never before the breakout
         datetime startTime = MathMax(g_buyBreakoutCandleTime, candle5mTime - (10 * 5 * 60));
         double lowestLow = FindLowestLowInRange(startTime, candle5mTime);

         LogMessage("Analyzing latest 10 candles from " + TimeToString(startTime, TIME_MINUTES) +
                    " to " + TimeToString(candle5mTime, TIME_MINUTES));
         LogMessage("(Breakout occurred at: " + TimeToString(g_buyBreakoutCandleTime, TIME_MINUTES) + ")");

         // Validate lowestLow before proceeding
         if(lowestLow == DBL_MAX || lowestLow <= 0)
         {
            LogMessage("ERROR: No valid bullish candles found in breakout pattern");
            LogMessage("Cannot determine lowest low - skipping BUY order");
            LogMessage("Resetting BUY signal tracking");
            g_buyBreakoutConfirmed = false;
            g_buyReversalConfirmed = false;
            return;
         }

         LogMessage("LOWEST Low in pattern: " + DoubleToString(lowestLow, _Digits));
         LogMessage("*** BUY REVERSAL CONFIRMED (High Volume) ***");
         LogMessage("FALSE BREAKOUT PATTERN COMPLETE - Executing BUY order");

         // Execute buy order using optimized SL calculation
         if(ExecuteBuyOrder(lowestLow, g_buyBreakoutCandleTime, candle5mTime))
         {
            g_buyOrderPlaced = true;
            LogMessage(">>> g_buyOrderPlaced set to TRUE <<<");
            // Reset tracking after successful order
            g_buyBreakoutConfirmed = false;
            g_buyReversalConfirmed = false;
            g_buyBreakoutCandleTime = 0;
            LogMessage("Buy order successfully placed and executed");
         }
         else
         {
            LogMessage("Buy order execution FAILED");
            LogMessage(">>> g_buyOrderPlaced remains FALSE - will retry on next signal <<<");
            // Reset on failure to try again
            g_buyBreakoutConfirmed = false;
            g_buyReversalConfirmed = false;
            g_buyBreakoutCandleTime = 0;
            // Don't set g_buyOrderPlaced = true on failure, so we can try again
         }
      }
   }

   // Track SELL signal (false breakout above 4H High, then reversal below)
   bool canCheckSellSignal = !g_sellOrderPlaced && !HasOpenPosition(ORDER_TYPE_SELL);

   if(EnableDetailedLogging)
   {
      LogMessage("--- SELL Signal Check ---");
      LogMessage("g_sellOrderPlaced: " + (g_sellOrderPlaced ? "TRUE" : "FALSE"));
      LogMessage("HasOpenPosition(SELL): " + (HasOpenPosition(ORDER_TYPE_SELL) ? "TRUE" : "FALSE"));
      LogMessage("Can check SELL signal: " + (canCheckSellSignal ? "YES" : "NO"));
   }

   if(canCheckSellSignal)
   {
      // Step 1 & 2: Check if 5-min candle closed ABOVE 4H High (breakout confirmation)
      if(!g_sellBreakoutConfirmed && candle5mClose > g_4HHigh)
      {
         LogMessage("*** SELL BREAKOUT DETECTED ***");
         LogMessage("5-min candle closed ABOVE 4H High");
         LogMessage("Candle Time: " + TimeToString(candle5mTime, TIME_DATE|TIME_MINUTES));
         LogMessage("Candle OHLC: O=" + DoubleToString(candle5mOpen, _Digits) +
                    " H=" + DoubleToString(candle5mHigh, _Digits) +
                    " L=" + DoubleToString(candle5mLow, _Digits) +
                    " C=" + DoubleToString(candle5mClose, _Digits));
         LogMessage("Candle Close: " + DoubleToString(candle5mClose, _Digits) + " | 4H High: " + DoubleToString(g_4HHigh, _Digits));
         LogMessage("Breakout Distance: " + DoubleToString(candle5mClose - g_4HHigh, _Digits) + " points");

         // Check volume confirmation if enabled - want LOW volume on breakout
         bool volumeOK = true;
         if(g_activeVolumeConfirmation)
         {
            LogMessage("--- Checking Breakout Volume (Want LOW) ---");

            // Get volume of the breakout candle (index 1 = last closed candle)
            g_sellBreakoutVolume = GetCandleVolume(1);

            // Calculate average volume (reuse if already calculated for BUY check)
            if(g_averageVolume <= 0)
            {
               g_averageVolume = CalculateAverageVolume(g_symbolParams.volumeAveragePeriod);
            }

            // Check if breakout volume is LOW (weak breakout = good for false breakout strategy)
            // Use symbol-specific threshold
            g_sellBreakoutVolumeOK = IsBreakoutVolumeLow(g_sellBreakoutVolume, g_averageVolume, g_symbolParams.breakoutVolumeMax);

            volumeOK = g_sellBreakoutVolumeOK;
         }
         else
         {
            LogMessage("Volume confirmation disabled - accepting breakout");
            g_sellBreakoutVolumeOK = true;
         }

         // Check divergence confirmation if volume is OK
         bool divergenceOK = true;
         if(volumeOK && g_activeDivergenceConfirmation)
         {
            LogMessage("--- Checking Divergence (Want Bearish) ---");

            bool rsiDivergence = DetectBearishRSIDivergence();
            bool macdDivergence = DetectBearishMACDDivergence();

            // Determine if divergence requirement is met
            if(RequireBothIndicators)
            {
               // Strict mode: require BOTH RSI and MACD divergence
               divergenceOK = (rsiDivergence && macdDivergence);
               g_sellDivergenceOK = divergenceOK;

               if(divergenceOK)
                  LogMessage("BOTH RSI and MACD show bearish divergence - CONFIRMED");
               else
                  LogMessage("Divergence requirement NOT met (need both RSI and MACD)");
            }
            else
            {
               // Lenient mode: require EITHER RSI or MACD divergence
               divergenceOK = (rsiDivergence || macdDivergence);
               g_sellDivergenceOK = divergenceOK;

               if(divergenceOK)
                  LogMessage("At least one indicator shows bearish divergence - CONFIRMED");
               else
                  LogMessage("No divergence detected on either RSI or MACD");
            }
         }
         else if(!g_activeDivergenceConfirmation)
         {
            LogMessage("Divergence confirmation disabled - accepting breakout");
            g_sellDivergenceOK = true;
         }

         // Only confirm breakout if BOTH volume and divergence are OK
         if(volumeOK && divergenceOK)
         {
            g_sellBreakoutConfirmed = true;
            g_sellBreakoutCandleTime = candle5mTime;
            LogMessage("*** SELL BREAKOUT CONFIRMED (Low Volume + Bearish Divergence) ***");
            LogMessage("Waiting for reversal back below 4H High...");
         }
         else
         {
            if(!volumeOK)
            {
               LogMessage("*** SELL BREAKOUT REJECTED - Volume Too High ***");
               LogMessage("Strong breakout likely to continue - not ideal for false breakout");
            }
            if(!divergenceOK)
            {
               LogMessage("*** SELL BREAKOUT REJECTED - No Bearish Divergence ***");
               LogMessage("Strong momentum suggests true breakout - not ideal for reversal");
            }

            LogMessage("Resetting to wait for next breakout opportunity");
            // Reset flags so we can check for another breakout
            g_sellBreakoutConfirmed = false;
            g_sellBreakoutVolumeOK = false;
            g_sellDivergenceOK = false;
         }
      }
      else if(!g_sellBreakoutConfirmed && EnableDetailedLogging)
      {
         LogMessage("SELL Breakout NOT confirmed: Close (" + DoubleToString(candle5mClose, _Digits) +
                    ") <= 4H High (" + DoubleToString(g_4HHigh, _Digits) + ")");
      }

      // Step 3 & 4: Check if 5-min candle closed BELOW 4H High (reversal confirmation)
      if(g_sellBreakoutConfirmed && !g_sellReversalConfirmed && candle5mClose < g_4HHigh)
      {
         LogMessage("*** SELL REVERSAL DETECTED ***");
         LogMessage("5-min candle closed BELOW 4H High after breakout");
         LogMessage("Candle Time: " + TimeToString(candle5mTime, TIME_DATE|TIME_MINUTES));
         LogMessage("Candle OHLC: O=" + DoubleToString(candle5mOpen, _Digits) +
                    " H=" + DoubleToString(candle5mHigh, _Digits) +
                    " L=" + DoubleToString(candle5mLow, _Digits) +
                    " C=" + DoubleToString(candle5mClose, _Digits));
         LogMessage("Candle Close: " + DoubleToString(candle5mClose, _Digits) + " | 4H High: " + DoubleToString(g_4HHigh, _Digits));
         LogMessage("Reversal Distance: " + DoubleToString(g_4HHigh - candle5mClose, _Digits) + " points");

         // Check reversal volume confirmation if enabled - want HIGH volume on reversal
         bool reversalVolumeOK = true;
         if(g_activeVolumeConfirmation)
         {
            LogMessage("--- Checking Reversal Volume (Want HIGH) ---");

            // Get volume of the reversal candle (index 1 = last closed candle)
            g_sellReversalVolume = GetCandleVolume(1);

            // Reuse average volume if already calculated, otherwise calculate it
            if(g_averageVolume <= 0)
            {
               g_averageVolume = CalculateAverageVolume(g_symbolParams.volumeAveragePeriod);
            }

            // Check if reversal volume is HIGH (strong reversal = good confirmation)
            // Use symbol-specific threshold
            g_sellReversalVolumeOK = IsReversalVolumeHigh(g_sellReversalVolume, g_averageVolume, g_symbolParams.reversalVolumeMin);

            reversalVolumeOK = g_sellReversalVolumeOK;
         }
         else
         {
            LogMessage("Volume confirmation disabled - accepting reversal");
            g_sellReversalVolumeOK = true;
         }

         // Only confirm reversal if volume is HIGH (or volume check is disabled)
         if(!reversalVolumeOK)
         {
            LogMessage("*** SELL REVERSAL REJECTED - Volume Too Low ***");
            LogMessage("Weak reversal lacks conviction - not ideal for trade");
            LogMessage("Resetting to wait for next opportunity");
            // Reset flags so we can check for another breakout
            g_sellBreakoutConfirmed = false;
            g_sellReversalConfirmed = false;
            g_sellBreakoutVolumeOK = false;
            g_sellReversalVolumeOK = false;
            g_sellDivergenceOK = false;
            return;
         }

         g_sellReversalConfirmed = true;

         // Find the HIGHEST high among the LATEST 10 candles within breakout-to-reversal range
         // Use the LATER of: (1) 10 candles back, or (2) breakout time
         // This ensures we analyze up to 10 candles but never before the breakout
         datetime startTime = MathMax(g_sellBreakoutCandleTime, candle5mTime - (10 * 5 * 60));
         double highestHigh = FindHighestHighInRange(startTime, candle5mTime);

         LogMessage("Analyzing latest 10 candles from " + TimeToString(startTime, TIME_MINUTES) +
                    " to " + TimeToString(candle5mTime, TIME_MINUTES));
         LogMessage("(Breakout occurred at: " + TimeToString(g_sellBreakoutCandleTime, TIME_MINUTES) + ")");

         // Validate highestHigh before proceeding
         if(highestHigh <= 0 || highestHigh == DBL_MAX)
         {
            LogMessage("ERROR: No valid bearish candles found in breakout pattern");
            LogMessage("Cannot determine highest high - skipping SELL order");
            LogMessage("Resetting SELL signal tracking");
            g_sellBreakoutConfirmed = false;
            g_sellReversalConfirmed = false;
            return;
         }

         LogMessage("HIGHEST High in pattern: " + DoubleToString(highestHigh, _Digits));
         LogMessage("*** SELL REVERSAL CONFIRMED (High Volume) ***");
         LogMessage("FALSE BREAKOUT PATTERN COMPLETE - Executing SELL order");

         // Execute sell order using optimized SL calculation
         if(ExecuteSellOrder(highestHigh, g_sellBreakoutCandleTime, candle5mTime))
         {
            g_sellOrderPlaced = true;
            LogMessage(">>> g_sellOrderPlaced set to TRUE <<<");
            // Reset tracking after successful order
            g_sellBreakoutConfirmed = false;
            g_sellReversalConfirmed = false;
            g_sellBreakoutCandleTime = 0;
            LogMessage("Sell order successfully placed and executed");
         }
         else
         {
            LogMessage("Sell order execution FAILED");
            LogMessage(">>> g_sellOrderPlaced remains FALSE - will retry on next signal <<<");
            // Reset on failure to try again
            g_sellBreakoutConfirmed = false;
            g_sellReversalConfirmed = false;
            g_sellBreakoutCandleTime = 0;
            // Don't set g_sellOrderPlaced = true on failure, so we can try again
         }
      }
   }

   // Detailed logging of current state
   if(EnableDetailedLogging)
   {
      LogMessage("--- False Breakout Tracking ---");
      LogMessage("Using 4H Candle: " + TimeToString(g_processed04CandleTime, TIME_DATE|TIME_MINUTES) + " UTC");
      LogMessage("Last 5min Close: " + DoubleToString(candle5mClose, _Digits));
      LogMessage("4H High: " + DoubleToString(g_4HHigh, _Digits) + " | 4H Low: " + DoubleToString(g_4HLow, _Digits));
      LogMessage("BUY: Breakout=" + (g_buyBreakoutConfirmed ? "YES" : "NO") + " | Reversal=" + (g_buyReversalConfirmed ? "YES" : "NO"));
      LogMessage("SELL: Breakout=" + (g_sellBreakoutConfirmed ? "YES" : "NO") + " | Reversal=" + (g_sellReversalConfirmed ? "YES" : "NO"));
   }
}

//+------------------------------------------------------------------+
//| Execute buy order                                                |
//+------------------------------------------------------------------+
bool ExecuteBuyOrder(double lowestLow, datetime breakoutTime, datetime reversalTime)
{
   LogMessage("--- Executing BUY Order ---");

   double currentAsk = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   // Calculate optimized stop-loss
   double stopLoss = CalculateOptimizedBuySL(lowestLow, currentAsk, breakoutTime, reversalTime);
   double risk = currentAsk - stopLoss;
   double takeProfit = currentAsk + (risk * RiskRewardRatio);

   LogMessage("=== Final Order Parameters ===");
   LogMessage("Entry Price: " + DoubleToString(currentAsk, _Digits));
   LogMessage("Final SL: " + DoubleToString(stopLoss, _Digits));
   LogMessage("Final Risk: " + DoubleToString(risk, _Digits) + " points");
   LogMessage("Final TP: " + DoubleToString(takeProfit, _Digits) + " (Risk × " + DoubleToString(RiskRewardRatio, 2) + ")");

   // Validate SL/TP
   if(stopLoss <= 0 || takeProfit <= 0 || stopLoss >= currentAsk)
   {
      LogMessage("ERROR: Invalid SL/TP levels. SL=" + DoubleToString(stopLoss, _Digits) + ", TP=" + DoubleToString(takeProfit, _Digits));
      return false;
   }

   double lotSize = CalculateLotSize(currentAsk, stopLoss);
   LogMessage("Calculated lot size: " + DoubleToString(lotSize, 2));

   if(lotSize < MinLotSize)
   {
      LogMessage("ERROR: Calculated lot size (" + DoubleToString(lotSize, 2) + ") is below minimum (" + DoubleToString(MinLotSize, 2) + ")");
      return false;
   }

   MqlTradeRequest request = {};
   MqlTradeResult result = {};

   request.action = TRADE_ACTION_DEAL;
   request.symbol = _Symbol;
   request.volume = lotSize;
   request.type = ORDER_TYPE_BUY;
   request.price = currentAsk;
   request.sl = NormalizePrice(stopLoss);
   request.tp = NormalizePrice(takeProfit);
   request.deviation = 10;
   request.magic = MagicNumber;
   request.comment = TradeComment;
   request.type_filling = ORDER_FILLING_FOK;

   LogMessage("Order Request Details:");
   LogMessage("  Symbol: " + request.symbol);
   LogMessage("  Volume: " + DoubleToString(request.volume, 2));
   LogMessage("  Type: BUY");
   LogMessage("  Price: " + DoubleToString(request.price, _Digits));
   LogMessage("  Stop-Loss: " + DoubleToString(request.sl, _Digits));
   LogMessage("  Take-Profit: " + DoubleToString(request.tp, _Digits));
   LogMessage("  Magic: " + IntegerToString(request.magic));

   if(!OrderSend(request, result))
   {
      LogMessage("ERROR: OrderSend failed. Error code: " + IntegerToString(GetLastError()));
      LogMessage("Result code: " + IntegerToString(result.retcode) + " | " + result.comment);
      return false;
   }

   LogMessage("OrderSend result code: " + IntegerToString(result.retcode));
   LogMessage("Result comment: " + result.comment);

   if(result.retcode == TRADE_RETCODE_DONE || result.retcode == TRADE_RETCODE_PLACED)
   {
      LogMessage("SUCCESS: Buy order executed");
      LogMessage("  Ticket: " + IntegerToString(result.order));
      LogMessage("  Execution Price: " + DoubleToString(result.price, _Digits));
      LogMessage("  Volume: " + DoubleToString(result.volume, 2));

      LogTrade("BUY", result.order, lotSize, result.price, stopLoss, takeProfit);
      return true;
   }

   LogMessage("Order not executed. Return code: " + IntegerToString(result.retcode));
   return false;
}

//+------------------------------------------------------------------+
//| Execute sell order                                               |
//+------------------------------------------------------------------+
bool ExecuteSellOrder(double highestHigh, datetime breakoutTime, datetime reversalTime)
{
   LogMessage("--- Executing SELL Order ---");

   double currentBid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   // Calculate optimized stop-loss
   double stopLoss = CalculateOptimizedSellSL(highestHigh, currentBid, breakoutTime, reversalTime);
   double risk = stopLoss - currentBid;
   double takeProfit = currentBid - (risk * RiskRewardRatio);

   LogMessage("=== Final Order Parameters ===");
   LogMessage("Entry Price: " + DoubleToString(currentBid, _Digits));
   LogMessage("Final SL: " + DoubleToString(stopLoss, _Digits));
   LogMessage("Final Risk: " + DoubleToString(risk, _Digits) + " points");
   LogMessage("Final TP: " + DoubleToString(takeProfit, _Digits) + " (Risk × " + DoubleToString(RiskRewardRatio, 2) + ")");

   // Validate SL/TP
   if(stopLoss <= 0 || takeProfit <= 0 || stopLoss <= currentBid)
   {
      LogMessage("ERROR: Invalid SL/TP levels. SL=" + DoubleToString(stopLoss, _Digits) + ", TP=" + DoubleToString(takeProfit, _Digits));
      return false;
   }

   double lotSize = CalculateLotSize(currentBid, stopLoss);
   LogMessage("Calculated lot size: " + DoubleToString(lotSize, 2));

   if(lotSize < MinLotSize)
   {
      LogMessage("ERROR: Calculated lot size (" + DoubleToString(lotSize, 2) + ") is below minimum (" + DoubleToString(MinLotSize, 2) + ")");
      return false;
   }

   MqlTradeRequest request = {};
   MqlTradeResult result = {};

   request.action = TRADE_ACTION_DEAL;
   request.symbol = _Symbol;
   request.volume = lotSize;
   request.type = ORDER_TYPE_SELL;
   request.price = currentBid;
   request.sl = NormalizePrice(stopLoss);
   request.tp = NormalizePrice(takeProfit);
   request.deviation = 10;
   request.magic = MagicNumber;
   request.comment = TradeComment;
   request.type_filling = ORDER_FILLING_FOK;

   LogMessage("Order Request Details:");
   LogMessage("  Symbol: " + request.symbol);
   LogMessage("  Volume: " + DoubleToString(request.volume, 2));
   LogMessage("  Type: SELL");
   LogMessage("  Price: " + DoubleToString(request.price, _Digits));
   LogMessage("  Stop-Loss: " + DoubleToString(request.sl, _Digits));
   LogMessage("  Take-Profit: " + DoubleToString(request.tp, _Digits));
   LogMessage("  Magic: " + IntegerToString(request.magic));

   if(!OrderSend(request, result))
   {
      LogMessage("ERROR: OrderSend failed. Error code: " + IntegerToString(GetLastError()));
      LogMessage("Result code: " + IntegerToString(result.retcode) + " | " + result.comment);
      return false;
   }

   LogMessage("OrderSend result code: " + IntegerToString(result.retcode));
   LogMessage("Result comment: " + result.comment);

   if(result.retcode == TRADE_RETCODE_DONE || result.retcode == TRADE_RETCODE_PLACED)
   {
      LogMessage("SUCCESS: Sell order executed");
      LogMessage("  Ticket: " + IntegerToString(result.order));
      LogMessage("  Execution Price: " + DoubleToString(result.price, _Digits));
      LogMessage("  Volume: " + DoubleToString(result.volume, 2));

      LogTrade("SELL", result.order, lotSize, result.price, stopLoss, takeProfit);
      return true;
   }

   LogMessage("Order not executed. Return code: " + IntegerToString(result.retcode));
   return false;
}

//+------------------------------------------------------------------+
//| Calculate lot size based on risk management                      |
//+------------------------------------------------------------------+
double CalculateLotSize(double entryPrice, double stopLoss)
{
   if(EnableDetailedLogging)
      LogMessage("--- Calculating Lot Size ---");

   double accountBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskAmount = accountBalance * (RiskPercentPerTrade / 100.0);

   if(EnableDetailedLogging)
   {
      LogMessage("Account Balance: " + DoubleToString(accountBalance, 2));
      LogMessage("Risk Percent: " + DoubleToString(RiskPercentPerTrade, 2) + "%");
      LogMessage("Risk Amount: " + DoubleToString(riskAmount, 2));
   }

   // Use cached symbol properties for better performance
   double stopLossPoints = MathAbs(entryPrice - stopLoss) / g_symbolPoint;

   if(EnableDetailedLogging)
   {
      LogMessage("Entry Price: " + DoubleToString(entryPrice, _Digits));
      LogMessage("Stop-Loss: " + DoubleToString(stopLoss, _Digits));
      LogMessage("SL Distance: " + DoubleToString(MathAbs(entryPrice - stopLoss), _Digits));
      LogMessage("SL Points: " + DoubleToString(stopLossPoints, 0));
      LogMessage("Point Value: " + DoubleToString(g_symbolTickValue, 2));
   }

   double lotSize = riskAmount / (stopLossPoints * g_symbolTickValue);

   if(EnableDetailedLogging)
      LogMessage("Raw lot size: " + DoubleToString(lotSize, 2));

   // Normalize lot size using cached values
   lotSize = MathFloor(lotSize / g_symbolLotStep) * g_symbolLotStep;
   // Ensure both symbol AND user minimums/maximums are respected
   lotSize = MathMax(lotSize, MathMax(g_symbolMinLot, MinLotSize));
   lotSize = MathMin(lotSize, MathMin(g_symbolMaxLot, MaxLotSize));

   if(EnableDetailedLogging)
   {
      LogMessage("Symbol Min Lot: " + DoubleToString(g_symbolMinLot, 2));
      LogMessage("Symbol Max Lot: " + DoubleToString(g_symbolMaxLot, 2));
      LogMessage("Lot Step: " + DoubleToString(g_symbolLotStep, 2));
      LogMessage("Final lot size: " + DoubleToString(lotSize, 2));
   }

   return lotSize;
}

//+------------------------------------------------------------------+
//| Check if ticket is in breakeven list - OPTIMIZED                 |
//+------------------------------------------------------------------+
bool IsTicketInBreakevenList(ulong ticket)
{
   // Binary search would be ideal if array was sorted, but for small arrays
   // linear search is fine. Most EAs won't have more than a few positions.
   int size = ArraySize(g_breakevenSetTickets);
   for(int i = 0; i < size; i++)
   {
      if(g_breakevenSetTickets[i] == ticket)
         return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Add ticket to breakeven list - OPTIMIZED                         |
//+------------------------------------------------------------------+
void AddTicketToBreakevenList(ulong ticket)
{
   // Check if already exists to avoid duplicates
   if(IsTicketInBreakevenList(ticket))
      return;

   int size = ArraySize(g_breakevenSetTickets);
   ArrayResize(g_breakevenSetTickets, size + 1);
   g_breakevenSetTickets[size] = ticket;

   if(EnableDetailedLogging)
      LogMessage("Position #" + IntegerToString(ticket) + " added to breakeven tracking list");
}

//+------------------------------------------------------------------+
//| Remove ticket from breakeven list - OPTIMIZED (swap and pop)     |
//+------------------------------------------------------------------+
void RemoveTicketFromBreakevenList(ulong ticket)
{
   int size = ArraySize(g_breakevenSetTickets);

   for(int i = 0; i < size; i++)
   {
      if(g_breakevenSetTickets[i] == ticket)
      {
         // Swap with last element and reduce size (faster than shifting)
         g_breakevenSetTickets[i] = g_breakevenSetTickets[size - 1];
         ArrayResize(g_breakevenSetTickets, size - 1);

         if(EnableDetailedLogging)
            LogMessage("Position #" + IntegerToString(ticket) + " removed from breakeven tracking list");

         return;
      }
   }
}

//+------------------------------------------------------------------+
//| Clear breakeven tracking list                                    |
//+------------------------------------------------------------------+
void ClearBreakevenList()
{
   ArrayResize(g_breakevenSetTickets, 0);
   LogMessage("Breakeven tracking list cleared");
}


//+------------------------------------------------------------------+
//| Clean up closed positions from tracking lists                    |
//+------------------------------------------------------------------+
void CleanupClosedPositions()
{
   // Clean up breakeven tracking
   int beSize = ArraySize(g_breakevenSetTickets);
   for(int i = beSize - 1; i >= 0; i--)
   {
      ulong ticket = g_breakevenSetTickets[i];

      // Try to select the position
      if(!PositionSelectByTicket(ticket))
      {
         // Position no longer exists - remove from list
         RemoveTicketFromBreakevenList(ticket);
         LogMessage("Position #" + IntegerToString(ticket) + " closed - removed from breakeven tracking");
      }
   }

   // Clean up trailing stop tracking
   int tsSize = ArraySize(g_trailingStopActiveTickets);
   for(int i = tsSize - 1; i >= 0; i--)
   {
      ulong ticket = g_trailingStopActiveTickets[i];

      // Try to select the position
      if(!PositionSelectByTicket(ticket))
      {
         // Position no longer exists - remove from list
         DeactivateTrailingStop(ticket);
         LogMessage("Position #" + IntegerToString(ticket) + " closed - removed from trailing stop tracking");
      }
   }
}

//+------------------------------------------------------------------+
//| Check if ticket has trailing stop activated - OPTIMIZED          |
//+------------------------------------------------------------------+
bool IsTrailingStopActive(ulong ticket)
{
   int size = ArraySize(g_trailingStopActiveTickets);
   for(int i = 0; i < size; i++)
   {
      if(g_trailingStopActiveTickets[i] == ticket)
         return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Add ticket to trailing stop active list - OPTIMIZED              |
//+------------------------------------------------------------------+
void ActivateTrailingStop(ulong ticket)
{
   // Check if already exists to avoid duplicates
   if(IsTrailingStopActive(ticket))
      return;

   int size = ArraySize(g_trailingStopActiveTickets);
   ArrayResize(g_trailingStopActiveTickets, size + 1);
   g_trailingStopActiveTickets[size] = ticket;

   LogMessage("Trailing stop ACTIVATED for position #" + IntegerToString(ticket));
}

//+------------------------------------------------------------------+
//| Remove ticket from trailing stop list - OPTIMIZED (swap and pop) |
//+------------------------------------------------------------------+
void DeactivateTrailingStop(ulong ticket)
{
   int size = ArraySize(g_trailingStopActiveTickets);

   for(int i = 0; i < size; i++)
   {
      if(g_trailingStopActiveTickets[i] == ticket)
      {
         // Swap with last element and reduce size (faster than shifting)
         g_trailingStopActiveTickets[i] = g_trailingStopActiveTickets[size - 1];
         ArrayResize(g_trailingStopActiveTickets, size - 1);

         if(EnableDetailedLogging)
            LogMessage("Position #" + IntegerToString(ticket) + " removed from trailing stop tracking");

         return;
      }
   }
}

//+------------------------------------------------------------------+
//| Clear trailing stop tracking list                                |
//+------------------------------------------------------------------+
void ClearTrailingStopList()
{
   ArrayResize(g_trailingStopActiveTickets, 0);
   LogMessage("Trailing stop tracking list cleared");
}


//+------------------------------------------------------------------+
//| Apply trailing stop - OPTIMIZED with PositionInfo                |
//+------------------------------------------------------------------+
void ApplyTrailingStopOptimized(PositionInfo &posInfo)
{
   string posTypeStr = (posInfo.type == POSITION_TYPE_BUY) ? "BUY" : "SELL";

   // Check if profit has reached the trailing stop trigger threshold
   if(posInfo.currentRR >= TrailingStopTriggerRR)
   {
      // Check if trailing stop is not yet activated for this position
      bool isFirstActivation = false;
      if(!IsTrailingStopActive(posInfo.ticket))
      {
         ActivateTrailingStop(posInfo.ticket);
         isFirstActivation = true;
      }

      // Calculate new trailing stop level
      double newSL = 0;
      bool needsUpdate = false;

      if(posInfo.type == POSITION_TYPE_BUY)
      {
         // For BUY: Trail below current price
         newSL = posInfo.currentPrice - TrailingStopDistance * g_symbolPoint;

         // Only update if new SL is higher than current SL
         if(newSL > posInfo.sl)
            needsUpdate = true;
      }
      else  // SELL
      {
         // For SELL: Trail above current price
         newSL = posInfo.currentPrice + TrailingStopDistance * g_symbolPoint;

         // Only update if new SL is lower than current SL
         if(newSL < posInfo.sl || posInfo.sl == 0)
            needsUpdate = true;
      }

      if(needsUpdate)
      {
         LogMessage("*** UPDATING TRAILING STOP ***");
         LogMessage("Ticket: " + IntegerToString(posInfo.ticket) + " | Type: " + posTypeStr);
         LogMessage("Current Price: " + DoubleToString(posInfo.currentPrice, _Digits));
         LogMessage("Current SL: " + DoubleToString(posInfo.sl, _Digits));
         LogMessage("New SL: " + DoubleToString(newSL, _Digits));
         LogMessage("Trailing Distance: " + DoubleToString(TrailingStopDistance, 0) + " points");

         if(isFirstActivation)
         {
            LogMessage("Take-Profit removed - position will be managed by trailing stop only");
         }

         MqlTradeRequest request = {};
         MqlTradeResult result = {};

         request.action = TRADE_ACTION_SLTP;
         request.position = posInfo.ticket;
         request.symbol = _Symbol;
         request.sl = NormalizePrice(newSL);
         request.tp = 0;  // Remove TP when trailing stop is active

         if(OrderSend(request, result))
         {
            if(result.retcode == TRADE_RETCODE_DONE)
            {
               LogMessage("SUCCESS: Trailing stop updated for ticket " + IntegerToString(posInfo.ticket));
            }
            else
            {
               LogMessage("WARNING: Modify result code: " + IntegerToString(result.retcode) + " | " + result.comment);
            }
         }
         else
         {
            LogMessage("ERROR: Failed to update trailing stop. Error: " + IntegerToString(GetLastError()));
            LogMessage("Result: " + IntegerToString(result.retcode) + " | " + result.comment);
         }
      }
      else if(EnableDetailedLogging)
      {
         LogMessage("Trailing stop for #" + IntegerToString(posInfo.ticket) + " - no update needed (SL: " +
                   DoubleToString(posInfo.sl, _Digits) + ")");
      }
   }
}

//+------------------------------------------------------------------+
//| Apply trailing stop (legacy function for compatibility)          |
//+------------------------------------------------------------------+
void ApplyTrailingStop(ulong ticket)
{
   if(!PositionSelectByTicket(ticket))
   {
      LogMessage("ApplyTrailingStop: Failed to select position " + IntegerToString(ticket));
      return;
   }

   // Create PositionInfo and call optimized version
   PositionInfo posInfo;
   posInfo.ticket = ticket;
   posInfo.type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
   posInfo.openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
   posInfo.sl = PositionGetDouble(POSITION_SL);
   posInfo.tp = PositionGetDouble(POSITION_TP);
   posInfo.currentPrice = (posInfo.type == POSITION_TYPE_BUY) ?
                          SymbolInfoDouble(_Symbol, SYMBOL_BID) :
                          SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   posInfo.risk = MathAbs(posInfo.openPrice - posInfo.sl);
   posInfo.currentPnL = (posInfo.type == POSITION_TYPE_BUY) ?
                        (posInfo.currentPrice - posInfo.openPrice) :
                        (posInfo.openPrice - posInfo.currentPrice);
   posInfo.currentRR = (posInfo.risk > 0) ? (posInfo.currentPnL / posInfo.risk) : 0;

   ApplyTrailingStopOptimized(posInfo);
}


//+------------------------------------------------------------------+
//| Manage open positions (breakeven, trailing, etc.) - OPTIMIZED    |
//+------------------------------------------------------------------+
void ManageOpenPositions()
{
   // Note: This function is called when (UseBreakeven OR UseTrailingStop) AND PositionsTotal()>0

   int totalPositions = PositionsTotal();

   if(EnableDetailedLogging)
      LogMessage("ManageOpenPositions: Checking " + IntegerToString(totalPositions) + " position(s)");

   for(int i = totalPositions - 1; i >= 0; i--)
   {
      PositionInfo posInfo;

      // Get all position info at once (optimized - single query)
      if(!GetPositionInfo(i, posInfo))
         continue;

      // Move stop-loss to breakeven if enabled and not already done
      if(UseBreakeven)
      {
         // Check if this position already has breakeven set
         if(!IsTicketInBreakevenList(posInfo.ticket))
         {
            // Move stop-loss to breakeven
            MoveToBreakevenOptimized(posInfo);
         }
         else if(EnableDetailedLogging)
         {
            LogMessage("Position #" + IntegerToString(posInfo.ticket) + " already at breakeven - skipping breakeven check");
         }
      }

      // Apply trailing stop if enabled (runs AFTER breakeven check)
      if(UseTrailingStop)
      {
         ApplyTrailingStopOptimized(posInfo);
      }
   }
}

//+------------------------------------------------------------------+
//| Move stop-loss to breakeven - OPTIMIZED with PositionInfo        |
//+------------------------------------------------------------------+
void MoveToBreakevenOptimized(PositionInfo &posInfo)
{
   string posTypeStr = (posInfo.type == POSITION_TYPE_BUY) ? "BUY" : "SELL";

   if(EnableDetailedLogging)
   {
      LogMessage("Checking breakeven for ticket " + IntegerToString(posInfo.ticket) + " (" + posTypeStr + ")");
      LogMessage("  Open: " + DoubleToString(posInfo.openPrice, _Digits) + " | Current: " + DoubleToString(posInfo.currentPrice, _Digits));
      LogMessage("  Current SL: " + DoubleToString(posInfo.sl, _Digits) + " | TP: " + DoubleToString(posInfo.tp, _Digits));
      LogMessage("  Risk: " + DoubleToString(posInfo.risk, _Digits) + " | Profit: " + DoubleToString(posInfo.currentPnL, _Digits));
      LogMessage("  Profit R:R: " + DoubleToString(posInfo.currentRR, 2) + " | Trigger: " + DoubleToString(BreakevenTriggerRR, 2));
   }

   // Check if profit has reached the breakeven trigger threshold
   if(posInfo.currentPnL >= posInfo.risk * BreakevenTriggerRR)
   {
      // Check if SL is not already at breakeven
      bool needsUpdate = false;

      if(posInfo.type == POSITION_TYPE_BUY && posInfo.sl < posInfo.openPrice)
         needsUpdate = true;
      else if(posInfo.type == POSITION_TYPE_SELL && posInfo.sl > posInfo.openPrice)
         needsUpdate = true;

      if(needsUpdate)
      {
         LogMessage("*** MOVING STOP-LOSS TO BREAKEVEN ***");
         LogMessage("Ticket: " + IntegerToString(posInfo.ticket) + " | Type: " + posTypeStr);

         MqlTradeRequest request = {};
         MqlTradeResult result = {};

         request.action = TRADE_ACTION_SLTP;
         request.position = posInfo.ticket;
         request.symbol = _Symbol;
         request.sl = NormalizePrice(posInfo.openPrice);
         request.tp = posInfo.tp;

         LogMessage("Modifying SL from " + DoubleToString(posInfo.sl, _Digits) + " to " + DoubleToString(posInfo.openPrice, _Digits));

         if(OrderSend(request, result))
         {
            if(result.retcode == TRADE_RETCODE_DONE)
            {
               LogMessage("SUCCESS: SL moved to breakeven for ticket " + IntegerToString(posInfo.ticket));

               // Add ticket to breakeven tracking list to prevent redundant checks
               AddTicketToBreakevenList(posInfo.ticket);
               LogMessage("Position #" + IntegerToString(posInfo.ticket) + " will not be checked for breakeven again");
            }
            else
            {
               LogMessage("WARNING: Modify result code: " + IntegerToString(result.retcode) + " | " + result.comment);
            }
         }
         else
         {
            LogMessage("ERROR: Failed to move SL to breakeven. Error: " + IntegerToString(GetLastError()));
            LogMessage("Result: " + IntegerToString(result.retcode) + " | " + result.comment);
         }
      }
      else if(EnableDetailedLogging)
      {
         LogMessage("SL already at or beyond breakeven - no update needed");
      }
   }
}

//+------------------------------------------------------------------+
//| Move stop-loss to breakeven (legacy function for compatibility)  |
//+------------------------------------------------------------------+
void MoveToBreakeven(ulong ticket)
{
   if(!PositionSelectByTicket(ticket))
   {
      LogMessage("MoveToBreakeven: Failed to select position " + IntegerToString(ticket));
      return;
   }

   // Create PositionInfo and call optimized version
   PositionInfo posInfo;
   posInfo.ticket = ticket;
   posInfo.type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
   posInfo.openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
   posInfo.sl = PositionGetDouble(POSITION_SL);
   posInfo.tp = PositionGetDouble(POSITION_TP);
   posInfo.currentPrice = (posInfo.type == POSITION_TYPE_BUY) ?
                          SymbolInfoDouble(_Symbol, SYMBOL_BID) :
                          SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   posInfo.risk = MathAbs(posInfo.openPrice - posInfo.sl);
   posInfo.currentPnL = (posInfo.type == POSITION_TYPE_BUY) ?
                        (posInfo.currentPrice - posInfo.openPrice) :
                        (posInfo.openPrice - posInfo.currentPrice);
   posInfo.currentRR = (posInfo.risk > 0) ? (posInfo.currentPnL / posInfo.risk) : 0;

   MoveToBreakevenOptimized(posInfo);
}

//+------------------------------------------------------------------+
//| Check if there's an open position of specified type              |
//+------------------------------------------------------------------+
bool HasOpenPosition(ENUM_ORDER_TYPE orderType)
{
   ENUM_POSITION_TYPE posType = (orderType == ORDER_TYPE_BUY) ?
                                 POSITION_TYPE_BUY :
                                 POSITION_TYPE_SELL;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == _Symbol &&
         PositionGetInteger(POSITION_MAGIC) == MagicNumber &&
         PositionGetInteger(POSITION_TYPE) == posType)
      {
         return true;
      }
   }

   return false;
}

//+------------------------------------------------------------------+
//| Check if in restricted trading period (00:00-08:00 UTC)          |
//| This covers both the first 4H candle (00:00-04:00) and second    |
//| 4H candle (04:00-08:00) to ensure proper data processing and     |
//| avoid trading during early market volatility                     |
//+------------------------------------------------------------------+
bool IsInCandleFormationPeriod()
{
   MqlDateTime currentTime;
   TimeToStruct(TimeCurrent(), currentTime);
   return (currentTime.hour >= 0 && currentTime.hour < 8);
}

//+------------------------------------------------------------------+
//| Check if current time is within trading hours                    |
//+------------------------------------------------------------------+
bool IsWithinTradingHours()
{
   MqlDateTime timeStruct;
   TimeToStruct(TimeCurrent(), timeStruct);

   int currentHour = timeStruct.hour;

   if(StartHour <= EndHour)
   {
      return (currentHour >= StartHour && currentHour <= EndHour);
   }
   else
   {
      // Handle overnight trading hours (e.g., 22:00 to 02:00)
      return (currentHour >= StartHour || currentHour <= EndHour);
   }
}

//+------------------------------------------------------------------+
//| Normalize price to symbol's digit precision                      |
//+------------------------------------------------------------------+
double NormalizePrice(double price)
{
   // Use cached symbol digits for better performance
   return NormalizeDouble(price, g_symbolDigits);
}

//+------------------------------------------------------------------+
//| Log trade to journal - OPTIMIZED with StringFormat               |
//+------------------------------------------------------------------+
void LogTrade(string direction, ulong ticket, double lotSize, double entryPrice, double sl, double tp)
{
   // Use StringFormat for better performance than string concatenation
   string logMessage = StringFormat(
      "========================================\n"
      "=== TRADE EXECUTED ===\n"
      "Time: %s\n"
      "Direction: %s\n"
      "Ticket: %I64u\n"
      "Symbol: %s\n"
      "Lot Size: %.2f\n"
      "Entry Price: %.*f\n"
      "Stop-Loss: %.*f\n"
      "Take-Profit: %.*f\n"
      "Risk: %.*f\n"
      "Potential Reward: %.*f\n"
      "R:R Ratio: 1:%.2f\n"
      "4H Candle High: %.*f\n"
      "4H Candle Low: %.*f\n"
      "Account Balance: %.2f\n"
      "========================================",
      TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS),
      direction,
      ticket,
      _Symbol,
      lotSize,
      _Digits, entryPrice,
      _Digits, sl,
      _Digits, tp,
      _Digits, MathAbs(entryPrice - sl),
      _Digits, MathAbs(tp - entryPrice),
      RiskRewardRatio,
      _Digits, g_4HHigh,
      _Digits, g_4HLow,
      AccountInfoDouble(ACCOUNT_BALANCE)
   );

   LogMessage(logMessage);
}

//+------------------------------------------------------------------+
//| Centralized logging function (optimized with persistent handle)  |
//+------------------------------------------------------------------+
void LogMessage(string message)
{
   string timestamp = TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS);
   string fullMessage = "[" + timestamp + "] " + message;

   // Print to console
   if(LogToConsole)
   {
      Print(fullMessage);
   }

   // Write to file using persistent handle (much faster than open/close each time)
   if(LogToFile)
   {
      // Open file handle if not already open
      if(g_logFileHandle == INVALID_HANDLE)
      {
         g_logFileHandle = FileOpen("FiveMinScalper_Log.txt", FILE_WRITE|FILE_READ|FILE_TXT|FILE_ANSI);
         if(g_logFileHandle != INVALID_HANDLE)
         {
            FileSeek(g_logFileHandle, 0, SEEK_END);
         }
         else
         {
            Print("ERROR: Failed to open log file. Error: ", GetLastError());
            return;
         }
      }

      // Write to file
      FileWriteString(g_logFileHandle, fullMessage + "\n");

      // Flush every 10 messages or every 5 seconds for safety
      static int messageCount = 0;
      static datetime lastFlush = 0;
      messageCount++;

      if(messageCount >= 10 || TimeCurrent() - lastFlush >= 5)
      {
         FileFlush(g_logFileHandle);
         messageCount = 0;
         lastFlush = TimeCurrent();
      }
   }
}

//+------------------------------------------------------------------+
//| Draw all levels on chart                                         |
//+------------------------------------------------------------------+
void DrawLevelsOnChart()
{
   LogMessage("Drawing levels on chart...");
   LogMessage("ShowLevelsOnChart = " + (ShowLevelsOnChart ? "true" : "false"));
   LogMessage("Values: 4HHigh=" + DoubleToString(g_4HHigh, _Digits) + ", 4HLow=" + DoubleToString(g_4HLow, _Digits));

   // Validate data before drawing
   if(g_4HHigh == 0 || g_4HLow == 0)
   {
      LogMessage("ERROR: Cannot draw lines - 4H candle data is zero");
      return;
   }

   // Delete old lines first
   DeleteAllChartObjects();
   LogMessage("Old chart objects deleted");

   // Draw 4H High line (SELL breakout level)
   CreateHorizontalLine("4H_High", g_4HHigh, Color4HHigh, LineWidth, LineStyle, "4H High (SELL Breakout): " + DoubleToString(g_4HHigh, _Digits));

   // Draw 4H Low line (BUY breakout level)
   CreateHorizontalLine("4H_Low", g_4HLow, Color4HLow, LineWidth, LineStyle, "4H Low (BUY Breakout): " + DoubleToString(g_4HLow, _Digits));

   LogMessage("All horizontal lines created");

   // Add info text
   CreateInfoText();
   LogMessage("Info text created");

   ChartRedraw();
   LogMessage("Chart redrawn - levels should now be visible");
}

//+------------------------------------------------------------------+
//| Create horizontal line - OPTIMIZED with tracking                 |
//+------------------------------------------------------------------+
void CreateHorizontalLine(string name, double price, color lineColor, int width, ENUM_LINE_STYLE style, string description)
{
   string objectName = "FMS_" + name;

   if(ObjectFind(0, objectName) >= 0)
   {
      ObjectDelete(0, objectName);
   }

   bool created = ObjectCreate(0, objectName, OBJ_HLINE, 0, 0, price);

   if(created)
   {
      // Batch property settings for better performance
      ObjectSetInteger(0, objectName, OBJPROP_COLOR, lineColor);
      ObjectSetInteger(0, objectName, OBJPROP_WIDTH, width);
      ObjectSetInteger(0, objectName, OBJPROP_STYLE, style);
      ObjectSetInteger(0, objectName, OBJPROP_BACK, false);
      ObjectSetInteger(0, objectName, OBJPROP_SELECTABLE, true);
      ObjectSetInteger(0, objectName, OBJPROP_SELECTED, false);
      ObjectSetString(0, objectName, OBJPROP_TEXT, description);
      ObjectSetString(0, objectName, OBJPROP_TOOLTIP, description);

      // Track the object for efficient deletion later
      TrackChartObject(objectName);

      LogMessage("Created line: " + objectName + " at price " + DoubleToString(price, _Digits));
   }
   else
   {
      int error = GetLastError();
      LogMessage("ERROR: Failed to create line " + objectName + " at price " + DoubleToString(price, _Digits) + ". Error: " + IntegerToString(error));
   }
}

//+------------------------------------------------------------------+
//| Create info text on chart                                        |
//+------------------------------------------------------------------+
void CreateInfoText()
{
   string objectName = "FMS_Info";

   // Delete existing object if it exists
   if(ObjectFind(0, objectName) >= 0)
   {
      LogMessage("Deleting existing info label...");
      if(!ObjectDelete(0, objectName))
      {
         LogMessage("WARNING: Failed to delete existing info label. Error: " + IntegerToString(GetLastError()));
      }
   }

   double range = g_4HHigh - g_4HLow;
   double rangePercent = (range / g_4HLow) * 100;

   // Use the actual 04:00 candle time we're trading with
   datetime displayTime = (g_processed04CandleTime > 0) ? g_processed04CandleTime : iTime(_Symbol, PERIOD_H4, 1);

   LogMessage("Creating info label with:");
   LogMessage("  Timestamp: " + TimeToString(displayTime, TIME_DATE|TIME_MINUTES) + " UTC");
   LogMessage("  4H High: " + DoubleToString(g_4HHigh, _Digits));
   LogMessage("  4H Low: " + DoubleToString(g_4HLow, _Digits));
   LogMessage("  Range: " + DoubleToString(range, _Digits) + " (" + DoubleToString(rangePercent, 2) + "%)");

   // Format timestamp more compactly
   MqlDateTime dt;
   TimeToStruct(displayTime, dt);
   string dateStr = StringFormat("%04d.%02d.%02d %02d:00", dt.year, dt.mon, dt.day, dt.hour);

   string infoText = "=== 5Min Scalper (False Breakout) ===\n";
   infoText += "4H Candle: " + dateStr + " UTC\n";
   infoText += "High: " + DoubleToString(g_4HHigh, _Digits) + "\n";
   infoText += "Low: " + DoubleToString(g_4HLow, _Digits) + "\n";
   infoText += "Range: " + DoubleToString(range, _Digits) + " (" + DoubleToString(rangePercent, 2) + "%)\n";
   infoText += "R:R: 1:" + DoubleToString(RiskRewardRatio, 1) + " | Risk: " + DoubleToString(RiskPercentPerTrade, 1) + "%\n";
   infoText += "\nBUY: Break below Low, reverse above\n";
   infoText += "SELL: Break above High, reverse below";

   // Create multiple label objects for each line (OBJ_LABEL doesn't support \n properly)
   string lines[];
   int lineCount = StringSplit(infoText, '\n', lines);

   int yOffset = 20;
   int lineHeight = 16;
   bool allCreated = true;

   for(int i = 0; i < lineCount; i++)
   {
      string lineObjectName = objectName + "_Line" + IntegerToString(i);

      // Delete if exists
      if(ObjectFind(0, lineObjectName) >= 0)
      {
         ObjectDelete(0, lineObjectName);
      }

      // Create new label for this line
      if(ObjectCreate(0, lineObjectName, OBJ_LABEL, 0, 0, 0))
      {
         // Batch property settings
         ObjectSetInteger(0, lineObjectName, OBJPROP_CORNER, CORNER_LEFT_UPPER);
         ObjectSetInteger(0, lineObjectName, OBJPROP_XDISTANCE, 10);
         ObjectSetInteger(0, lineObjectName, OBJPROP_YDISTANCE, yOffset + (i * lineHeight));
         ObjectSetInteger(0, lineObjectName, OBJPROP_COLOR, clrWhite);
         ObjectSetInteger(0, lineObjectName, OBJPROP_FONTSIZE, 9);
         ObjectSetString(0, lineObjectName, OBJPROP_FONT, "Courier New");
         ObjectSetString(0, lineObjectName, OBJPROP_TEXT, lines[i]);
         ObjectSetInteger(0, lineObjectName, OBJPROP_SELECTABLE, false);

         // Track the object
         TrackChartObject(lineObjectName);
      }
      else
      {
         allCreated = false;
         LogMessage("ERROR: Failed to create line " + IntegerToString(i) + ". Error: " + IntegerToString(GetLastError()));
      }
   }

   if(allCreated)
   {
      LogMessage("SUCCESS: Info panel created with " + IntegerToString(lineCount) + " lines");
   }
}

//+------------------------------------------------------------------+
//| Delete all chart objects - OPTIMIZED with tracking               |
//+------------------------------------------------------------------+
void DeleteAllChartObjects()
{
   // Use tracked objects for faster deletion
   int size = ArraySize(g_chartObjects);

   for(int i = 0; i < size; i++)
   {
      ObjectDelete(0, g_chartObjects[i]);
   }

   // Clear the tracking array
   ArrayResize(g_chartObjects, 0);
}

//+------------------------------------------------------------------+
//| Track created chart object                                       |
//+------------------------------------------------------------------+
void TrackChartObject(string objectName)
{
   int size = ArraySize(g_chartObjects);
   ArrayResize(g_chartObjects, size + 1);
   g_chartObjects[size] = objectName;
}




//+------------------------------------------------------------------+
//| Find the most recent first 4H candle of day                      |
//| NOTE: iTime() returns opening time (00:00)                       |
//|       Chart displays closing time (04:00)                        |
//+------------------------------------------------------------------+
datetime Find00UTCCandle()
{
   // Search backwards up to 24 hours (6 x 4H candles)
   for(int i = 1; i <= 6; i++)
   {
      datetime candleTime = iTime(_Symbol, PERIOD_H4, i);  // Returns opening time
      MqlDateTime timeStruct;
      TimeToStruct(candleTime, timeStruct);

      if(timeStruct.hour == 4)  // Opening time is 00:00 (chart shows 04:00)
      {
         return candleTime;  // Returns opening time (00:00)
      }
   }

   return 0;
}

//+------------------------------------------------------------------+
//| Find the index of the most recent first 4H candle of day         |
//| NOTE: iTime() returns opening time (00:00)                       |
//|       Chart displays closing time (04:00)                        |
//+------------------------------------------------------------------+
int Find00UTCCandleIndex()
{
   // Search backwards up to 24 hours (6 x 4H candles)
   for(int i = 1; i <= 6; i++)
   {
      datetime candleTime = iTime(_Symbol, PERIOD_H4, i);  // Returns opening time
      MqlDateTime timeStruct;
      TimeToStruct(candleTime, timeStruct);

      if(timeStruct.hour == 4)  // Opening time is 00:00 (chart shows 04:00)
      {
         return i;
      }
   }

   return 0;
}

//+------------------------------------------------------------------+
//| Update 4H data from specific candle index                        |
//+------------------------------------------------------------------+
void Update4HData(int candleIndex)
{
   g_4HHigh = iHigh(_Symbol, PERIOD_H4, candleIndex);
   g_4HLow = iLow(_Symbol, PERIOD_H4, candleIndex);
   double open = iOpen(_Symbol, PERIOD_H4, candleIndex);
   double close = iClose(_Symbol, PERIOD_H4, candleIndex);
   long volume4H = iVolume(_Symbol, PERIOD_H4, candleIndex);
   datetime closedCandleTime = iTime(_Symbol, PERIOD_H4, candleIndex);

   // Store opening time of first 4H candle (iTime returns opening time)
   if(UseOnly00UTCCandle)
   {
      g_processed04CandleTime = closedCandleTime;  // Stores opening time (00:00)
   }

   double range = g_4HHigh - g_4HLow;
   string candleType = (close > open) ? "Bullish" : (close < open) ? "Bearish" : "Doji";

   LogMessage("========================================");
   LogMessage("=== 4H DATA UPDATED ===");
   LogMessage("Candle Index: " + IntegerToString(candleIndex));
   LogMessage("Closed at: " + TimeToString(closedCandleTime, TIME_DATE|TIME_MINUTES) + " UTC");
   LogMessage("Candle Type: " + candleType);
   LogMessage("High: " + DoubleToString(g_4HHigh, _Digits));
   LogMessage("Low: " + DoubleToString(g_4HLow, _Digits));
   LogMessage("Range: " + DoubleToString(range, _Digits) + " (" + DoubleToString(range / g_4HLow * 100, 2) + "%)");
   LogMessage("Volume: " + IntegerToString(volume4H));

   // Reset tracking
   g_buyOrderPlaced = false;
   g_sellOrderPlaced = false;
   g_buyBreakoutConfirmed = false;
   g_buyReversalConfirmed = false;
   g_buyBreakoutCandleTime = 0;
   g_sellBreakoutConfirmed = false;
   g_sellReversalConfirmed = false;
   g_sellBreakoutCandleTime = 0;

   // Reset volume tracking
   g_buyBreakoutVolume = 0;
   g_buyReversalVolume = 0;
   g_sellBreakoutVolume = 0;
   g_sellReversalVolume = 0;
   g_averageVolume = 0;
   g_buyBreakoutVolumeOK = false;
   g_buyReversalVolumeOK = false;
   g_sellBreakoutVolumeOK = false;
   g_sellReversalVolumeOK = false;
   g_buyDivergenceOK = false;
   g_sellDivergenceOK = false;

   // Enable trading after updating 4H data
   g_tradingAllowedToday = true;
   LogMessage("TRADING ENABLED - 4H data updated");

   // Redraw chart
   if(ShowLevelsOnChart)
   {
      DrawLevelsOnChart();
   }

   LogMessage("========================================");
}


//+------------------------------------------------------------------+
//| Find the lowest low among BULLISH candles - OPTIMIZED            |
//| Analyzes up to 10 latest candles within breakout-to-reversal range|
//+------------------------------------------------------------------+
double FindLowestLowInRange(datetime startTime, datetime endTime)
{
   double lowestLow = DBL_MAX;
   int candlesAnalyzed = 0;
   int bullishCandles = 0;

   LogMessage("--- Finding Lowest Low in Latest Candles (Max 10) ---");
   LogMessage("Start Time: " + TimeToString(startTime, TIME_DATE|TIME_MINUTES));
   LogMessage("End Time (Reversal): " + TimeToString(endTime, TIME_DATE|TIME_MINUTES));
   LogMessage("Priority: BULLISH candles that closed below 4H Low");
   LogMessage("Fallback: ANY candles that closed below 4H Low if no bullish found");

   // Calculate how many candles to fetch based on time range
   // Time range in seconds / 300 seconds per 5-min candle + buffer
   int timeRangeSeconds = (int)(endTime - startTime);
   int candlesToFetch = MathMin(100, MathMax(5, (timeRangeSeconds / 300) + 5));

   LogMessage("Time range: " + IntegerToString(timeRangeSeconds) + " seconds (" +
             IntegerToString(timeRangeSeconds / 60) + " minutes)");
   LogMessage("Fetching " + IntegerToString(candlesToFetch) + " candles for analysis");

   // Use CopyRates for bulk data retrieval (much faster than individual calls)
   MqlRates rates[];
   int copied = CopyRates(_Symbol, PERIOD_M5, 1, candlesToFetch, rates);

   if(copied <= 0)
   {
      LogMessage("ERROR: Failed to copy rates. Error: " + IntegerToString(GetLastError()));
      return DBL_MAX;
   }

   LogMessage("Successfully copied " + IntegerToString(copied) + " candles");

   // CopyRates returns candles in chronological order:
   // rates[0] = most recent (bar index 1)
   // rates[copied-1] = oldest (bar index 1+copied-1)
   // We need to iterate through all of them to find those in our time range

   // FIRST PASS: Look for BULLISH candles that closed below 4H Low
   for(int i = 0; i < copied; i++)
   {
      datetime candleTime = rates[i].time;

      // Only process candles within our range
      if(candleTime >= startTime && candleTime <= endTime)
      {
         double candleOpen = rates[i].open;
         double candleClose = rates[i].close;
         double candleLow = rates[i].low;

         candlesAnalyzed++;

         // Only consider candles that closed BELOW 4H Low (in breakout zone)
         if(candleClose < g_4HLow)
         {
            // FIRST PASS: Only BULLISH candles
            if(candleClose > candleOpen)
            {
               bullishCandles++;

               if(candleLow < lowestLow)
               {
                  lowestLow = candleLow;
                  if(EnableDetailedLogging)
                     LogMessage("  Bullish candle at " + TimeToString(candleTime, TIME_MINUTES) +
                               " Low: " + DoubleToString(candleLow, _Digits) +
                               " (O:" + DoubleToString(candleOpen, _Digits) +
                               " C:" + DoubleToString(candleClose, _Digits) + ") - new lowest");
               }
               else if(EnableDetailedLogging)
               {
                  LogMessage("  Bullish candle at " + TimeToString(candleTime, TIME_MINUTES) +
                            " Low: " + DoubleToString(candleLow, _Digits));
               }
            }
         }
      }
   }

   // SECOND PASS: If no bullish candles found, use ANY candles that closed below 4H Low
   if(lowestLow == DBL_MAX)
   {
      LogMessage("No bullish candles found - using fallback: ANY candles that closed below 4H Low");

      for(int i = 0; i < copied; i++)
      {
         datetime candleTime = rates[i].time;

         if(candleTime >= startTime && candleTime <= endTime)
         {
            double candleOpen = rates[i].open;
            double candleClose = rates[i].close;
            double candleLow = rates[i].low;

            // Use ANY candle that closed below 4H Low (including bearish)
            if(candleClose < g_4HLow)
            {
               if(candleLow < lowestLow)
               {
                  lowestLow = candleLow;
                  bool isBullish = (candleClose > candleOpen);
                  if(EnableDetailedLogging)
                     LogMessage("  " + (isBullish ? "Bullish" : "Bearish") + " candle at " + TimeToString(candleTime, TIME_MINUTES) +
                               " Low: " + DoubleToString(candleLow, _Digits) +
                               " (O:" + DoubleToString(candleOpen, _Digits) +
                               " C:" + DoubleToString(candleClose, _Digits) + ") - new lowest");
               }
            }
         }
      }
   }

   LogMessage("Analyzed " + IntegerToString(candlesAnalyzed) + " total candles in time range");
   LogMessage("Found " + IntegerToString(bullishCandles) + " bullish candles that closed below 4H Low");
   LogMessage("4H Low reference: " + DoubleToString(g_4HLow, _Digits));

   if(lowestLow != DBL_MAX)
   {
      if(bullishCandles > 0)
         LogMessage("Lowest Low from bullish candles: " + DoubleToString(lowestLow, _Digits));
      else
         LogMessage("Lowest Low from fallback (any candles): " + DoubleToString(lowestLow, _Digits));
   }
   else
   {
      LogMessage("WARNING: No candles found that closed below 4H Low");
      LogMessage("Pattern does not meet criteria for BUY signal");
   }

   return lowestLow;
}

//+------------------------------------------------------------------+
//| Find the highest high among BEARISH candles - OPTIMIZED          |
//| Analyzes up to 10 latest candles within breakout-to-reversal range|
//+------------------------------------------------------------------+
double FindHighestHighInRange(datetime startTime, datetime endTime)
{
   double highestHigh = 0;
   int candlesAnalyzed = 0;
   int bearishCandles = 0;

   LogMessage("--- Finding Highest High in Latest Candles (Max 10) ---");
   LogMessage("Start Time: " + TimeToString(startTime, TIME_DATE|TIME_MINUTES));
   LogMessage("End Time (Reversal): " + TimeToString(endTime, TIME_DATE|TIME_MINUTES));
   LogMessage("Priority: BEARISH candles that closed above 4H High");
   LogMessage("Fallback: ANY candles that closed above 4H High if no bearish found");

   // Calculate how many candles to fetch based on time range
   // Time range in seconds / 300 seconds per 5-min candle + buffer
   int timeRangeSeconds = (int)(endTime - startTime);
   int candlesToFetch = MathMin(100, MathMax(5, (timeRangeSeconds / 300) + 5));

   LogMessage("Time range: " + IntegerToString(timeRangeSeconds) + " seconds (" +
             IntegerToString(timeRangeSeconds / 60) + " minutes)");
   LogMessage("Fetching " + IntegerToString(candlesToFetch) + " candles for analysis");

   // Use CopyRates for bulk data retrieval (much faster than individual calls)
   MqlRates rates[];
   int copied = CopyRates(_Symbol, PERIOD_M5, 1, candlesToFetch, rates);

   if(copied <= 0)
   {
      LogMessage("ERROR: Failed to copy rates. Error: " + IntegerToString(GetLastError()));
      return 0;
   }

   LogMessage("Successfully copied " + IntegerToString(copied) + " candles");

   // CopyRates returns candles in chronological order:
   // rates[0] = most recent (bar index 1)
   // rates[copied-1] = oldest (bar index 1+copied-1)
   // We need to iterate through all of them to find those in our time range

   // FIRST PASS: Look for BEARISH candles that closed above 4H High
   for(int i = 0; i < copied; i++)
   {
      datetime candleTime = rates[i].time;

      // Only process candles within our range
      if(candleTime >= startTime && candleTime <= endTime)
      {
         double candleOpen = rates[i].open;
         double candleClose = rates[i].close;
         double candleHigh = rates[i].high;

         candlesAnalyzed++;

         // Only consider candles that closed ABOVE 4H High (in breakout zone)
         if(candleClose > g_4HHigh)
         {
            // FIRST PASS: Only BEARISH candles
            if(candleClose < candleOpen)
            {
               bearishCandles++;

               if(candleHigh > highestHigh)
               {
                  highestHigh = candleHigh;
                  if(EnableDetailedLogging)
                     LogMessage("  Bearish candle at " + TimeToString(candleTime, TIME_MINUTES) +
                               " High: " + DoubleToString(candleHigh, _Digits) +
                               " (O:" + DoubleToString(candleOpen, _Digits) +
                               " C:" + DoubleToString(candleClose, _Digits) + ") - new highest");
               }
               else if(EnableDetailedLogging)
               {
                  LogMessage("  Bearish candle at " + TimeToString(candleTime, TIME_MINUTES) +
                            " High: " + DoubleToString(candleHigh, _Digits));
               }
            }
         }
      }
   }

   // SECOND PASS: If no bearish candles found, use ANY candles that closed above 4H High
   if(highestHigh == 0)
   {
      LogMessage("No bearish candles found - using fallback: ANY candles that closed above 4H High");

      for(int i = 0; i < copied; i++)
      {
         datetime candleTime = rates[i].time;

         if(candleTime >= startTime && candleTime <= endTime)
         {
            double candleOpen = rates[i].open;
            double candleClose = rates[i].close;
            double candleHigh = rates[i].high;

            // Use ANY candle that closed above 4H High (including bullish)
            if(candleClose > g_4HHigh)
            {
               if(candleHigh > highestHigh)
               {
                  highestHigh = candleHigh;
                  bool isBearish = (candleClose < candleOpen);
                  if(EnableDetailedLogging)
                     LogMessage("  " + (isBearish ? "Bearish" : "Bullish") + " candle at " + TimeToString(candleTime, TIME_MINUTES) +
                               " High: " + DoubleToString(candleHigh, _Digits) +
                               " (O:" + DoubleToString(candleOpen, _Digits) +
                               " C:" + DoubleToString(candleClose, _Digits) + ") - new highest");
               }
            }
         }
      }
   }

   LogMessage("Analyzed " + IntegerToString(candlesAnalyzed) + " total candles in time range");
   LogMessage("Found " + IntegerToString(bearishCandles) + " bearish candles that closed above 4H High");
   LogMessage("4H High reference: " + DoubleToString(g_4HHigh, _Digits));

   if(highestHigh > 0)
   {
      if(bearishCandles > 0)
         LogMessage("Highest High from bearish candles: " + DoubleToString(highestHigh, _Digits));
      else
         LogMessage("Highest High from fallback (any candles): " + DoubleToString(highestHigh, _Digits));
   }
   else
   {
      LogMessage("WARNING: No candles found that closed above 4H High");
      LogMessage("Pattern does not meet criteria for SELL signal");
   }

   return highestHigh;
}

//+------------------------------------------------------------------+
//| Calculate average volume over a specified period                 |
//+------------------------------------------------------------------+
double CalculateAverageVolume(int period)
{
   if(period <= 0)
   {
      LogMessage("ERROR: Invalid period for volume calculation: " + IntegerToString(period));
      return 0;
   }

   // Get volume data for the specified period
   // We use index 1 to start from the last closed candle
   long volumes[];
   int copied = CopyTickVolume(_Symbol, PERIOD_M5, 1, period, volumes);

   if(copied <= 0)
   {
      LogMessage("ERROR: Failed to copy volume data. Error: " + IntegerToString(GetLastError()));
      return 0;
   }

   // Calculate average
   long totalVolume = 0;
   for(int i = 0; i < copied; i++)
   {
      totalVolume += volumes[i];
   }

   double avgVolume = (double)totalVolume / copied;

   if(EnableDetailedLogging)
   {
      LogMessage("Volume Analysis:");
      LogMessage("  Period: " + IntegerToString(period) + " candles");
      LogMessage("  Candles copied: " + IntegerToString(copied));
      LogMessage("  Total volume: " + IntegerToString(totalVolume));
      LogMessage("  Average volume: " + DoubleToString(avgVolume, 0));
   }

   return avgVolume;
}

//+------------------------------------------------------------------+
//| Get volume for a specific candle by index                        |
//+------------------------------------------------------------------+
long GetCandleVolume(int candleIndex)
{
   long volume = iVolume(_Symbol, PERIOD_M5, candleIndex);

   if(volume < 0)
   {
      LogMessage("ERROR: Failed to get volume for candle index " + IntegerToString(candleIndex));
      return 0;
   }

   return volume;
}

//+------------------------------------------------------------------+
//| Check if breakout volume is LOW (weak breakout = good for false breakout strategy) |
//+------------------------------------------------------------------+
bool IsBreakoutVolumeLow(long breakoutVolume, double averageVolume, double maxThreshold)
{
   if(averageVolume <= 0)
   {
      LogMessage("WARNING: Average volume is zero or negative - cannot confirm volume");
      return false;
   }

   double volumeRatio = (double)breakoutVolume / averageVolume;
   bool isLow = volumeRatio <= maxThreshold;

   LogMessage("=== Breakout Volume Check (Want LOW Volume) ===");
   LogMessage("Breakout Volume: " + IntegerToString(breakoutVolume));
   LogMessage("Average Volume: " + DoubleToString(averageVolume, 0));
   LogMessage("Volume Ratio: " + DoubleToString(volumeRatio, 2) + "x");
   LogMessage("Max Threshold: " + DoubleToString(maxThreshold, 2) + "x");
   LogMessage("Volume is LOW: " + (isLow ? "YES" : "NO"));

   if(!isLow)
   {
      LogMessage(">>> VOLUME TOO HIGH - Strong breakout, likely to continue <<<");
      LogMessage(">>> Not ideal for false breakout strategy - skipping <<<");
   }
   else
   {
      LogMessage(">>> VOLUME IS LOW - Weak breakout, likely to reverse <<<");
      LogMessage(">>> Good candidate for false breakout - proceeding <<<");
   }

   return isLow;
}

//+------------------------------------------------------------------+
//| Check if reversal volume is HIGH (strong reversal = good confirmation) |
//+------------------------------------------------------------------+
bool IsReversalVolumeHigh(long reversalVolume, double averageVolume, double minThreshold)
{
   if(averageVolume <= 0)
   {
      LogMessage("WARNING: Average volume is zero or negative - cannot confirm volume");
      return false;
   }

   double volumeRatio = (double)reversalVolume / averageVolume;
   bool isHigh = volumeRatio >= minThreshold;

   LogMessage("=== Reversal Volume Check (Want HIGH Volume) ===");
   LogMessage("Reversal Volume: " + IntegerToString(reversalVolume));
   LogMessage("Average Volume: " + DoubleToString(averageVolume, 0));
   LogMessage("Volume Ratio: " + DoubleToString(volumeRatio, 2) + "x");
   LogMessage("Min Threshold: " + DoubleToString(minThreshold, 2) + "x");
   LogMessage("Volume is HIGH: " + (isHigh ? "YES" : "NO"));

   if(!isHigh)
   {
      LogMessage(">>> VOLUME TOO LOW - Weak reversal, lacks conviction <<<");
      LogMessage(">>> May not be a strong false breakout - skipping <<<");
   }
   else
   {
      LogMessage(">>> VOLUME IS HIGH - Strong reversal confirmation <<<");
      LogMessage(">>> Excellent false breakout signal - proceeding <<<");
   }

   return isHigh;
}



//+------------------------------------------------------------------+
//| Calculate optimized stop-loss for BUY order                      |
//+------------------------------------------------------------------+
double CalculateOptimizedBuySL(double lowestLow, double entryPrice, datetime breakoutTime, datetime reversalTime)
{
   // Calculate SL using the lowest low with offset
   double stopLoss = lowestLow - (lowestLow * StopLossOffsetPercent / 100.0);
   double risk = entryPrice - stopLoss;

   LogMessage("=== Calculating BUY Stop-Loss ===");
   LogMessage("Entry Price: " + DoubleToString(entryPrice, _Digits));
   LogMessage("Lowest Low in pattern: " + DoubleToString(lowestLow, _Digits));
   LogMessage("Stop-Loss: " + DoubleToString(stopLoss, _Digits));
   LogMessage("Risk: " + DoubleToString(risk, _Digits));

   return stopLoss;
}

//+------------------------------------------------------------------+
//| Calculate optimized stop-loss for SELL order                     |
//+------------------------------------------------------------------+
double CalculateOptimizedSellSL(double highestHigh, double entryPrice, datetime breakoutTime, datetime reversalTime)
{
   // Calculate SL using the highest high with offset
   double stopLoss = highestHigh + (highestHigh * StopLossOffsetPercent / 100.0);
   double risk = stopLoss - entryPrice;

   LogMessage("=== Calculating SELL Stop-Loss ===");
   LogMessage("Entry Price: " + DoubleToString(entryPrice, _Digits));
   LogMessage("Highest High in pattern: " + DoubleToString(highestHigh, _Digits));
   LogMessage("Stop-Loss: " + DoubleToString(stopLoss, _Digits));
   LogMessage("Risk: " + DoubleToString(risk, _Digits));

   return stopLoss;
}



//+------------------------------------------------------------------+
//| Export candle data to CSV file for verification                  |
//+------------------------------------------------------------------+
void ExportCandleToCSV(datetime time, double open, double high, double low, double close)
{
   static int csvHandle = INVALID_HANDLE;
   static bool headerWritten = false;

   // Create CSV filename with symbol and date
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   string filename = StringFormat("CandleData_%s_%04d%02d%02d.csv",
                                  _Symbol, dt.year, dt.mon, dt.day);

   // Open file for writing (append mode)
   if(csvHandle == INVALID_HANDLE)
   {
      csvHandle = FileOpen(filename, FILE_WRITE|FILE_CSV|FILE_ANSI, ',');

      if(csvHandle == INVALID_HANDLE)
      {
         LogMessage("ERROR: Failed to create CSV file: " + filename);
         return;
      }

      LogMessage("CSV Export: Created file " + filename);
   }

   // Write header on first call
   if(!headerWritten)
   {
      FileWrite(csvHandle, "DateTime", "Open", "High", "Low", "Close", "4H_High", "4H_Low", "Status");
      headerWritten = true;
   }

   // Determine status
   string status = "INSIDE";
   if(close < g_4HLow)
      status = "BELOW_4H_LOW";
   else if(close > g_4HHigh)
      status = "ABOVE_4H_HIGH";

   // Write candle data
   FileWrite(csvHandle,
             TimeToString(time, TIME_DATE|TIME_MINUTES),
             DoubleToString(open, _Digits),
             DoubleToString(high, _Digits),
             DoubleToString(low, _Digits),
             DoubleToString(close, _Digits),
             DoubleToString(g_4HHigh, _Digits),
             DoubleToString(g_4HLow, _Digits),
             status);

   FileFlush(csvHandle);
}

//+------------------------------------------------------------------+
//| Log all active trades for this EA                                |
//+------------------------------------------------------------------+
void LogActiveTrades()
{
   int totalPositions = PositionsTotal();
   int eaPositions = 0;
   bool hasBuyPosition = false;
   bool hasSellPosition = false;

   LogMessage("=== ACTIVE TRADES CHECK ===");
   LogMessage("Total positions in account: " + IntegerToString(totalPositions));

   // First, count EA positions and check what types exist
   for(int i = 0; i < totalPositions; i++)
   {
      if(PositionGetSymbol(i) == _Symbol &&
         PositionGetInteger(POSITION_MAGIC) == MagicNumber)
      {
         eaPositions++;
         ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

         if(type == POSITION_TYPE_BUY)
            hasBuyPosition = true;
         else if(type == POSITION_TYPE_SELL)
            hasSellPosition = true;
      }
   }

   // Auto-correct flags if no positions exist
   bool flagsCorrected = false;

   if(!hasBuyPosition && g_buyOrderPlaced)
   {
      LogMessage("*** AUTO-CORRECTION: No BUY position exists but g_buyOrderPlaced = TRUE ***");
      LogMessage("Resetting g_buyOrderPlaced to FALSE");
      g_buyOrderPlaced = false;
      flagsCorrected = true;
   }

   if(!hasSellPosition && g_sellOrderPlaced)
   {
      LogMessage("*** AUTO-CORRECTION: No SELL position exists but g_sellOrderPlaced = TRUE ***");
      LogMessage("Resetting g_sellOrderPlaced to FALSE");
      g_sellOrderPlaced = false;
      flagsCorrected = true;
   }

   if(flagsCorrected)
   {
      LogMessage("Flags have been auto-corrected - EA can now check for new signals");
   }

   if(eaPositions == 0)
   {
      LogMessage("No EA positions for this symbol");
      LogMessage("g_buyOrderPlaced: " + (g_buyOrderPlaced ? "TRUE" : "FALSE"));
      LogMessage("g_sellOrderPlaced: " + (g_sellOrderPlaced ? "TRUE" : "FALSE"));
      LogMessage("===========================");
      return;
   }

   // Now log detailed information for each EA position
   LogMessage("EA has " + IntegerToString(eaPositions) + " active position(s)");

   int positionCount = 0;
   for(int i = 0; i < totalPositions; i++)
   {
      if(PositionGetSymbol(i) == _Symbol &&
         PositionGetInteger(POSITION_MAGIC) == MagicNumber)
      {
         positionCount++;

         ulong ticket = PositionGetInteger(POSITION_TICKET);
         ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
         double volume = PositionGetDouble(POSITION_VOLUME);
         double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
         double currentPrice = (type == POSITION_TYPE_BUY) ?
                               SymbolInfoDouble(_Symbol, SYMBOL_BID) :
                               SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double sl = PositionGetDouble(POSITION_SL);
         double tp = PositionGetDouble(POSITION_TP);
         double profit = PositionGetDouble(POSITION_PROFIT);
         datetime openTime = (datetime)PositionGetInteger(POSITION_TIME);

         string typeStr = (type == POSITION_TYPE_BUY) ? "BUY" : "SELL";

         LogMessage("--- Position #" + IntegerToString(positionCount) + " ---");
         LogMessage("Ticket: " + IntegerToString(ticket));
         LogMessage("Type: " + typeStr);
         LogMessage("Volume: " + DoubleToString(volume, 2));
         LogMessage("Open Price: " + DoubleToString(openPrice, _Digits));
         LogMessage("Current Price: " + DoubleToString(currentPrice, _Digits));
         LogMessage("Stop Loss: " + DoubleToString(sl, _Digits));
         LogMessage("Take Profit: " + (tp > 0 ? DoubleToString(tp, _Digits) : "None"));
         LogMessage("Profit: " + DoubleToString(profit, 2) + " " + AccountInfoString(ACCOUNT_CURRENCY));
         LogMessage("Open Time: " + TimeToString(openTime, TIME_DATE|TIME_MINUTES));

         // Calculate R:R
         double risk = MathAbs(openPrice - sl);
         double currentPnL = (type == POSITION_TYPE_BUY) ?
                            (currentPrice - openPrice) :
                            (openPrice - currentPrice);
         double currentRR = (risk > 0) ? (currentPnL / risk) : 0;

         LogMessage("Current R:R: " + DoubleToString(currentRR, 2));
      }
   }

   LogMessage("EA Positions: " + IntegerToString(eaPositions) + " / " + IntegerToString(totalPositions));
   LogMessage("g_buyOrderPlaced: " + (g_buyOrderPlaced ? "TRUE" : "FALSE"));
   LogMessage("g_sellOrderPlaced: " + (g_sellOrderPlaced ? "TRUE" : "FALSE"));
   LogMessage("===========================");
}

//+------------------------------------------------------------------+
//| Detect bullish RSI divergence (for BUY setup)                    |
//| Price makes lower low, but RSI makes higher low                  |
//| This indicates weakening downward momentum = likely to reverse   |
//+------------------------------------------------------------------+
bool DetectBullishRSIDivergence()
{
   if(g_rsiHandle == INVALID_HANDLE)
      return false;

   // Get RSI values for lookback period
   double rsiValues[];
   ArraySetAsSeries(rsiValues, true);

   int copied = CopyBuffer(g_rsiHandle, 0, 0, g_symbolParams.divergenceLookback + 1, rsiValues);
   if(copied <= 0)
   {
      LogMessage("ERROR: Failed to copy RSI data. Error: " + IntegerToString(GetLastError()));
      return false;
   }

   // Get price lows for lookback period
   double lows[];
   ArraySetAsSeries(lows, true);

   copied = CopyLow(_Symbol, PERIOD_M5, 0, g_symbolParams.divergenceLookback + 1, lows);
   if(copied <= 0)
   {
      LogMessage("ERROR: Failed to copy price lows. Error: " + IntegerToString(GetLastError()));
      return false;
   }

   // Find the most recent swing low (excluding current candle at index 0)
   // Look for a low that is lower than its neighbors
   int recentLowIndex = -1;
   for(int i = 2; i < g_symbolParams.divergenceLookback - 1; i++)
   {
      if(lows[i] < lows[i-1] && lows[i] < lows[i+1])
      {
         recentLowIndex = i;
         break;
      }
   }

   if(recentLowIndex == -1)
   {
      if(EnableDetailedLogging)
         LogMessage("No swing low found in lookback period");
      return false;
   }

   // Current price low (index 1 = last closed candle)
   double currentLow = lows[1];
   double previousLow = lows[recentLowIndex];

   // Current RSI and previous RSI at swing low
   double currentRSI = rsiValues[1];
   double previousRSI = rsiValues[recentLowIndex];

   // Bullish divergence: Price makes lower low, RSI makes higher low
   bool priceLowerLow = (currentLow < previousLow);
   bool rsiHigherLow = (currentRSI > previousRSI);

   if(priceLowerLow && rsiHigherLow)
   {
      LogMessage("*** BULLISH RSI DIVERGENCE DETECTED ***");
      LogMessage("Price: " + DoubleToString(previousLow, _Digits) + " -> " + DoubleToString(currentLow, _Digits) + " (Lower Low)");
      LogMessage("RSI: " + DoubleToString(previousRSI, 2) + " -> " + DoubleToString(currentRSI, 2) + " (Higher Low)");
      LogMessage("Swing low found at index " + IntegerToString(recentLowIndex) + " (" + IntegerToString(recentLowIndex * 5) + " minutes ago)");
      return true;
   }

   if(EnableDetailedLogging)
   {
      LogMessage("No bullish RSI divergence:");
      LogMessage("  Price Lower Low: " + (priceLowerLow ? "YES" : "NO"));
      LogMessage("  RSI Higher Low: " + (rsiHigherLow ? "YES" : "NO"));
   }

   return false;
}

//+------------------------------------------------------------------+
//| Detect bearish RSI divergence (for SELL setup)                   |
//| Price makes higher high, but RSI makes lower high                |
//| This indicates weakening upward momentum = likely to reverse     |
//+------------------------------------------------------------------+
bool DetectBearishRSIDivergence()
{
   if(g_rsiHandle == INVALID_HANDLE)
      return false;

   // Get RSI values for lookback period
   double rsiValues[];
   ArraySetAsSeries(rsiValues, true);

   int copied = CopyBuffer(g_rsiHandle, 0, 0, g_symbolParams.divergenceLookback + 1, rsiValues);
   if(copied <= 0)
   {
      LogMessage("ERROR: Failed to copy RSI data. Error: " + IntegerToString(GetLastError()));
      return false;
   }

   // Get price highs for lookback period
   double highs[];
   ArraySetAsSeries(highs, true);

   copied = CopyHigh(_Symbol, PERIOD_M5, 0, g_symbolParams.divergenceLookback + 1, highs);
   if(copied <= 0)
   {
      LogMessage("ERROR: Failed to copy price highs. Error: " + IntegerToString(GetLastError()));
      return false;
   }

   // Find the most recent swing high (excluding current candle at index 0)
   // Look for a high that is higher than its neighbors
   int recentHighIndex = -1;
   for(int i = 2; i < g_symbolParams.divergenceLookback - 1; i++)
   {
      if(highs[i] > highs[i-1] && highs[i] > highs[i+1])
      {
         recentHighIndex = i;
         break;
      }
   }

   if(recentHighIndex == -1)
   {
      if(EnableDetailedLogging)
         LogMessage("No swing high found in lookback period");
      return false;
   }

   // Current price high (index 1 = last closed candle)
   double currentHigh = highs[1];
   double previousHigh = highs[recentHighIndex];

   // Current RSI and previous RSI at swing high
   double currentRSI = rsiValues[1];
   double previousRSI = rsiValues[recentHighIndex];

   // Bearish divergence: Price makes higher high, RSI makes lower high
   bool priceHigherHigh = (currentHigh > previousHigh);
   bool rsiLowerHigh = (currentRSI < previousRSI);

   if(priceHigherHigh && rsiLowerHigh)
   {
      LogMessage("*** BEARISH RSI DIVERGENCE DETECTED ***");
      LogMessage("Price: " + DoubleToString(previousHigh, _Digits) + " -> " + DoubleToString(currentHigh, _Digits) + " (Higher High)");
      LogMessage("RSI: " + DoubleToString(previousRSI, 2) + " -> " + DoubleToString(currentRSI, 2) + " (Lower High)");
      LogMessage("Swing high found at index " + IntegerToString(recentHighIndex) + " (" + IntegerToString(recentHighIndex * 5) + " minutes ago)");
      return true;
   }

   if(EnableDetailedLogging)
   {
      LogMessage("No bearish RSI divergence:");
      LogMessage("  Price Higher High: " + (priceHigherHigh ? "YES" : "NO"));
      LogMessage("  RSI Lower High: " + (rsiLowerHigh ? "YES" : "NO"));
   }

   return false;
}


//+------------------------------------------------------------------+
//| Detect bullish MACD divergence (for BUY setup)                   |
//| Price makes lower low, but MACD makes higher low                 |
//| This indicates weakening downward momentum = likely to reverse   |
//+------------------------------------------------------------------+
bool DetectBullishMACDDivergence()
{
   if(g_macdHandle == INVALID_HANDLE)
      return false;

   // Get MACD main line values for lookback period
   double macdValues[];
   ArraySetAsSeries(macdValues, true);

   int copied = CopyBuffer(g_macdHandle, 0, 0, g_symbolParams.divergenceLookback + 1, macdValues);
   if(copied <= 0)
   {
      LogMessage("ERROR: Failed to copy MACD data. Error: " + IntegerToString(GetLastError()));
      return false;
   }

   // Get price lows for lookback period
   double lows[];
   ArraySetAsSeries(lows, true);

   copied = CopyLow(_Symbol, PERIOD_M5, 0, g_symbolParams.divergenceLookback + 1, lows);
   if(copied <= 0)
   {
      LogMessage("ERROR: Failed to copy price lows. Error: " + IntegerToString(GetLastError()));
      return false;
   }

   // Find the most recent swing low (excluding current candle at index 0)
   int recentLowIndex = -1;
   for(int i = 2; i < g_symbolParams.divergenceLookback - 1; i++)
   {
      if(lows[i] < lows[i-1] && lows[i] < lows[i+1])
      {
         recentLowIndex = i;
         break;
      }
   }

   if(recentLowIndex == -1)
   {
      if(EnableDetailedLogging)
         LogMessage("No swing low found for MACD divergence");
      return false;
   }

   // Current price low and MACD (index 1 = last closed candle)
   double currentLow = lows[1];
   double previousLow = lows[recentLowIndex];
   double currentMACD = macdValues[1];
   double previousMACD = macdValues[recentLowIndex];

   // Bullish divergence: Price makes lower low, MACD makes higher low
   bool priceLowerLow = (currentLow < previousLow);
   bool macdHigherLow = (currentMACD > previousMACD);

   if(priceLowerLow && macdHigherLow)
   {
      LogMessage("*** BULLISH MACD DIVERGENCE DETECTED ***");
      LogMessage("Price: " + DoubleToString(previousLow, _Digits) + " -> " + DoubleToString(currentLow, _Digits) + " (Lower Low)");
      LogMessage("MACD: " + DoubleToString(previousMACD, 5) + " -> " + DoubleToString(currentMACD, 5) + " (Higher Low)");
      LogMessage("Swing low found at index " + IntegerToString(recentLowIndex) + " (" + IntegerToString(recentLowIndex * 5) + " minutes ago)");
      return true;
   }

   if(EnableDetailedLogging)
   {
      LogMessage("No bullish MACD divergence:");
      LogMessage("  Price Lower Low: " + (priceLowerLow ? "YES" : "NO"));
      LogMessage("  MACD Higher Low: " + (macdHigherLow ? "YES" : "NO"));
   }

   return false;
}

//+------------------------------------------------------------------+
//| Detect bearish MACD divergence (for SELL setup)                  |
//| Price makes higher high, but MACD makes lower high               |
//| This indicates weakening upward momentum = likely to reverse     |
//+------------------------------------------------------------------+
bool DetectBearishMACDDivergence()
{
   if(g_macdHandle == INVALID_HANDLE)
      return false;

   // Get MACD main line values for lookback period
   double macdValues[];
   ArraySetAsSeries(macdValues, true);

   int copied = CopyBuffer(g_macdHandle, 0, 0, g_symbolParams.divergenceLookback + 1, macdValues);
   if(copied <= 0)
   {
      LogMessage("ERROR: Failed to copy MACD data. Error: " + IntegerToString(GetLastError()));
      return false;
   }

   // Get price highs for lookback period
   double highs[];
   ArraySetAsSeries(highs, true);

   copied = CopyHigh(_Symbol, PERIOD_M5, 0, g_symbolParams.divergenceLookback + 1, highs);
   if(copied <= 0)
   {
      LogMessage("ERROR: Failed to copy price highs. Error: " + IntegerToString(GetLastError()));
      return false;
   }

   // Find the most recent swing high (excluding current candle at index 0)
   int recentHighIndex = -1;
   for(int i = 2; i < g_symbolParams.divergenceLookback - 1; i++)
   {
      if(highs[i] > highs[i-1] && highs[i] > highs[i+1])
      {
         recentHighIndex = i;
         break;
      }
   }

   if(recentHighIndex == -1)
   {
      if(EnableDetailedLogging)
         LogMessage("No swing high found for MACD divergence");
      return false;
   }

   // Current price high and MACD (index 1 = last closed candle)
   double currentHigh = highs[1];
   double previousHigh = highs[recentHighIndex];
   double currentMACD = macdValues[1];
   double previousMACD = macdValues[recentHighIndex];

   // Bearish divergence: Price makes higher high, MACD makes lower high
   bool priceHigherHigh = (currentHigh > previousHigh);
   bool macdLowerHigh = (currentMACD < previousMACD);

   if(priceHigherHigh && macdLowerHigh)
   {
      LogMessage("*** BEARISH MACD DIVERGENCE DETECTED ***");
      LogMessage("Price: " + DoubleToString(previousHigh, _Digits) + " -> " + DoubleToString(currentHigh, _Digits) + " (Higher High)");
      LogMessage("MACD: " + DoubleToString(previousMACD, 5) + " -> " + DoubleToString(currentMACD, 5) + " (Lower High)");
      LogMessage("Swing high found at index " + IntegerToString(recentHighIndex) + " (" + IntegerToString(recentHighIndex * 5) + " minutes ago)");
      return true;
   }

   if(EnableDetailedLogging)
   {
      LogMessage("No bearish MACD divergence:");
      LogMessage("  Price Higher High: " + (priceHigherHigh ? "YES" : "NO"));
      LogMessage("  MACD Lower High: " + (macdLowerHigh ? "YES" : "NO"));
   }

   return false;
}

//+------------------------------------------------------------------+
//| Process closed trade and update adaptive filter system           |
//| Called when a trade closes to track win/loss and adjust filters  |
//| Parameter: positionId - the position ID (not deal ticket)        |
//+------------------------------------------------------------------+
void ProcessClosedTrade(ulong positionId)
{
   if(!UseAdaptiveFilters)
      return;

   // Avoid processing the same trade twice
   if(positionId == g_lastClosedTicket)
      return;

   g_lastClosedTicket = positionId;

   // Select the position from history
   if(!HistorySelectByPosition(positionId))
   {
      LogMessage("ERROR: Failed to select position " + IntegerToString(positionId) + " from history");
      return;
   }

   // Calculate total P&L for this position by summing all deals
   double totalProfit = 0;
   double totalSwap = 0;
   double totalCommission = 0;

   int totalDeals = HistoryDealsTotal();
   for(int i = 0; i < totalDeals; i++)
   {
      ulong dealTicket = HistoryDealGetTicket(i);
      if(dealTicket == 0)
         continue;

      long dealPosition = HistoryDealGetInteger(dealTicket, DEAL_POSITION_ID);
      if(dealPosition != (long)positionId)
         continue;

      totalProfit += HistoryDealGetDouble(dealTicket, DEAL_PROFIT);
      totalSwap += HistoryDealGetDouble(dealTicket, DEAL_SWAP);
      totalCommission += HistoryDealGetDouble(dealTicket, DEAL_COMMISSION);
   }

   double totalPnL = totalProfit + totalSwap + totalCommission;

   // Determine if trade was a win or loss
   bool isWin = (totalPnL > 0);

   LogMessage("=== ADAPTIVE FILTER: Trade Closed ===");
   LogMessage("Position ID: " + IntegerToString(positionId));
   LogMessage("Profit: " + DoubleToString(totalProfit, 2));
   LogMessage("Swap: " + DoubleToString(totalSwap, 2));
   LogMessage("Commission: " + DoubleToString(totalCommission, 2));
   LogMessage("Total P&L: " + DoubleToString(totalPnL, 2));
   LogMessage("Result: " + (isWin ? "WIN" : "LOSS"));

   if(isWin)
   {
      // Reset consecutive losses
      g_consecutiveLosses = 0;

      // If adaptive mode is active, count consecutive wins
      if(g_adaptiveModeActive)
      {
         g_consecutiveWins++;
         LogMessage("Consecutive Wins (Adaptive Mode): " + IntegerToString(g_consecutiveWins) + " / " + IntegerToString(g_symbolParams.adaptiveWinRecovery));

         // Check if we should deactivate adaptive mode (using symbol-specific trigger)
         if(g_consecutiveWins >= g_symbolParams.adaptiveWinRecovery)
         {
            DeactivateAdaptiveFilters();
         }
      }
      else
      {
         LogMessage("Consecutive Losses Reset: 0");
      }
   }
   else // Loss
   {
      // Reset consecutive wins
      g_consecutiveWins = 0;

      // Count consecutive losses
      g_consecutiveLosses++;
      LogMessage("Consecutive Losses: " + IntegerToString(g_consecutiveLosses) + " / " + IntegerToString(g_symbolParams.adaptiveLossTrigger));

      // Check if we should activate adaptive mode (using symbol-specific trigger)
      if(!g_adaptiveModeActive && g_consecutiveLosses >= g_symbolParams.adaptiveLossTrigger)
      {
         ActivateAdaptiveFilters();
      }
   }

   LogMessage("Adaptive Mode Active: " + (g_adaptiveModeActive ? "YES" : "NO"));
   LogMessage("=====================================");
}

//+------------------------------------------------------------------+
//| Activate adaptive filters after consecutive losses               |
//+------------------------------------------------------------------+
void ActivateAdaptiveFilters()
{
   if(g_adaptiveModeActive)
      return; // Already active

   g_adaptiveModeActive = true;
   g_consecutiveWins = 0; // Reset win counter

   // Enable both volume and divergence confirmation (using working variables)
   g_activeVolumeConfirmation = true;
   g_activeDivergenceConfirmation = true;

   LogMessage("╔════════════════════════════════════════════════════════════╗");
   LogMessage("║  ADAPTIVE MODE ACTIVATED                                   ║");
   LogMessage("╚════════════════════════════════════════════════════════════╝");
   LogMessage("Reason: " + IntegerToString(g_symbolParams.adaptiveLossTrigger) + " consecutive losses detected");
   LogMessage("Action: Enabling volume AND divergence filters");
   LogMessage("Recovery: Need " + IntegerToString(g_symbolParams.adaptiveWinRecovery) + " consecutive wins to deactivate");
   LogMessage("Original Settings:");
   LogMessage("  Volume Confirmation: " + (g_originalVolumeConfirmation ? "Enabled" : "Disabled"));
   LogMessage("  Divergence Confirmation: " + (g_originalDivergenceConfirmation ? "Enabled" : "Disabled"));
   LogMessage("Current Settings:");
   LogMessage("  Volume Confirmation: ENABLED (Adaptive)");
   LogMessage("  Divergence Confirmation: ENABLED (Adaptive)");
   LogMessage("════════════════════════════════════════════════════════════");
}

//+------------------------------------------------------------------+
//| Deactivate adaptive filters after consecutive wins               |
//+------------------------------------------------------------------+
void DeactivateAdaptiveFilters()
{
   if(!g_adaptiveModeActive)
      return; // Already inactive

   g_adaptiveModeActive = false;
   g_consecutiveLosses = 0; // Reset loss counter
   g_consecutiveWins = 0;   // Reset win counter

   // Restore original settings (using working variables)
   g_activeVolumeConfirmation = g_originalVolumeConfirmation;
   g_activeDivergenceConfirmation = g_originalDivergenceConfirmation;

   LogMessage("╔════════════════════════════════════════════════════════════╗");
   LogMessage("║  ADAPTIVE MODE DEACTIVATED                                 ║");
   LogMessage("╚════════════════════════════════════════════════════════════╝");
   LogMessage("Reason: " + IntegerToString(g_symbolParams.adaptiveWinRecovery) + " consecutive wins achieved");
   LogMessage("Action: Restoring original filter settings");
   LogMessage("Restored Settings:");
   LogMessage("  Volume Confirmation: " + (g_activeVolumeConfirmation ? "Enabled" : "Disabled"));
   LogMessage("  Divergence Confirmation: " + (g_activeDivergenceConfirmation ? "Enabled" : "Disabled"));
   LogMessage("════════════════════════════════════════════════════════════");
}

//+------------------------------------------------------------------+
//| Check for closed positions and process them                      |
//| Should be called on every tick to detect position closures       |
//+------------------------------------------------------------------+
void CheckForClosedPositions()
{
   if(!UseAdaptiveFilters)
      return;

   // Request history for the last day
   datetime from = TimeCurrent() - 86400; // Last 24 hours
   datetime to = TimeCurrent();

   if(!HistorySelect(from, to))
   {
      if(EnableDetailedLogging)
         LogMessage("Failed to select history for adaptive filter check");
      return;
   }

   int totalDeals = HistoryDealsTotal();

   // Check the most recent deals for position closures
   for(int i = totalDeals - 1; i >= MathMax(0, totalDeals - 10); i--) // Check last 10 deals
   {
      ulong ticket = HistoryDealGetTicket(i);

      if(ticket == 0)
         continue;

      // Only process deals from this EA
      long magic = HistoryDealGetInteger(ticket, DEAL_MAGIC);
      if(magic != MagicNumber)
         continue;

      // Only process exit deals (position closures)
      ENUM_DEAL_ENTRY dealEntry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(ticket, DEAL_ENTRY);
      if(dealEntry != DEAL_ENTRY_OUT)
         continue;

      // Get the position ticket (not the deal ticket)
      long positionId = HistoryDealGetInteger(ticket, DEAL_POSITION_ID);

      // Check if we've already processed this position closure
      if(positionId == (long)g_lastClosedTicket)
         continue;

      // Process this closed position
      ProcessClosedTrade((ulong)positionId);
      break; // Only process one closure per tick to avoid spam
   }
}

//+------------------------------------------------------------------+
//| Detect symbol category based on symbol name                      |
//+------------------------------------------------------------------+
ENUM_SYMBOL_CATEGORY DetectSymbolCategory(string symbol)
{
   // Convert to uppercase for comparison
   StringToUpper(symbol);

   // Major Forex Pairs (most liquid, tight spreads, moderate volatility)
   if(StringFind(symbol, "EURUSD") >= 0 || StringFind(symbol, "GBPUSD") >= 0 ||
      StringFind(symbol, "USDJPY") >= 0 || StringFind(symbol, "USDCHF") >= 0 ||
      StringFind(symbol, "AUDUSD") >= 0 || StringFind(symbol, "USDCAD") >= 0 ||
      StringFind(symbol, "NZDUSD") >= 0)
   {
      return SYMBOL_MAJOR_FOREX;
   }

   // Minor Forex Pairs (cross pairs, moderate liquidity)
   if(StringFind(symbol, "EURGBP") >= 0 || StringFind(symbol, "EURJPY") >= 0 ||
      StringFind(symbol, "GBPJPY") >= 0 || StringFind(symbol, "EURCHF") >= 0 ||
      StringFind(symbol, "EURAUD") >= 0 || StringFind(symbol, "EURCAD") >= 0 ||
      StringFind(symbol, "GBPCHF") >= 0 || StringFind(symbol, "GBPAUD") >= 0 ||
      StringFind(symbol, "AUDNZD") >= 0 || StringFind(symbol, "AUDCAD") >= 0 ||
      StringFind(symbol, "AUDJPY") >= 0 || StringFind(symbol, "CADJPY") >= 0 ||
      StringFind(symbol, "CHFJPY") >= 0 || StringFind(symbol, "NZDJPY") >= 0)
   {
      return SYMBOL_MINOR_FOREX;
   }

   // Exotic Forex Pairs (low liquidity, high spreads, high volatility)
   if(StringFind(symbol, "TRY") >= 0 || StringFind(symbol, "ZAR") >= 0 ||
      StringFind(symbol, "MXN") >= 0 || StringFind(symbol, "BRL") >= 0 ||
      StringFind(symbol, "RUB") >= 0 || StringFind(symbol, "HKD") >= 0 ||
      StringFind(symbol, "SGD") >= 0 || StringFind(symbol, "THB") >= 0 ||
      StringFind(symbol, "NOK") >= 0 || StringFind(symbol, "SEK") >= 0 ||
      StringFind(symbol, "DKK") >= 0 || StringFind(symbol, "PLN") >= 0)
   {
      return SYMBOL_EXOTIC_FOREX;
   }

   // Precious Metals (Gold, Silver - high volatility, trending)
   if(StringFind(symbol, "XAUUSD") >= 0 || StringFind(symbol, "GOLD") >= 0 ||
      StringFind(symbol, "XAGUSD") >= 0 || StringFind(symbol, "SILVER") >= 0 ||
      StringFind(symbol, "XAU") >= 0 || StringFind(symbol, "XAG") >= 0)
   {
      return SYMBOL_METALS;
   }

   // Stock Indices (trending, moderate to high volatility)
   if(StringFind(symbol, "SPX") >= 0 || StringFind(symbol, "SP500") >= 0 ||
      StringFind(symbol, "NAS100") >= 0 || StringFind(symbol, "NASDAQ") >= 0 ||
      StringFind(symbol, "US30") >= 0 || StringFind(symbol, "DOW") >= 0 ||
      StringFind(symbol, "DAX") >= 0 || StringFind(symbol, "GER") >= 0 ||
      StringFind(symbol, "FTSE") >= 0 || StringFind(symbol, "UK100") >= 0 ||
      StringFind(symbol, "CAC") >= 0 || StringFind(symbol, "FRA") >= 0 ||
      StringFind(symbol, "NIKKEI") >= 0 || StringFind(symbol, "JPN") >= 0 ||
      StringFind(symbol, "ASX") >= 0 || StringFind(symbol, "AUS") >= 0)
   {
      return SYMBOL_INDICES;
   }

   // Cryptocurrencies (very high volatility, 24/7 trading)
   if(StringFind(symbol, "BTC") >= 0 || StringFind(symbol, "ETH") >= 0 ||
      StringFind(symbol, "XRP") >= 0 || StringFind(symbol, "LTC") >= 0 ||
      StringFind(symbol, "BCH") >= 0 || StringFind(symbol, "ADA") >= 0 ||
      StringFind(symbol, "DOT") >= 0 || StringFind(symbol, "LINK") >= 0 ||
      StringFind(symbol, "DOGE") >= 0 || StringFind(symbol, "CRYPTO") >= 0)
   {
      return SYMBOL_CRYPTO;
   }

   // Commodities (Oil, Gas, etc.)
   if(StringFind(symbol, "WTI") >= 0 || StringFind(symbol, "BRENT") >= 0 ||
      StringFind(symbol, "OIL") >= 0 || StringFind(symbol, "USOIL") >= 0 ||
      StringFind(symbol, "UKOIL") >= 0 || StringFind(symbol, "NGAS") >= 0 ||
      StringFind(symbol, "GAS") >= 0)
   {
      return SYMBOL_COMMODITIES;
   }

   return SYMBOL_UNKNOWN;
}

//+------------------------------------------------------------------+
//| Get category name as string                                      |
//+------------------------------------------------------------------+
string GetSymbolCategoryName(ENUM_SYMBOL_CATEGORY category)
{
   switch(category)
   {
      case SYMBOL_MAJOR_FOREX:   return "Major Forex";
      case SYMBOL_MINOR_FOREX:   return "Minor Forex";
      case SYMBOL_EXOTIC_FOREX:  return "Exotic Forex";
      case SYMBOL_METALS:        return "Precious Metals";
      case SYMBOL_INDICES:       return "Stock Indices";
      case SYMBOL_CRYPTO:        return "Cryptocurrencies";
      case SYMBOL_COMMODITIES:   return "Commodities";
      default:                   return "Unknown";
   }
}

//+------------------------------------------------------------------+
//| Get optimized parameters for symbol category                     |
//+------------------------------------------------------------------+
SymbolParameters GetSymbolParameters(ENUM_SYMBOL_CATEGORY category)
{
   SymbolParameters params;

   switch(category)
   {
      case SYMBOL_MAJOR_FOREX:
         // Major pairs: Moderate volatility, high liquidity
         // Standard settings work well
         params.breakoutVolumeMax = 0.8;      // Tighter - want very weak breakouts
         params.reversalVolumeMin = 1.8;      // Higher - want strong reversals
         params.volumeAveragePeriod = 20;
         params.rsiPeriod = 14;
         params.macdFast = 12;
         params.macdSlow = 26;
         params.macdSignal = 9;
         params.divergenceLookback = 20;
         params.adaptiveLossTrigger = 3;      // Standard trigger
         params.adaptiveWinRecovery = 2;
         break;

      case SYMBOL_MINOR_FOREX:
         // Minor pairs: Higher volatility, moderate liquidity
         // Need slightly more conservative settings
         params.breakoutVolumeMax = 0.7;      // Even tighter
         params.reversalVolumeMin = 2.0;      // Want very strong reversals
         params.volumeAveragePeriod = 25;     // Longer average for stability
         params.rsiPeriod = 14;
         params.macdFast = 12;
         params.macdSlow = 26;
         params.macdSignal = 9;
         params.divergenceLookback = 25;      // Look back further
         params.adaptiveLossTrigger = 2;      // Activate filters sooner
         params.adaptiveWinRecovery = 3;      // Need more wins to relax
         break;

      case SYMBOL_EXOTIC_FOREX:
         // Exotic pairs: Very high volatility, low liquidity
         // Most conservative settings
         params.breakoutVolumeMax = 0.6;      // Very tight
         params.reversalVolumeMin = 2.5;      // Very strong reversals needed
         params.volumeAveragePeriod = 30;     // Longer average
         params.rsiPeriod = 21;               // Slower RSI
         params.macdFast = 16;                // Slower MACD
         params.macdSlow = 32;
         params.macdSignal = 12;
         params.divergenceLookback = 30;      // Look back much further
         params.adaptiveLossTrigger = 2;      // Very quick to activate
         params.adaptiveWinRecovery = 4;      // Need many wins to relax
         break;

      case SYMBOL_METALS:
         // Metals (Gold/Silver): High volatility, trending
         // Need to catch strong trends, avoid whipsaws
         params.breakoutVolumeMax = 0.7;
         params.reversalVolumeMin = 2.2;
         params.volumeAveragePeriod = 25;
         params.rsiPeriod = 14;
         params.macdFast = 12;
         params.macdSlow = 26;
         params.macdSignal = 9;
         params.divergenceLookback = 25;
         params.adaptiveLossTrigger = 2;      // Quick to protect
         params.adaptiveWinRecovery = 3;
         break;

      case SYMBOL_INDICES:
         // Indices: Trending, moderate volatility
         // Good for false breakout strategy
         params.breakoutVolumeMax = 0.8;
         params.reversalVolumeMin = 1.8;
         params.volumeAveragePeriod = 20;
         params.rsiPeriod = 14;
         params.macdFast = 12;
         params.macdSlow = 26;
         params.macdSignal = 9;
         params.divergenceLookback = 20;
         params.adaptiveLossTrigger = 3;
         params.adaptiveWinRecovery = 2;
         break;

      case SYMBOL_CRYPTO:
         // Crypto: Extremely high volatility, 24/7
         // Most aggressive filtering needed
         params.breakoutVolumeMax = 0.5;      // Extremely tight
         params.reversalVolumeMin = 3.0;      // Massive reversals only
         params.volumeAveragePeriod = 40;     // Much longer average
         params.rsiPeriod = 21;               // Slower indicators
         params.macdFast = 16;
         params.macdSlow = 32;
         params.macdSignal = 12;
         params.divergenceLookback = 40;      // Look back very far
         params.adaptiveLossTrigger = 1;      // Activate after single loss
         params.adaptiveWinRecovery = 5;      // Need many wins
         break;

      case SYMBOL_COMMODITIES:
         // Commodities (Oil, Gas): High volatility, news-driven
         params.breakoutVolumeMax = 0.7;
         params.reversalVolumeMin = 2.0;
         params.volumeAveragePeriod = 25;
         params.rsiPeriod = 14;
         params.macdFast = 12;
         params.macdSlow = 26;
         params.macdSignal = 9;
         params.divergenceLookback = 25;
         params.adaptiveLossTrigger = 2;
         params.adaptiveWinRecovery = 3;
         break;

      default: // SYMBOL_UNKNOWN
         // Use default input parameters
         params.breakoutVolumeMax = BreakoutVolumeMaxMultiplier;
         params.reversalVolumeMin = ReversalVolumeMinMultiplier;
         params.volumeAveragePeriod = VolumeAveragePeriod;
         params.rsiPeriod = RSI_Period;
         params.macdFast = MACD_Fast;
         params.macdSlow = MACD_Slow;
         params.macdSignal = MACD_Signal;
         params.divergenceLookback = DivergenceLookback;
         params.adaptiveLossTrigger = AdaptiveLossTrigger;
         params.adaptiveWinRecovery = AdaptiveWinRecovery;
         break;
   }

   return params;
}

//+------------------------------------------------------------------+
//| Apply symbol-specific parameters                                 |
//+------------------------------------------------------------------+
void ApplySymbolParameters()
{
   if(!UseSymbolSpecificSettings)
   {
      LogMessage("Symbol-specific optimization: DISABLED");
      LogMessage("Using default input parameters for all symbols");
      return;
   }

   // Detect symbol category (or use manual override)
   if(ManualSymbolCategory == "AUTO")
   {
      g_symbolCategory = DetectSymbolCategory(_Symbol);
      LogMessage("Symbol category: AUTO-DETECTED as " + GetSymbolCategoryName(g_symbolCategory));
   }
   else if(ManualSymbolCategory == "MAJOR_FOREX")
   {
      g_symbolCategory = SYMBOL_MAJOR_FOREX;
      LogMessage("Symbol category: MANUALLY SET to Major Forex");
   }
   else if(ManualSymbolCategory == "MINOR_FOREX")
   {
      g_symbolCategory = SYMBOL_MINOR_FOREX;
      LogMessage("Symbol category: MANUALLY SET to Minor Forex");
   }
   else if(ManualSymbolCategory == "EXOTIC_FOREX")
   {
      g_symbolCategory = SYMBOL_EXOTIC_FOREX;
      LogMessage("Symbol category: MANUALLY SET to Exotic Forex");
   }
   else if(ManualSymbolCategory == "METALS")
   {
      g_symbolCategory = SYMBOL_METALS;
      LogMessage("Symbol category: MANUALLY SET to Precious Metals");
   }
   else if(ManualSymbolCategory == "INDICES")
   {
      g_symbolCategory = SYMBOL_INDICES;
      LogMessage("Symbol category: MANUALLY SET to Stock Indices");
   }
   else if(ManualSymbolCategory == "CRYPTO")
   {
      g_symbolCategory = SYMBOL_CRYPTO;
      LogMessage("Symbol category: MANUALLY SET to Cryptocurrencies");
   }
   else if(ManualSymbolCategory == "COMMODITIES")
   {
      g_symbolCategory = SYMBOL_COMMODITIES;
      LogMessage("Symbol category: MANUALLY SET to Commodities");
   }
   else
   {
      g_symbolCategory = DetectSymbolCategory(_Symbol);
      LogMessage("Symbol category: Invalid manual setting, AUTO-DETECTED as " + GetSymbolCategoryName(g_symbolCategory));
   }

   // Get optimized parameters for this category
   g_symbolParams = GetSymbolParameters(g_symbolCategory);

   // Log parameter comparison
   LogMessage("╔════════════════════════════════════════════════════════════╗");
   LogMessage("║  SYMBOL-SPECIFIC PARAMETERS APPLIED                        ║");
   LogMessage("╚════════════════════════════════════════════════════════════╝");
   LogMessage("Symbol: " + _Symbol);
   LogMessage("Category: " + GetSymbolCategoryName(g_symbolCategory));
   LogMessage("");
   LogMessage("Volume Parameters:");
   LogMessage("  Breakout Max:     " + DoubleToString(g_symbolParams.breakoutVolumeMax, 2) +
              " (default: " + DoubleToString(g_defaultParams.breakoutVolumeMax, 2) + ")");
   LogMessage("  Reversal Min:     " + DoubleToString(g_symbolParams.reversalVolumeMin, 2) +
              " (default: " + DoubleToString(g_defaultParams.reversalVolumeMin, 2) + ")");
   LogMessage("  Average Period:   " + IntegerToString(g_symbolParams.volumeAveragePeriod) +
              " (default: " + IntegerToString(g_defaultParams.volumeAveragePeriod) + ")");
   LogMessage("");
   LogMessage("Divergence Parameters:");
   LogMessage("  RSI Period:       " + IntegerToString(g_symbolParams.rsiPeriod) +
              " (default: " + IntegerToString(g_defaultParams.rsiPeriod) + ")");
   LogMessage("  MACD Fast:        " + IntegerToString(g_symbolParams.macdFast) +
              " (default: " + IntegerToString(g_defaultParams.macdFast) + ")");
   LogMessage("  MACD Slow:        " + IntegerToString(g_symbolParams.macdSlow) +
              " (default: " + IntegerToString(g_defaultParams.macdSlow) + ")");
   LogMessage("  MACD Signal:      " + IntegerToString(g_symbolParams.macdSignal) +
              " (default: " + IntegerToString(g_defaultParams.macdSignal) + ")");
   LogMessage("  Lookback Period:  " + IntegerToString(g_symbolParams.divergenceLookback) +
              " (default: " + IntegerToString(g_defaultParams.divergenceLookback) + ")");
   LogMessage("");
   LogMessage("Adaptive Triggers:");
   LogMessage("  Loss Trigger:     " + IntegerToString(g_symbolParams.adaptiveLossTrigger) +
              " (default: " + IntegerToString(g_defaultParams.adaptiveLossTrigger) + ")");
   LogMessage("  Win Recovery:     " + IntegerToString(g_symbolParams.adaptiveWinRecovery) +
              " (default: " + IntegerToString(g_defaultParams.adaptiveWinRecovery) + ")");
   LogMessage("════════════════════════════════════════════════════════════");
}

