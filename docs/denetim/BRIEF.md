# Bağımsız denetim — ortak kurallar (her denetçi için)

Bu metin her bağımsız denetçiye aynen verilir. Denetçiye ayrıca yalnızca kendi alanı ve dosya listesi verilir;
hiçbir bulgu, hipotez ya da öncelik verilmez.

## Proje

Raise the Empires Türkçe: Zynga'nın kapanmış Flash oyunu Empires & Allies için çevrimdışı yerel sunucu. Python 3.12 +
Flask sunucu (`empires-server.py` ve modüller), oyunun asıl Flash istemcisi (`assets/ZGame.109338.swf`, değiştirilmez;
`client_patches.py` küçük bayt yamaları yapar) ve Türkçe çeviri (`turkce/`). İstemci her şeyi AMF ile
`BaseService.dispatchBatch` üzerinden ister; sunucu cevaplar ve oyuncunun kaydını `mygames/save.db` (SQLite) içinde
tutar. Oyun tek kişiliktir; çok oyunculu özellikler (komşular, PvP rakipleri) yerel kayıtlar ve botlarla taklit edilir.
GPL-3.0. Proje sahibi yazılımcı değildir; kodu yapay zekâ oturumları yazar, sahibi oyunda dener.

Denetlenen kod: `C:\Users\Avukat Emre Aydoğdu\Desktop\Raise\raisetheempires-pr`, dal `denetim-1`, commit `a4de86e`.
Python: `C:\Users\Avukat Emre Aydoğdu\Desktop\Raise\venv312\Scripts\python.exe`. Testler depo kökünden:
`../venv312/Scripts/python.exe -m pytest -q` (bugün 147 test geçiyor).

## Bağımsızlık (zorunlu)

- Okuyabileceklerin: depodaki kod, testler, oyun verisi (`gamesettings-converted.json`, `questsettings-converted.json`,
  `assets/`, `allies/`, `mods/`), `README.md`, `README.en.md`, `FLASH.md`, `SERVERS.md`.
- **Okuma yasağı:** `docs/` altındaki öteki raporlar, `git log` / `git show` ile commit mesajları ve eski farklar,
  GitHub issue ve PR'ları, depo dışındaki notlar. Vardığın her sonuç kendi okumanla ve kendi hesabınla olmalı.
- **Dokunma yasağı:** depodaki hiçbir dosyayı değiştirme (yalnızca kendi rapor dosyanı ve `docs/denetim/hesap/<alan>/`
  altındaki betiklerini yazabilirsin), commit atma, dal değiştirme. Oyuncunun gerçek kurulumuna
  (`C:\Users\Avukat Emre Aydoğdu\Desktop\Raise\TurkceOyun`, içindeki `mygames` ve çalışan sunucu) hiç dokunma, okuma
  da.
- Test ve küçük Python betikleri çalıştırmak serbest. İstemcinin bir alanı nasıl okuduğunu görmek için
  `turkce/araclar/abc.py <swf> strings|classes|method|refs <regex>` kullanılabilir (swf: `assets/ZGame.109338.swf`).

## Yöntem

- Kodu satır satır oku; her bulguyu **kodla kanıtla** (dosya:satır ve kısa alıntı). Mümkünse küçük bir betikle
  **çalıştırarak** göster (komut ve çıktısı). Betikleri `docs/denetim/hesap/<alan>/` altına koy ki yeniden
  çalıştırılabilsin.
- Kanıtlanmış bulguyu tahminden ayır: her bulguya güven derecesi ver (kesin / yüksek / olası).
- Her alanda şunları ara: doğruluk hataları, oyuncunun kaydını bozan ya da kaybettiren yollar, çökme yolları
  (istemciyi gri ekranda ya da "net status failure" ile bırakan hatalar), istemcinin beklediği cevap biçimine
  uymayan cevaplar, yarış koşulları, güvenlik (yerel ağdan erişim, dosya yolu, CSRF, güvenilmeyen veri), performans
  tuzakları, hata işleme boşlukları, test boşlukları (test var ama yanlış şeyi mi ölçüyor?), belge ile kod
  uyumsuzluğu.
- Oyunun asıl davranışını ölçüt al: istemcinin ne gönderdiği ve ne beklediği (abc.py ile), oyun verisindeki
  kurallar.

## Önem ölçeği

- **Kritik:** kayıt kaybı, güvenlik açığı ya da oyunu oynanamaz hâle getiren hata; hemen düzeltilmeli.
- **Yüksek:** oyuncunun düzenli karşılaşacağı yanlış davranış (yanlış ödül, donma, çökme) ya da ciddi sapma.
- **Orta:** belirli koşullarda görülen hata, bakım riski.
- **Düşük:** küçük tutarsızlık, iyileştirme fırsatı.

## Rapor biçimi (Türkçe; Markdown; dosya adı görevde verilir)

```
# <Alan> — Bağımsız denetim raporu
Denetçi: bağımsız denetçi (<alan>). Kaynak: denetim-1 @ a4de86e. Tarih: <gün>.

## Özet
Puan (0-10) ve gerekçesi; en önemli 3-5 nokta, yazılımcı olmayan biri anlayacak dille.

## Bulgular
Her bulgu: kimlik (<KISALTMA>-01 ...), başlık, önem, güven, dosya:satır, kanıt (alıntı / komut ve çıktı),
oyuncuya etkisi (somut bir senaryo), önerilen düzeltme.

## Sağlam bulunanlar
Neye baktın ve doğru buldun (kanıtıyla, kısaca).

## Bakılamayanlar ve sınırlar
```

Kısa ve kanıtlı yaz; aynı şeyi iki kez sayma. Bulgu yoksa uydurma.
