//+------------------------------------------------------------------+
//| ZenithSmaEA.mq5  v2.20                                           |
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
//| Varsayilan DEMO'dur. Canli hesap acik ve tam hesap kilidi ister. |
//| MetaEditor F7 ile derleyin; once Strateji Sinayici'da test edin. |
//+------------------------------------------------------------------+
#property copyright "Zenith contributors"
#property version   "2.20"
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
input int    MaxSpreadPoints     = 50;       // Yeni alim icin en yuksek spread (puan)
input bool   AllowLiveAccount    = false;    // Varsayilan: sadece demo hesap
input ulong  LiveAccountLogin    = 0;        // Canlida izin verilen TAM hesap no
input double MaxMarginPercent    = 20.0;     // Tek emrin azami equity/margin orani
input bool   AllowWeekendEntry   = false;    // Cuma gec/hafta sonu yeni giris
input int    FridayCutoffHourUTC = 18;       // Cuma yeni giris kesme saati (UTC)
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
   if(FastPeriod <= 0 || SlowPeriod <= 0 || FastPeriod >= SlowPeriod)
     {
      Print("Hata: periyotlar pozitif ve FastPeriod < SlowPeriod olmali");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(RiskPercent <= 0 || RiskPercent > 5 || StopLossPoints <= 0
      || TakeProfitPoints <= 0 || MaxDailyLossPercent < 0
      || MaxDailyLossPercent > 20 || CooldownBars < 0 || MaxSpreadPoints <= 0
      || MaxMarginPercent <= 0 || MaxMarginPercent > 100
      || FridayCutoffHourUTC < 0 || FridayCutoffHourUTC > 23)
     {
      Print("Hata: risk/SL/TP/gunluk limit/cooldown/spread parametreleri gecersiz");
      return(INIT_PARAMETERS_INCORRECT);
     }
   long tradeMode = AccountInfoInteger(ACCOUNT_TRADE_MODE);
   ulong accountLogin = (ulong)AccountInfoInteger(ACCOUNT_LOGIN);
   if(tradeMode != ACCOUNT_TRADE_MODE_DEMO
      && (!AllowLiveAccount || LiveAccountLogin == 0 || LiveAccountLogin != accountLogin))
     {
      Print("GUVENLIK: Canli hesap icin AllowLiveAccount=true ve LiveAccountLogin=",
            accountLogin, " birlikte gerekir.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)
      || !MQLInfoInteger(MQL_TRADE_ALLOWED)
      || !AccountInfoInteger(ACCOUNT_TRADE_ALLOWED)
      || !AccountInfoInteger(ACCOUNT_TRADE_EXPERT))
     {
      Print("GUVENLIK: Terminal/hesap Expert Advisor islemlerine izin vermiyor.");
      return(INIT_FAILED);
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
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.SetDeviationInPoints(20);
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
      if(trade.PositionClose(ticket))
         Print("Pozisyon kapatildi: ", reason);
      else
         Print("Pozisyon KAPATILAMADI (", reason, "): ", trade.ResultRetcodeDescription());
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
    // Minimum lota YUKARI yuvarlamak belirlenen para riskini asabilir.
    // Hesaplanan miktar minimumun altindaysa islem acmamak daha guvenlidir.
    if(lots < minLot)
       return(0.0);
    return(MathMin(lots, maxLot));
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
      if(!AllowWeekendEntry)
        {
         MqlDateTime utc;
         TimeToStruct(TimeGMT(), utc);
         if(utc.day_of_week == 6 || utc.day_of_week == 0
            || (utc.day_of_week == 5 && utc.hour >= FridayCutoffHourUTC))
           {
            Print("Hafta sonu/gap korumasi: yeni giris yok");
            return;
           }
        }
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
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      if(bid <= 0 || ask <= 0 || ask < bid)
        {
         Print("Gecersiz kotasyon, giris yok");
         return;
        }
      double spreadPoints = (ask - bid) / _Point;
      if(spreadPoints > MaxSpreadPoints)
        {
         Print("Spread ", DoubleToString(spreadPoints, 1), " puan; limit ",
               MaxSpreadPoints, ", giris yok");
         return;
        }
      double lots = LotsByRisk();
      if(lots <= 0)
        {
         Print("Lot hesaplanamadi, islem yok");
         return;
        }
      double sl  = NormalizeDouble(ask - StopLossPoints * _Point, _Digits);
      double tp  = NormalizeDouble(ask + TakeProfitPoints * _Point, _Digits);
      long stopsLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
      if((ask - sl) / _Point < stopsLevel || (tp - ask) / _Point < stopsLevel)
        {
         Print("SL/TP broker minimum mesafesini karsilamiyor: ", stopsLevel, " puan");
         return;
        }
      double requiredMargin = 0.0;
      double equity = AccountInfoDouble(ACCOUNT_EQUITY);
      if(!OrderCalcMargin(ORDER_TYPE_BUY, _Symbol, lots, ask, requiredMargin)
         || equity <= 0 || requiredMargin > equity * MaxMarginPercent / 100.0)
        {
         Print("Margin limiti/on kontrolu basarisiz; giris yok. Gereken=",
               requiredMargin, " equity=", equity);
         return;
        }
      if(!trade.Buy(lots, _Symbol, 0.0, sl, tp, "ZenithSmaEA v2.20"))
         Print("Alim emri basarisiz: ", trade.ResultRetcodeDescription());
     }
  }
//+------------------------------------------------------------------+
