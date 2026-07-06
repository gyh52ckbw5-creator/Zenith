//+------------------------------------------------------------------+
//| ZenithSmaEA.mq5                                                  |
//| SMA kesisim stratejisi - egitim amacli Expert Advisor            |
//|                                                                  |
//| trading_bot/bot/strategies.py icindeki SmaCross'un MQL5 hali.    |
//| SADECE DEMO HESAPTA kullanin. Once MetaEditor'de derleyin (F7),  |
//| sonra Strateji Sinayici'da (Ctrl+R) yillarca veride test edin.   |
//|                                                                  |
//| Kurallar:                                                        |
//|  - Hizli SMA yavas SMA'yi yukari keserse: AL (long)              |
//|  - Asagi keserse: pozisyonu KAPAT (short acilmaz)                |
//|  - Her pozisyona otomatik stop-loss ve take-profit konur         |
//|  - Lot, hesap bakiyesinin RiskPercent'i riske girecek boyutta    |
//+------------------------------------------------------------------+
#property copyright "Zenith contributors"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

CTrade trade;

input int    FastPeriod       = 20;       // Hizli SMA periyodu
input int    SlowPeriod       = 50;       // Yavas SMA periyodu
input double RiskPercent      = 1.0;      // Islem basina risk (% bakiye)
input int    StopLossPoints   = 2000;     // Stop-loss (puan)
input int    TakeProfitPoints = 4000;     // Take-profit (puan)
input ulong  MagicNumber      = 20260706; // Bu EA'nin islem imzasi

int fastHandle = INVALID_HANDLE;
int slowHandle = INVALID_HANDLE;

//+------------------------------------------------------------------+
int OnInit()
  {
   if(FastPeriod >= SlowPeriod)
     {
      Print("Hata: FastPeriod < SlowPeriod olmali");
      return(INIT_PARAMETERS_INCORRECT);
     }
   fastHandle = iMA(_Symbol, _Period, FastPeriod, 0, MODE_SMA, PRICE_CLOSE);
   slowHandle = iMA(_Symbol, _Period, SlowPeriod, 0, MODE_SMA, PRICE_CLOSE);
   if(fastHandle == INVALID_HANDLE || slowHandle == INVALID_HANDLE)
      return(INIT_FAILED);
   trade.SetExpertMagicNumber(MagicNumber);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(fastHandle != INVALID_HANDLE) IndicatorRelease(fastHandle);
   if(slowHandle != INVALID_HANDLE) IndicatorRelease(slowHandle);
  }

//+------------------------------------------------------------------+
//| Yeni mum acildi mi? Sinyal sadece kapanan mumdan uretilir.       |
//+------------------------------------------------------------------+
bool IsNewBar()
  {
   static datetime lastBarTime = 0;
   datetime t = iTime(_Symbol, _Period, 0);
   if(t == lastBarTime)
      return(false);
   lastBarTime = t;
   return(true);
  }

//+------------------------------------------------------------------+
//| Bu EA'ya (MagicNumber) ait acik pozisyon var mi?                 |
//+------------------------------------------------------------------+
bool HasPosition()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionSelectByTicket(ticket)
         && PositionGetString(POSITION_SYMBOL) == _Symbol
         && PositionGetInteger(POSITION_MAGIC) == (long)MagicNumber)
         return(true);
     }
   return(false);
  }

//+------------------------------------------------------------------+
void CloseAllPositions()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionSelectByTicket(ticket)
         && PositionGetString(POSITION_SYMBOL) == _Symbol
         && PositionGetInteger(POSITION_MAGIC) == (long)MagicNumber)
         trade.PositionClose(ticket);
     }
  }

//+------------------------------------------------------------------+
//| Stop mesafesine gore riski RiskPercent'e sabitleyen lot hesabi.  |
//+------------------------------------------------------------------+
double LotsByRisk()
  {
   double equity    = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskMoney = equity * RiskPercent / 100.0;
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickValue <= 0 || tickSize <= 0)
      return(0.0);
   double lossPerLot = StopLossPoints * _Point / tickSize * tickValue;
   if(lossPerLot <= 0)
      return(0.0);
   double lots    = riskMoney / lossPerLot;
   double step    = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(step > 0)
      lots = MathFloor(lots / step) * step;
   return(MathMin(MathMax(lots, minLot), maxLot));
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   if(!IsNewBar())
      return;

   // Kapanmis son iki mumun SMA degerleri (index 0 = son kapanan mum)
   double fast[], slow[];
   ArraySetAsSeries(fast, true);
   ArraySetAsSeries(slow, true);
   if(CopyBuffer(fastHandle, 0, 1, 2, fast) < 2)
      return;
   if(CopyBuffer(slowHandle, 0, 1, 2, slow) < 2)
      return;

   bool crossUp   = fast[0] > slow[0] && fast[1] <= slow[1];
   bool crossDown = fast[0] < slow[0] && fast[1] >= slow[1];
   bool inPosition = HasPosition();

   if(crossDown && inPosition)
     {
      CloseAllPositions();
      return;
     }

   if(crossUp && !inPosition)
     {
      double lots = LotsByRisk();
      if(lots <= 0)
        {
         Print("Lot hesaplanamadi, islem yok");
         return;
        }
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl  = NormalizeDouble(ask - StopLossPoints * _Point, _Digits);
      double tp  = NormalizeDouble(ask + TakeProfitPoints * _Point, _Digits);
      if(!trade.Buy(lots, _Symbol, 0.0, sl, tp, "ZenithSmaEA"))
         Print("Alim emri basarisiz: ", trade.ResultRetcodeDescription());
     }
  }
//+------------------------------------------------------------------+
