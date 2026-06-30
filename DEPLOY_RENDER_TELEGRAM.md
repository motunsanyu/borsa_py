# Borsa Telegram Botunu Render'da Yayina Alma Rehberi

Bu rehber, bu projedeki Telegram borsa botunu GitHub'a yukleyip Render uzerinde Web Service olarak calistirmak icindir.

Botun calisma mantigi:

```text
Telegram mesaji -> Render Web Service -> Flask webhook -> scrape_borsa.py -> Telegram cevabi
```

Kullanici Telegram'da ornegin sunu yazar:

```text
/hisse THYAO
```

Bot Mynet borsa verisini ceker ve fiyat, degisim, en yuksek, en dusuk, hacim gibi bilgileri cevap olarak gonderir.

## 1. Projedeki Dosyalar Ne Ise Yariyor?

Bu projede Render icin gerekli ana dosyalar sunlar:

```text
main.py
scrape_borsa.py
requirements.txt
render.yaml
```

Dosyalarin gorevleri:

- `main.py`: Telegram webhook isteklerini alan Flask uygulamasi.
- `scrape_borsa.py`: Borsa verisini Mynet'ten ceken modul.
- `requirements.txt`: Render'in kuracagi Python kutuphaneleri.
- `render.yaml`: Render Web Service ayarlarini tarif eden dosya.
- `telegram.py`: Eski yardimci dosya. Ana webhook sistemi artik `main.py` uzerinden calisir.

## 2. Telegram Bot Token'ini Yenile

Projede daha once token acik sekilde yazildigi icin BotFather'dan token'i yenilemek guvenli olur.

Adimlar:

1. Telegram'da `@BotFather` hesabini ac.
2. Su komutu gonder:

```text
/mybots
```

3. Botunu sec.
4. `API Token` veya `Revoke current token` secenegini kullan.
5. Yeni token'i al.

Yeni token su formata benzer:

```text
1234567890:ABCdefGHIjkl...
```

Bu token'i kimseyle paylasma ve koda yazma. Render'da Environment Variable olarak girecegiz.

## 3. GitHub'a Yukleme

Render, projeyi genelde GitHub reposundan alarak deploy eder. Bu yuzden once projeyi GitHub'a yuklemek gerekiyor.

### Yontem A: GitHub Desktop ile

Git komutlariyla ugrasmadan yapmak icin en kolay yol budur.

1. GitHub Desktop uygulamasini ac.
2. `File > Add local repository` sec.
3. Proje klasorunu sec:

```text
C:\Users\muzaf\OneDrive\Belgeler\borsa_py
```

4. Eger GitHub Desktop "This directory does not appear to be a Git repository" derse `create a repository` secenegini kullan.
5. Repository adi olarak ornegin sunu yaz:

```text
borsa-telegram-bot
```

6. Commit mesajina sunu yaz:

```text
Initial Render Telegram bot setup
```

7. `Commit to main` butonuna bas.
8. `Publish repository` butonuna bas.
9. Repo'yu public veya private yapabilirsin. Private repo da Render'a baglanabilir.

### Yontem B: Terminal ile

Proje klasorunde terminal ac:

```powershell
cd C:\Users\muzaf\OneDrive\Belgeler\borsa_py
```

Git repo henuz hazir degilse:

```powershell
git init
git add .
git commit -m "Initial Render Telegram bot setup"
```

GitHub'da bos bir repository olustur. Ornegin adi:

```text
borsa-telegram-bot
```

Sonra GitHub'in verdigi remote komutunu kullan. Ornek:

```powershell
git remote add origin https://github.com/KULLANICI_ADIN/borsa-telegram-bot.git
git branch -M main
git push -u origin main
```

`KULLANICI_ADIN` kismini kendi GitHub kullanici adinla degistir.

## 4. Render'da Web Service Olusturma

1. Render hesabina gir:

```text
https://render.com
```

2. Dashboard'da `New +` butonuna tikla.
3. `Web Service` sec.
4. GitHub hesabini bagla.
5. `borsa-telegram-bot` reposunu sec.
6. Render `render.yaml` dosyasini gorurse Blueprint olarak kurulum onerebilir.

Manuel ayar girmen gerekirse:

```text
Environment: Python
Build Command: pip install -r requirements.txt
Start Command: gunicorn main:app
```

Service adi ornegin:

```text
borsa-telegram-bot
```

Deploy bolgesi olarak sana yakin bir bolge secebilirsin. Avrupa bolgesi uygundur.

## 5. Render Environment Variables

Render servis ayarlarinda `Environment` veya `Environment Variables` bolumunu ac.

Su iki degiskeni ekle:

```text
TELEGRAM_BOT_TOKEN=BotFather'dan aldigin yeni token
TELEGRAM_WEBHOOK_SECRET=kendine-ozel-gizli-bir-yol
```

Ornek:

```text
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjkl
TELEGRAM_WEBHOOK_SECRET=benim-gizli-webhook-yolum-2026
```

