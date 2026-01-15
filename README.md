# 🐋 Balina Bot - Gelişmiş Trading Bot

Balina Bot, Binance Futures için gelişmiş multi-strategy trading bot'udur. Mevcut stratejinizi geliştirip, hibrit stratejiler ve market regime detection ekleyerek daha akıllı trading kararları alır.

## 🚀 **Özellikler**

### **1. Multi-Factor Scoring Stratejisi**
- Funding Rate analizi
- Open Interest değişimi
- Hacim analizi
- Fiyat momentumu
- Volatilite analizi
- Ağırlıklı scoring sistemi

### **2. Hibrit Strateji (Trend + Mean Reversion)**
- Moving Average trend analizi
- RSI aşırı değer tespiti
- Bollinger Bands mean reversion
- Hacim bazlı sinyal güçlendirme
- Trend ve mean reversion uyumu

### **3. Market Regime Detection**
- Volatilite bazlı regime tespiti
- BTC dominance analizi
- Market cap değişimi takibi
- Regime'e göre strateji adaptasyonu
- Risk yönetimi optimizasyonu

### **4. Gelişmiş Risk Yönetimi**
- Güvenilirlik bazlı pozisyon büyüklüğü
- Dinamik stop-loss ve take-profit
- Pozisyon süresi yönetimi
- Cooldown sistemi
- Tek pozisyon kuralı

## 🏗️ **Proje Yapısı**

```
balina_bot/
├── config.py                 # Konfigürasyon ayarları
├── main.py                   # Ana bot sınıfı
├── requirements.txt          # Python paketleri
├── binance_futures_symbols.json  # Sembol listesi
├── strategies/               # Strateji modülleri
│   ├── __init__.py
│   ├── base_strategy.py     # Temel strateji sınıfı
│   ├── multi_factor_strategy.py  # Multi-factor scoring
│   ├── hybrid_strategy.py   # Hibrit strateji
│   ├── market_regime_strategy.py # Market regime detection
│   └── strategy_manager.py  # Strateji yöneticisi
├── clients/                  # API client'ları
│   ├── __init__.py
│   ├── binance_client.py    # Binance API client
│   └── telegram_client.py   # Telegram bot client
├── trading/                  # Trading modülleri
│   ├── __init__.py
│   └── position_manager.py  # Pozisyon yönetimi
└── utils/                    # Yardımcı fonksiyonlar
    ├── __init__.py
    └── helpers.py           # Genel yardımcılar
```

## 📦 **Kurulum**

### **1. Gereksinimler**
```bash
pip install -r requirements.txt
```

### **2. Konfigürasyon**
`config.py` dosyasında API anahtarlarınızı ve trading parametrelerini ayarlayın:

```python
# API Anahtarları
BINANCE_API_KEY = "your_api_key"
BINANCE_API_SECRET = "your_secret_key"
TELEGRAM_BOT_TOKEN = "your_bot_token"
TELEGRAM_CHAT_ID = "your_chat_id"

# Trading Parametreleri
LEVERAGE = 20
VOLUME_THRESHOLD = 5_000_000
OI_CHANGE_THRESHOLD = 0.05
```

### **3. Sembol Listesi**
`binance_futures_symbols.json` dosyasında takip edilecek sembolleri belirtin.

## 🎯 **Strateji Detayları**

### **Multi-Factor Scoring**
```python
# Ağırlıklar
funding_rate: 25%    # Funding rate analizi
oi_change: 25%       # Open Interest değişimi
volume: 20%          # Hacim analizi
price_momentum: 15%  # Fiyat momentumu
volatility: 15%      # Volatilite analizi

# Scoring sistemi
- Her faktör 0-100 puan arası
- Ağırlıklı toplam hesaplama
- Minimum %60 güvenilirlik eşiği
```

