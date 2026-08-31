# Şarkı İstek Kiosku

Misafirler QR kodu okutur, aradıkları şarkıyı bulur, "İste" der — şarkı senin
belirlediğin TEK playlist'e eklenir. Misafirler hiçbir zaman Spotify'a giriş
yapmaz, senin token'ını görmez, diğer playlist'lerine dokunamaz. Backend sadece
tek bir işlemi yapabilir: `TARGET_PLAYLIST_ID`'ye şarkı eklemek.

## Kurulum (bir kere yapılır)

1. **Spotify uygulaması oluştur**
   https://developer.spotify.com/dashboard → "Create app"
   - Redirect URI: deploy edeceğin adres + `/callback`
     (yerelde test için: `http://localhost:8888/callback`)
   - Client ID ve Client Secret'ı kopyala.

2. **Hedef playlist'i oluştur ve ID'sini al**
   Spotify'da playlist'i aç → paylaş → linki kopyala.
   Link şuna benzer: `https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M`
   ID, `playlist/` ile `?` arasındaki kısım: `37i9dQZF1DXcBWIGoYBM5M`

3. **.env dosyasını doldur**
   `.env.example` dosyasını `.env` olarak kopyala, kendi bilgilerini gir.

4. **Bağımlılıkları kur ve çalıştır**
   ```
   pip install -r requirements.txt
   python app.py
   ```

5. **Deploy sonrası: bir kere kendi hesabınla giriş yap**
   Canlıdaki `/login` adresine git (adım 6'daki adres + `/login`), kendi
   Spotify hesabınla onayla. `/callback` sayfası sana bir
   `SPOTIFY_REFRESH_TOKEN` değeri gösterecek — bunu hosting panelindeki
   ortam değişkenlerine ekle (adım 6'da nasıl olduğu anlatılıyor). Bu
   sayede servis her yeniden başladığında tekrar giriş yapman gerekmez.

6. **Render'a ücretsiz deploy — adım adım**
   1. Kodu bir GitHub reposuna yükle (Render, GitHub bağlantısıyla deploy
      ediyor — repo public ya da private olabilir).
   2. https://render.com → hesap aç (GitHub ile giriş yapabilirsin).
   3. Dashboard'da **New +** → **Web Service**.
   4. Reponu seç, Render otomatik Python projesi olarak tanır.
   5. Ayarlar:
      - **Name:** `pizzarya-song-request` gibi bir isim (bu, URL'inin
        parçası olur: `https://pizzarya-song-request.onrender.com`)
      - **Build Command:** `pip install -r requirements.txt`
      - **Start Command:** `gunicorn app:app` *(requirements.txt'ye
        `gunicorn` eklemeyi unutma — aşağıda var)*
      - **Instance Type:** **Free**
   6. **Environment** sekmesinden şu değişkenleri ekle:
      - `SPOTIFY_CLIENT_ID`
      - `SPOTIFY_CLIENT_SECRET`
      - `SPOTIFY_REDIRECT_URI` → `https://pizzarya-song-request.onrender.com/callback`
      - `TARGET_PLAYLIST_ID`
      (`SPOTIFY_REFRESH_TOKEN`'ı henüz ekleme — adım 5'i tamamlayınca ekleyeceksin.)
   7. **Create Web Service** — Render build alıp deploy eder (birkaç dakika sürer).
   8. Spotify Developer Dashboard'a dön, o app'in **Redirect URI**'sini
      `https://pizzarya-song-request.onrender.com/callback` olarak güncelle.
   9. Şimdi adım 5'i canlı adreste yap: `.../login` → onayla → çıkan
      `SPOTIFY_REFRESH_TOKEN` değerini kopyala → Render'ın Environment
      sekmesine ekle → kaydet (Render otomatik yeniden deploy eder).

   **Ücretsiz katmanın huyu:** 15 dakika istek gelmezse servis uyur, ilk
   istek geldiğinde uyanması 30-60 saniye sürebilir. Etkinlikten 5 dakika
   önce sayfayı bir kere sen aç, misafirler geldiğinde zaten uyanık olsun.
   Disk kalıcı değil ama artık token env var'da olduğu için bu sorun değil.

7. **QR kodu üret**
   ```
   python qr_generate.py https://pizzarya-song-request.onrender.com
   ```
   Çıkan `song_request_qr.png` dosyasını yazdır, masaya koy.

## Güvenlik mantığı

- Guest tarafında **hiç** Spotify kimlik bilgisi yok — sadece arama kutusu.
- Backend, senin token'ınla sadece `sp.playlist_add_items(TARGET_PLAYLIST_ID, ...)`
  çağırır. Kodda başka hiçbir Spotify write-işlemi yok — silme, düzenleme,
  başka playlist'e erişim mümkün değil çünkü kod bunu hiç yapmıyor.
- IP başına 45 saniyede bir istek sınırı ve aynı şarkının 20 dakikada bir
  eklenmesi kısıtlaması var (spam / art arda aynı şarkı önlemi).

## Kolayca eklenebilecek geliştirmeler

- **Moderasyon kuyruğu:** `/api/request` doğrudan eklemek yerine bir bekleme
  listesine yazsın, sen ayrı bir `/admin` sayfasından onaylayınca eklensin.
- **Açık içerik filtresi:** Spotify API'sindeki `explicit` alanını kontrol
  edip filtreleyebilirsin.
- **Süre limiti:** Gece belirli saatten sonra `/api/request`'i kapatmak.
