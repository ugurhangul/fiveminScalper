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
input bool     UseOnly00UTCCandle = true;      // Use only 00:00 UTC 4H candle (closes at 04:00)
input int      MagicNumber = 123456;           // Magic number for orders
input string   TradeComment = "5MinScalper";   // Trade comment

input group "=== Logging Settings ==="
input bool     EnableDetailedLogging = true;   // Enable detailed logging
input bool     LogToFile = true;               // Write logs to file
input bool     LogToConsole = true;            // Print logs to console
input bool     ExportCandleData = false;       // Export candle data to CSV for verification

input group "=== Debug Settings ==="
input bool     LogActiveTradesEvery5Min = true; // Log all active trades every 5-min candle

input group "=== Visual Settings ==="
input bool     ShowLevelsOnChart = true;       // Draw levels on chart
input color    Color4HHigh = clrDodgerBlue;    // 4H High line color
input color    Color4HLow = clrDodgerBlue;     // 4H Low line color
input color    ColorBuyEntry = clrLime;        // Buy entry line color
input color    ColorSellEntry = clrRed;        // Sell entry line color
input int      LineWidth = 2;                  // Line width
input ENUM_LINE_STYLE LineStyle = STYLE_SOLID; // Line style

//--- Global Variables
datetime g_last4HCandleTime = 0;               // Last processed 4H candle time (for trading)
datetime g_lastSeen4HCandleTime = 0;           // Last seen 4H candle time (including skipped ones)
datetime g_last5MinCandleTime = 0;             // Last processed 5-min candle time
datetime g_processed04CandleTime = 0;          // Time of the 04:00 UTC candle we're using
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
   LogMessage("Use Only 00:00 UTC Candle: " + (UseOnly00UTCCandle ? "Yes (closes at 04:00)" : "No"));
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

   LogMessage("Initialization successful - EA is ready to trade");

   // Initialize with current 4H candle on startup
   datetime current4HTime = iTime(_Symbol, PERIOD_H4, 0);
   if(current4HTime > 0)
   {
      int candleIndex = 1; // Start with last closed candle
      bool foundValidCandle = false;

      // If 00:00 UTC filter is enabled, search for the most recent 00:00 UTC candle
      if(UseOnly00UTCCandle)
      {
         LogMessage("Searching for most recent 00:00 UTC candle (closes at 04:00)...");

         // Search backwards up to 24 hours (6 x 4H candles)
         for(int i = 1; i <= 6; i++)
         {
            datetime candleTime = iTime(_Symbol, PERIOD_H4, i);
            MqlDateTime timeStruct;
            TimeToStruct(candleTime, timeStruct);

            if(timeStruct.hour == 0)  // Found a 00:00 UTC candle
            {
               candleIndex = i;
               foundValidCandle = true;
               LogMessage("Found 00:00 UTC candle at index " + IntegerToString(i) + " - " + TimeToString(candleTime, TIME_DATE|TIME_MINUTES) + " UTC");
               LogMessage("This candle closes at 04:00 UTC");
               break;
            }
         }

         if(!foundValidCandle)
         {
            LogMessage("No 00:00 UTC candle found in last 24 hours - waiting for next one");
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
         datetime closedCandleTime = iTime(_Symbol, PERIOD_H4, candleIndex);

         // Store which 00:00 candle we're using
         if(UseOnly00UTCCandle)
         {
            g_processed04CandleTime = closedCandleTime;
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

         // Check if we're in the 00:00 UTC candle formation period (00:00 - 04:00)
         if(IsInCandleFormationPeriod())
         {
            g_tradingAllowedToday = false;
            LogMessage("TRADING SUSPENDED - EA started during 00:00 UTC candle formation (00:00-04:00)");
            LogMessage("Trading will begin at 04:00 UTC when the candle closes");
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

      // If filter is enabled, only process 00:00 UTC candles
      if(UseOnly00UTCCandle)
      {
         // Check if the closed candle is at 00:00 UTC
         if(timeStruct.hour != 0)
         {
            LogMessage("SKIPPING: Candle hour is " + IntegerToString(timeStruct.hour) + ":00 UTC (only 00:00 UTC candles are processed)");
            LogMessage("Updated g_lastSeen4HCandleTime but NOT g_last4HCandleTime");
            LogMessage("Will check for 00:00 candle on next 4H candle");
            return false;
         }
         else
         {
            LogMessage("PROCESSING: Candle hour is 00:00 UTC (closes at 04:00) - This candle will be processed");
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
   g_last4HCandleTime = iTime(_Symbol, PERIOD_H4, 0);

   // Store the time of the 00:00 candle we're using
   datetime closedCandleTime = iTime(_Symbol, PERIOD_H4, 1);
   if(UseOnly00UTCCandle)
   {
      g_processed04CandleTime = closedCandleTime;
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

   // Check if we're in the 00:00 UTC candle formation period (00:00 - 04:00)
   if(IsInCandleFormationPeriod())
   {
      g_tradingAllowedToday = false;
      LogMessage("TRADING SUSPENDED - New 00:00 UTC candle is forming (will close at 04:00)");
      LogMessage("Trading will resume at 04:00 UTC when this candle closes");
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

   // Check if we're in the 00:00 UTC candle formation period (00:00 - 04:00)
   if(IsInCandleFormationPeriod())
   {
      if(EnableDetailedLogging)
         LogMessage("MonitorEntries: Trading suspended - Waiting for 00:00 UTC candle to close at 04:00");
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
         g_buyBreakoutConfirmed = true;
         g_buyBreakoutCandleTime = candle5mTime;  // Store the time of breakout candle

         LogMessage("*** BUY BREAKOUT CONFIRMED ***");
         LogMessage("5-min candle closed BELOW 4H Low");
         LogMessage("Candle Time: " + TimeToString(candle5mTime, TIME_DATE|TIME_MINUTES));
         LogMessage("Candle OHLC: O=" + DoubleToString(candle5mOpen, _Digits) +
                    " H=" + DoubleToString(candle5mHigh, _Digits) +
                    " L=" + DoubleToString(candle5mLow, _Digits) +
                    " C=" + DoubleToString(candle5mClose, _Digits));
         LogMessage("Candle Close: " + DoubleToString(candle5mClose, _Digits) + " | 4H Low: " + DoubleToString(g_4HLow, _Digits));
         LogMessage("Breakout Distance: " + DoubleToString(g_4HLow - candle5mClose, _Digits) + " points");
         LogMessage("Waiting for reversal back above 4H Low...");
      }
      else if(!g_buyBreakoutConfirmed && EnableDetailedLogging)
      {
         LogMessage("BUY Breakout NOT confirmed: Close (" + DoubleToString(candle5mClose, _Digits) +
                    ") >= 4H Low (" + DoubleToString(g_4HLow, _Digits) + ")");
      }

      // Step 3 & 4: Check if 5-min candle closed ABOVE 4H Low (reversal confirmation)
      if(g_buyBreakoutConfirmed && !g_buyReversalConfirmed && candle5mClose > g_4HLow)
      {
         g_buyReversalConfirmed = true;

         // Find the LOWEST low among the LATEST 10 candles within breakout-to-reversal range
         // Use the LATER of: (1) 10 candles back, or (2) breakout time
         // This ensures we analyze up to 10 candles but never before the breakout
         datetime startTime = MathMax(g_buyBreakoutCandleTime, candle5mTime - (10 * 5 * 60));
         double lowestLow = FindLowestLowInRange(startTime, candle5mTime);

         LogMessage("*** BUY REVERSAL CONFIRMED ***");
         LogMessage("5-min candle closed ABOVE 4H Low after breakout");
         LogMessage("Candle Time: " + TimeToString(candle5mTime, TIME_DATE|TIME_MINUTES));
         LogMessage("Candle OHLC: O=" + DoubleToString(candle5mOpen, _Digits) +
                    " H=" + DoubleToString(candle5mHigh, _Digits) +
                    " L=" + DoubleToString(candle5mLow, _Digits) +
                    " C=" + DoubleToString(candle5mClose, _Digits));
         LogMessage("Candle Close: " + DoubleToString(candle5mClose, _Digits) + " | 4H Low: " + DoubleToString(g_4HLow, _Digits));
         LogMessage("Reversal Distance: " + DoubleToString(candle5mClose - g_4HLow, _Digits) + " points");
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
         g_sellBreakoutConfirmed = true;
         g_sellBreakoutCandleTime = candle5mTime;  // Store the time of breakout candle

         LogMessage("*** SELL BREAKOUT CONFIRMED ***");
         LogMessage("5-min candle closed ABOVE 4H High");
         LogMessage("Candle Time: " + TimeToString(candle5mTime, TIME_DATE|TIME_MINUTES));
         LogMessage("Candle OHLC: O=" + DoubleToString(candle5mOpen, _Digits) +
                    " H=" + DoubleToString(candle5mHigh, _Digits) +
                    " L=" + DoubleToString(candle5mLow, _Digits) +
                    " C=" + DoubleToString(candle5mClose, _Digits));
         LogMessage("Candle Close: " + DoubleToString(candle5mClose, _Digits) + " | 4H High: " + DoubleToString(g_4HHigh, _Digits));
         LogMessage("Breakout Distance: " + DoubleToString(candle5mClose - g_4HHigh, _Digits) + " points");
         LogMessage("Waiting for reversal back below 4H High...");
      }
      else if(!g_sellBreakoutConfirmed && EnableDetailedLogging)
      {
         LogMessage("SELL Breakout NOT confirmed: Close (" + DoubleToString(candle5mClose, _Digits) +
                    ") <= 4H High (" + DoubleToString(g_4HHigh, _Digits) + ")");
      }

      // Step 3 & 4: Check if 5-min candle closed BELOW 4H High (reversal confirmation)
      if(g_sellBreakoutConfirmed && !g_sellReversalConfirmed && candle5mClose < g_4HHigh)
      {
         g_sellReversalConfirmed = true;

         // Find the HIGHEST high among the LATEST 10 candles within breakout-to-reversal range
         // Use the LATER of: (1) 10 candles back, or (2) breakout time
         // This ensures we analyze up to 10 candles but never before the breakout
         datetime startTime = MathMax(g_sellBreakoutCandleTime, candle5mTime - (10 * 5 * 60));
         double highestHigh = FindHighestHighInRange(startTime, candle5mTime);

         LogMessage("*** SELL REVERSAL CONFIRMED ***");
         LogMessage("5-min candle closed BELOW 4H High after breakout");
         LogMessage("Candle Time: " + TimeToString(candle5mTime, TIME_DATE|TIME_MINUTES));
         LogMessage("Candle OHLC: O=" + DoubleToString(candle5mOpen, _Digits) +
                    " H=" + DoubleToString(candle5mHigh, _Digits) +
                    " L=" + DoubleToString(candle5mLow, _Digits) +
                    " C=" + DoubleToString(candle5mClose, _Digits));
         LogMessage("Candle Close: " + DoubleToString(candle5mClose, _Digits) + " | 4H High: " + DoubleToString(g_4HHigh, _Digits));
         LogMessage("Reversal Distance: " + DoubleToString(g_4HHigh - candle5mClose, _Digits) + " points");
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
//| Check if in candle formation period (00:00-04:00 UTC)            |
//+------------------------------------------------------------------+
bool IsInCandleFormationPeriod()
{
   MqlDateTime currentTime;
   TimeToStruct(TimeCurrent(), currentTime);
   return (currentTime.hour >= 0 && currentTime.hour < 4);
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
//| Find the most recent 00:00 UTC candle time                       |
//+------------------------------------------------------------------+
datetime Find00UTCCandle()
{
   // Search backwards up to 24 hours (6 x 4H candles)
   for(int i = 1; i <= 6; i++)
   {
      datetime candleTime = iTime(_Symbol, PERIOD_H4, i);
      MqlDateTime timeStruct;
      TimeToStruct(candleTime, timeStruct);

      if(timeStruct.hour == 0)  // Found a 00:00 UTC candle
      {
         return candleTime;
      }
   }

   return 0;
}

//+------------------------------------------------------------------+
//| Find the index of the most recent 00:00 UTC candle               |
//+------------------------------------------------------------------+
int Find00UTCCandleIndex()
{
   // Search backwards up to 24 hours (6 x 4H candles)
   for(int i = 1; i <= 6; i++)
   {
      datetime candleTime = iTime(_Symbol, PERIOD_H4, i);
      MqlDateTime timeStruct;
      TimeToStruct(candleTime, timeStruct);

      if(timeStruct.hour == 0)  // Found a 00:00 UTC candle
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
   datetime closedCandleTime = iTime(_Symbol, PERIOD_H4, candleIndex);

   // Store which 00:00 candle we're using
   if(UseOnly00UTCCandle)
   {
      g_processed04CandleTime = closedCandleTime;
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

   // Reset tracking
   g_buyOrderPlaced = false;
   g_sellOrderPlaced = false;
   g_buyBreakoutConfirmed = false;
   g_buyReversalConfirmed = false;
   g_buyBreakoutCandleTime = 0;
   g_sellBreakoutConfirmed = false;
   g_sellReversalConfirmed = false;
   g_sellBreakoutCandleTime = 0;

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