`TELEGRAM_WEBHOOK_SECRET` icin tahmin edilmesi zor bir deger kullan. Bosluk ve Turkce karakter kullanma.

Iyi ornek:

```text
borsa-webhook-8f42d9
```

Kotu ornek:

```text
test
```

Environment Variable'lari ekledikten sonra servisi tekrar deploy etmen gerekebilir.

## 6. Deploy Sonrasi Render URL'ini Al

Deploy tamamlaninca Render sana bir URL verir. Ornek:

```text
https://borsa-telegram-bot.onrender.com
```

Bu adrese tarayicidan girince su tarz bir cevap gormelisin:

```json
{"status":"ok"}
```

Bu cevap geliyorsa Flask uygulamasi ayakta demektir.

## 7. Telegram Webhook'u Tanitma

Telegram'a bot mesajlarini Render servisimize gondermesini soylememiz gerekiyor.

Webhook URL formati:

```text
https://api.telegram.org/botBOT_TOKEN/setWebhook?url=RENDER_URL/telegram/TELEGRAM_WEBHOOK_SECRET
```

Ornek:

```text
https://api.telegram.org/bot1234567890:ABCdefGHIjkl/setWebhook?url=https://borsa-telegram-bot.onrender.com/telegram/borsa-webhook-8f42d9
```

Bu URL'yi tarayicida ac.

Basarili olursa Telegram buna benzer bir cevap verir:

```json
{
  "ok": true,
  "result": true,
  "description": "Webhook was set"
}
```

## 8. Webhook Durumunu Kontrol Etme

Webhook dogru mu diye kontrol etmek icin:

```text
https://api.telegram.org/botBOT_TOKEN/getWebhookInfo
```

Ornek:

```text
https://api.telegram.org/bot1234567890:ABCdefGHIjkl/getWebhookInfo
```

Beklenen cevapta `url` alani Render webhook adresini gostermeli:

```json
{
  "ok": true,
  "result": {
    "url": "https://borsa-telegram-bot.onrender.com/telegram/borsa-webhook-8f42d9"
  }
}
```

## 9. Botu Telegram'da Test Etme

Telegram'da botunu ac ve su mesajlardan birini gonder:

```text
/start
```

Sonra:

```text
/hisse THYAO
```

Alternatif olarak sadece hisse kodu da yazabilirsin:

```text
ASELS
```

Bot su bilgileri dondurmelidir:

```text
THYAO

Fiyat: ...
Degisim: ...
En yuksek: ...
En dusuk: ...
AOF: ...
Hacim lot: ...
Hacim TL: ...
Saat: ...
Detay: ...
```

## 10. Sik Karsilasilan Hatalar

### Bot hic cevap vermiyor

Kontrol et:

- Render servisi deploy oldu mu?
- Render URL'inde `{"status":"ok"}` gorunuyor mu?
- `TELEGRAM_BOT_TOKEN` dogru mu?
- `TELEGRAM_WEBHOOK_SECRET` ile webhook URL'indeki gizli yol ayni mi?
- Telegram `getWebhookInfo` cevabinda hata var mi?

### Render loglarinda TELEGRAM_BOT_TOKEN hatasi var

Sebep:

```text
TELEGRAM_BOT_TOKEN environment variable eksik.
```

Cozum:

Render servis ayarlarindan `TELEGRAM_BOT_TOKEN` ekle ve yeniden deploy et.

### Hisse icin veri bulunamadi diyor

Sebep ihtimalleri:

- Hisse kodu yanlis yazildi.
- Mynet sayfa yapisi degisti.
- Borsa kapaliyken veri bos veya sifir geliyor olabilir.
- Render servisinden Mynet'e erisim anlik sorun yasiyor olabilir.

Test icin bilinen hisseler:

```text
/hisse THYAO
/hisse ASELS
/hisse GARAN
/hisse KCHOL
```

### Telegram webhook basarili ama cevap gec geliyor

Render'in ucretsiz planinda servis bir sure kullanilmazsa uykuya dalabilir. Ilk istek yavas olabilir. Daha stabil calisma icin ucretli instance veya ayrica veri cache sistemi kullanilabilir.

## 11. Ileride Gelistirme Fikirleri

Bu ilk surum her sorguda Mynet'ten canli veri ceker. Kucuk kullanim icin yeterli.

Daha sonra sunlar eklenebilir:

- Supabase'e periyodik veri yazma.
- Hisse alarm sistemi.
- `/liste` komutu.
- `/alarm THYAO 300` gibi fiyat alarmi.
- Teknik indikatorler: RSI, MACD, hareketli ortalama.
- Kanal veya grup mesajlari.

## 12. Kisa Ozet

Yapilacaklar:

1. BotFather'dan yeni token al.
2. Projeyi GitHub'a yukle.
3. Render'da Web Service olustur.
4. Environment Variable'lari ekle:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_WEBHOOK_SECRET
```

5. Deploy et.
6. Render URL'ini al.
7. Telegram `setWebhook` URL'ini tarayicida ac.
8. Telegram'da `/hisse THYAO` ile test et.

