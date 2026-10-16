@echo off
rem Raise the Empires - Turkce + hata duzeltmeleri
cd /d "%~dp0"
set PY=..\venv312\Scripts\python.exe
set URL=http://127.0.0.1:5005/

rem Oyun zaten aciksa ikinci bir sunucu baslatma, sadece pencereyi ac
curl -s -o nul %URL% && goto tarayici

echo Kayit yedekleniyor...
"%PY%" yedekle.py || (echo Yedek alinamadi, oyun baslatilmadi. & pause & exit /b 1)

echo Oyun baslatiliyor, lutfen bekleyin...
echo Bu pencereyi oyun bitene kadar KAPATMAYIN.
start "" /b "%PY%" "kod\empires-server.py" --no-popup --no-crash-log > "mygames\sunucu.log" 2>&1

set /a deneme=0
:bekle
timeout /t 2 /nobreak > nul
curl -s -o nul %URL% && goto tarayici
set /a deneme+=1
if %deneme% lss 60 goto bekle
echo.
echo HATA: Oyun sunucusu 2 dakikada acilmadi. Kayit dosyasinin son satirlari:
powershell -NoProfile -Command "Get-Content 'mygames\sunucu.log' -Tail 25"
pause
exit /b 1

:tarayici
rem --no-sandbox: eski Chromium 82, Windows 11'in yeni surumlerinde onsuz gri ekranda kaliyor.
rem --proxy-server: oyun penceresi internete cikamaz, sadece bu bilgisayardaki oyun sunucusuna baglanir.
start "" "chromium\chrome.exe" --user-data-dir="%~dp0mygames\chromium-profile" --allow-outdated-plugins --no-sandbox --proxy-server=127.0.0.1:9 --no-first-run --disable-background-networking --app=%URL%
echo Oyun acildi. Oyunu kapattiktan sonra bu pencereyi kapatabilirsiniz.
pause > nul