### **Hibrit Strateji**
```python
# Trend Following
- 5 ve 20 dakikalık MA karşılaştırması
- Fiyat trend ile uyumu kontrolü
- Trend gücü hesaplama

# Mean Reversion
- RSI aşırı değer tespiti (30/70)
- Bollinger Bands pozisyonu
- Hacim bazlı doğrulama

# Sinyal Konsolidasyonu
- Trend + Mean Reversion uyumu = Güçlü sinyal
- Sadece trend = Orta sinyal
- Sadece mean reversion = Orta sinyal
```

### **Market Regime Detection**
```python
# Regime Türleri
VOLATILE: Yüksek volatilite, sıkı risk yönetimi
TRENDING_UP: Yükselen trend, agresif long
TRENDING_DOWN: Düşen trend, muhafazakar short
SIDEWAYS: Yatay piyasa, mean reversion

# Adaptif Parametreler
- Stop-loss ve take-profit ayarları
- Pozisyon süresi optimizasyonu
- Risk çarpanları
- Hacim eşikleri
```

## 🚀 **Kullanım**

### **Bot Başlatma**
```bash
python main.py
```

### **Telegram Komutları**
Bot otomatik olarak şu mesajları gönderir:
- 🤖 Bot başlangıç durumu
- 🚨 Trading alert'leri
- 🚀 Pozisyon açıldı bildirimi
- ❌ Pozisyon kapandı bildirimi
- 📊 Strateji özetleri

### **Log Dosyaları**
- `bot.log`: Detaylı log kayıtları
- Console: Canlı durum bilgileri

## ⚙️ **Konfigürasyon Parametreleri**

### **Trading Ayarları**
```python
volume_threshold = 5_000_000      # USD
oi_change_threshold = 0.05        # %5
interval = "1m"                   # 1 dakika
lookback = 10                     # 10 periyot
leverage = 20                     # 20x kaldıraç
take_profit_percent = 15.0       # %15 kar al
stop_loss_percent = 10.0         # %10 zarar kes
```

### **Strateji Ağırlıkları**
```python
MultiFactor: 40%      # Ana strateji
Hybrid: 35%           # Hibrit strateji
MarketRegime: 25%     # Market regime
```

### **Risk Yönetimi**
```python
min_confidence = 0.6              # %60 minimum güvenilirlik
position_duration_min = 5         # 5 dakika minimum
position_duration_max = 45        # 45 dakika maksimum
cooldown_duration = 300           # 5 dakika cooldown
```

## 📊 **Performans Takibi**

### **Metrikler**
- Toplam PnL
- Win rate
- Pozisyon sayısı
- Strateji performansı
- Market regime dağılımı

### **Log Analizi**
```bash
# Başarılı işlemler
grep "Pozisyon açıldı" bot.log

# Hatalar
grep "ERROR" bot.log

# Strateji sonuçları
grep "Strateji" bot.log
```

## 🔧 **Geliştirme**

### **Yeni Strateji Ekleme**
1. `strategies/base_strategy.py`'den türet
2. `analyze_symbol` metodunu implement et
3. `strategy_manager.py`'e ekle
4. Ağırlıkları ayarla

### **Yeni İndikatör Ekleme**
1. `clients/binance_client.py`'e ekle
2. `get_market_data` metodunu güncelle
3. Stratejilerde kullan

## ⚠️ **Güvenlik Notları**

- API anahtarlarını güvenli tutun
- Test ortamında deneyin
- Küçük miktarlarla başlayın
- Risk yönetimi kurallarına uyun

## 📝 **Lisans**

Bu proje eğitim amaçlıdır. Gerçek trading'de kullanmadan önce test edin.

## 🤝 **Katkıda Bulunma**

1. Fork yapın
2. Feature branch oluşturun
3. Commit yapın
4. Pull request gönderin

## 📞 **Destek**

Sorularınız için issue açın veya Telegram'dan ulaşın.

---

**⚠️ Uyarı: Bu bot eğitim amaçlıdır. Gerçek trading'de kullanmadan önce kapsamlı test yapın.**
