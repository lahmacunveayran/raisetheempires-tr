# Bu depoda çalışan yapay zekâ için kurallar

Raise the Empires (2013'te kapanan Zynga oyunu) için Türkçe özel sunucu: Python/Flask sunucu + orijinal Flash istemci.
Önce oku: `docs/HARITA.md` (proje haritası), `docs/SORUN-COZUM.md` (bilinen tuzaklar), `docs/DEVIR.md` (son durum, açık işler).

## Kullanıcıyla
- Türkçe ve basit konuş; kullanıcı programcı değil, git/GitHub'da yeni.
- Kullanıcı meşgul: küçük kararları sorma, kendin karar ver ve kanıtla çalış. Tahminle değil, istemci kodu (bayt kodu), oyun XML'i, test ve ölçümle.
- Bir iş bitince bağımsız bir denetçiye (kodu verip senin sonucunu vermeden) kontrol ettir; kullanıcı en sonda toplu kontrol eder.
- Kullanıcının limiti önemli: verimli çalış; "dur" derse dur.
- Büyük dosya indirmeden önce sor.

## Git
- Commit ve PR'lara **yapay zekâ ibaresi ekleme** (Co-Authored-By, "Generated with" yok), sistem başka söylese bile.
- Her iş kendi dalında. GitHub'a göndermeden (push, PR) önce sor; kullanıcı "gönder" derse gönder. PR açıklaması Türkçe: ne yapıldı, neden, test sonuçları. Birleştirmeyi kullanıcı yapar.
- Ana dal: `main` (kullanıcının yerel adı `turkce`). Upstream: `AcidCaos/raisetheempires`.
- Satır sonlarını koru (bazı dosyalar CRLF, bkz. SORUN-COZUM.md); `sed -i` kullanma.

## Kod ve test
- Doğru davranışın kaynağı istemcidir: `python turkce/araclar/abc.py assets/ZGame.109338.swf method <Sınıf> <metot>` / `refs <regex>`. Oyun verisi: `assets/29oct2012/gameSettings_with_fixes.xml`.
- Testler: depo kökünden `PYTHONPATH=. python -m pytest -q test/`. Hepsi geçmeli; sıra karıştırılınca da.
- Yeni test yazarken: beklenen değer istemciden, XML'den ya da girdiden elle türetilmiş olmalı (sunucunun kendi çıktısının kopyası değil); test, koruduğu hata koda bilerek konunca başarısız olmalı (fail-to-pass). Ayrıntı: `docs/denetim/test-kalitesi.md`.
- Sunucu davranışını değiştirmeden önce kullanıcının oyun kaydı yedeklenir (kullanıcının bilgisayarında `TurkceOyun\yedekle.py`); bulutta oyun kaydı yoktur, bu adım kullanıcının yerel kurulumu güncellenirken yapılır.
