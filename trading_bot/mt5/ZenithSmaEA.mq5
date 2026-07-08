//+------------------------------------------------------------------+
//| ZenithSmaEA.mq5  v2                                              |
//| SMA kesisim stratejisi + tam risk zinciri - egitim amacli EA     |
//|                                                                  |
//| Python botundaki (trading_bot/) risk yonetiminin MQL5 karsiligi: |
//|  - SMA kesisiminde long, ters kesisimde kapat (short yok)        |
//|  - Istege bagli SMA200 trend filtresi (dusen bicak koruması)     |
//|  - Sabit SL/TP + istege bagli iz suren stop (trailing)           |
//|  - Gunluk zarar freni: gun ici kayip limiti asilirsa gun kapanir |
//|  - Cooldown: pozisyon kapandiktan sonra N mum yeni giris yok     |
//|  - Lot, "islem basina % risk" kuralindan hesaplanir              |
//|                                                                  |
//| SADECE DEMO HESAPTA kullanin. MetaEditor'de F7 ile derleyin,     |
//| Strateji Sinayici'da (Ctrl+R) yillarca veride test edin.         |
//+------------------------------------------------------------------+
#property copyright "Zenith contributors"
#property version   "2.00"
#property strict

#include <Trade\Trade.mqh>

CTrade trade;

input int    FastPeriod          = 20;       // Hizli SMA periyodu
input int    SlowPeriod          = 50;       // Yavas SMA periyodu
input bool   UseTrendFilter      = true;     // SMA trend filtresi acik mi?
input int    TrendPeriod         = 200;      // Trend filtresi periyodu
input double RiskPercent         = 1.0;      // Islem basina risk (% bakiye)
input int    StopLossPoints      = 2000;     // Stop-loss (puan)
input int    TakeProfitPoints    = 4000;     // Take-profit (puan)
input int    TrailingStopPoints  = 0;        // Iz suren stop (puan, 0 = kapali)
input double MaxDailyLossPercent = 5.0;      // Gunluk zarar freni (%, 0 = kapali)
input int    CooldownBars        = 3;        // Kapanis sonrasi bekleme (mum)
input ulong  MagicNumber         = 20260708; // Bu EA'nin islem imzasi

int fastHandle = INVALID_HANDLE;
int slowHandle = INVALID_HANDLE;
int trendHandle = INVALID_HANDLE;

datetime g_lastCloseTime = 0;   // cooldown icin son kapanis zamani
datetime g_dayStart = 0;        // gunluk fren: gunun baslangici
double   g_dayStartEquity = 0;  // gunluk fren: gun basi bakiye
bool     g_haltedToday = false; // fren cekildiyse bugun islem yok
bool     g_hadPosition = false; // kapanis tespiti icin onceki tur durumu

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
   if(UseTrendFilter)
     {
      trendHandle = iMA(_Symbol, _Period, TrendPeriod, 0, MODE_SMA, PRICE_CLOSE);
      if(trendHandle == INVALID_HANDLE)
         return(INIT_FAILED);
     }
   trade.SetExpertMagicNumber(MagicNumber);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(fastHandle != INVALID_HANDLE)  IndicatorRelease(fastHandle);
   if(slowHandle != INVALID_HANDLE)  IndicatorRelease(slowHandle);
   if(trendHandle != INVALID_HANDLE) IndicatorRelease(trendHandle);
  }

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
//| Bu EA'ya ait acik pozisyonun ticket'i (yoksa 0).                 |
//+------------------------------------------------------------------+
ulong MyPositionTicket()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionSelectByTicket(ticket)
         && PositionGetString(POSITION_SYMBOL) == _Symbol
         && PositionGetInteger(POSITION_MAGIC) == (long)MagicNumber)
         return(ticket);
     }
   return(0);
  }

//+------------------------------------------------------------------+
void CloseAllPositions(const string reason)
  {
   ulong ticket = MyPositionTicket();
   if(ticket > 0)
     {
      trade.PositionClose(ticket);
      Print("Pozisyon kapatildi: ", reason);
     }
  }

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
   double lots   = riskMoney / lossPerLot;
   double step   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(step > 0)
      lots = MathFloor(lots / step) * step;
   return(MathMin(MathMax(lots, minLot), maxLot));
  }

