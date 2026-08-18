# XST kainos stebėjimo Telegram botas

Botas kas 2 minutes (nustatoma) tikrina XST tokeno kainą per DexScreener API
ir siunčia pranešimą į Telegram, kai kaina pakinta 10–15% nuo dienos
aukščiausio/žemiausio taško (skaičiuojama nuo boto paleidimo, atsinaujina
kiekvieną dieną).

## 1. Susikurk Telegram botą

1. Telegrame susirask **@BotFather**, parašyk `/newbot`, seki instrukcijas.
2. Gausi **TELEGRAM_BOT_TOKEN** (atrodo kaip `123456789:AAExxxxxxx`).
3. Susirask **@userinfobot**, parašyk jam bet ką — jis atsakys su tavo
   **chat_id** (skaičius, pvz. `987654321`). Tai bus **TELEGRAM_CHAT_ID**.
4. Svarbu: parašyk savo naujam botui bent vieną žinutę (pvz. `/start`) —
   kitaip jis negalės tau siųsti pranešimų (Telegram taip veikia).

## 2. Rask teisingą XST kontrakto adresą (rekomenduojama)

Kadangi yra keli tokenai su simboliu "XST", saugiau nurodyti tikslų
kontrakto adresą, o ne paiešką pagal pavadinimą.

1. Eik į https://dexscreener.com
2. Paieškoje įvesk "XST" arba "Xsolu"
3. Rask porą, kurios kaina/rinkos kapitalizacija atitinka tavo programėlę
   (pagal nuotrauką: kaina ~$0.06, MC ~$65M)
4. Paspausk ant tos poros, nukopijuok **token address** (ne pair address)
5. Įrašyk jį kaip XST_TOKEN_ADDRESS kintamąjį (žr. žemiau)

Jei nenurodysi adreso, botas ieškos pagal "XST Xsolu" tekstą ir pasirinks
didžiausio likvidumo porą — tai turėtų veikti, bet adresas yra tikslesnis.

## 3. Talpinimas Railway (nemokamai)

1. Susikurk paskyrą https://railway.app (gali prisijungti per GitHub)
2. Sukurk naują GitHub repo ir įkelk šiuos failus (bot.py, requirements.txt,
   Procfile)
3. Railway → "New Project" → "Deploy from GitHub repo" → pasirink repo
4. Projekto nustatymuose (Variables) pridėk:
   - `TELEGRAM_BOT_TOKEN` = tavo boto tokenas
   - `TELEGRAM_CHAT_ID` = tavo chat id
   - `XST_TOKEN_ADDRESS` = kontrakto adresas (jei radai, žr. žingsnį 2)
   - (nebūtina) `CHECK_INTERVAL_SECONDS` = 120
   - (nebūtina) `ALERT_THRESHOLD_LOW` = 10
   - (nebūtina) `ALERT_THRESHOLD_HIGH` = 15
5. Railway automatiškai paleis `python bot.py` kaip worker procesą (be
   viešo URL — jam ir nereikia, jis tik siunčia žinutes).
6. Railway nemokamas planas turi mėnesinį kreditų limitą — šis botas,
   veikdamas 24/7 su 2 min. intervalu, sunaudos labai nedaug (paprastas
   HTTP užklausas), bet stebėk sąskaitą pirmą mėnesį.

## 4. Kaip veikia pranešimai

- Botas seka aukščiausią ir žemiausią kainą nuo paleidimo (atsinaujina
  kiekvieną dieną UTC laiku).
- Kai kaina nukrenta ≥10% nuo tos dienos aukščio → pranešimas 🔴
- Kai kaina pakyla ≥15% nuo tos dienos aukščio nuo žemumo → pranešimas 🟢🟢
  (stipresnis pažymėjimas ties 15%)
- Kad neužverstų pranešimais, tas pats "kryptis" nepersiunčiamas, kol
  pokytis nepadidėja bent 5 procentiniais punktais.

## 5. Testavimas lokaliai (nebūtina)

```bash
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."
export XST_TOKEN_ADDRESS="..."
pip install -r requirements.txt
python bot.py
```

Paleidus turėtum iškart gauti "✅ XST kainos stebėjimo botas paleistas."
pranešimą Telegrame.