//+------------------------------------------------------------------+
//| Gunluk zarar freni: gun degisimini izler, limit asilirsa durur.  |
//+------------------------------------------------------------------+
bool DailyHaltActive()
  {
   datetime today = iTime(_Symbol, PERIOD_D1, 0);
   if(today != g_dayStart)
     {
      g_dayStart = today;
      g_dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
      g_haltedToday = false;
     }
   if(g_haltedToday)
      return(true);
   if(MaxDailyLossPercent <= 0 || g_dayStartEquity <= 0)
      return(false);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(equity <= g_dayStartEquity * (1 - MaxDailyLossPercent / 100.0))
     {
      CloseAllPositions("gunluk zarar freni");
      g_haltedToday = true;
      Print("KILL SWITCH: gunluk zarar > %", MaxDailyLossPercent, ", bugun islem yok");
      return(true);
     }
   return(false);
  }

//+------------------------------------------------------------------+
//| Iz suren stop: SL'i sadece YUKARI tasir (long pozisyon).         |
//+------------------------------------------------------------------+
void ApplyTrailing()
  {
   if(TrailingStopPoints <= 0)
      return;
   ulong ticket = MyPositionTicket();
   if(ticket == 0 || !PositionSelectByTicket(ticket))
      return;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double newSL = NormalizeDouble(bid - TrailingStopPoints * _Point, _Digits);
   double curSL = PositionGetDouble(POSITION_SL);
   double curTP = PositionGetDouble(POSITION_TP);
   if(newSL > curSL + _Point)  // sadece iyilesme yonunde guncelle
      trade.PositionModify(ticket, newSL, curTP);
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   if(DailyHaltActive())
      return;

   ApplyTrailing();  // trailing her tikte calisir, sinyaller yeni mumda

   // kapanis tespiti (SL/TP/manuel dahil): cooldown sayaci baslat
   bool nowHasPosition = (MyPositionTicket() != 0);
   if(g_hadPosition && !nowHasPosition)
      g_lastCloseTime = TimeCurrent();
   g_hadPosition = nowHasPosition;

   if(!IsNewBar())
      return;

   double fast[], slow[];
   ArraySetAsSeries(fast, true);
   ArraySetAsSeries(slow, true);
   if(CopyBuffer(fastHandle, 0, 1, 2, fast) < 2)
      return;
   if(CopyBuffer(slowHandle, 0, 1, 2, slow) < 2)
      return;

   bool crossUp   = fast[0] > slow[0] && fast[1] <= slow[1];
   bool crossDown = fast[0] < slow[0] && fast[1] >= slow[1];

   if(crossDown && nowHasPosition)
     {
      CloseAllPositions("strateji sinyali");
      return;
     }

   if(crossUp && !nowHasPosition)
     {
      // cooldown: son kapanistan bu yana yeterli mum gecti mi?
      if(CooldownBars > 0 && g_lastCloseTime > 0
         && TimeCurrent() - g_lastCloseTime < (long)CooldownBars * PeriodSeconds(_Period))
        {
         Print("cooldown: yeni giris icin bekleniyor");
         return;
        }
      // trend filtresi: fiyat uzun donem ortalamanin ustunde olmali
      if(UseTrendFilter)
        {
         double trendBuf[];
         ArraySetAsSeries(trendBuf, true);
         if(CopyBuffer(trendHandle, 0, 1, 1, trendBuf) < 1)
            return;
         double lastClose = iClose(_Symbol, _Period, 1);
         if(lastClose <= trendBuf[0])
           {
            Print("trend filtresi: fiyat SMA", TrendPeriod, " altinda, giris yok");
            return;
           }
        }
      double lots = LotsByRisk();
      if(lots <= 0)
        {
         Print("Lot hesaplanamadi, islem yok");
         return;
        }
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl  = NormalizeDouble(ask - StopLossPoints * _Point, _Digits);
      double tp  = NormalizeDouble(ask + TakeProfitPoints * _Point, _Digits);
      if(!trade.Buy(lots, _Symbol, 0.0, sl, tp, "ZenithSmaEA v2"))
         Print("Alim emri basarisiz: ", trade.ResultRetcodeDescription());
     }
  }
//+------------------------------------------------------------------+
