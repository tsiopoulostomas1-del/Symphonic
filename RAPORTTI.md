# Symphonic — Projektiraportti

**Tekijä:** Tomas Tsiopoulos
**Projekti:** Symphonic desktop music player
**Ajanjakso:** 30.10 – 18.12, 7 viikkoa
**Ohjaaja:** [Ohjaajan nimi]

---

## 1. Tiivistelmä

Symphonic on musiikkisoitin, jolla voit yhdistää paikalliseen tai ulkoiseen palvelimeen IP-osoitteella, käyttäjätunnuksella ja salasanalla. Sovellus on suunniteltu Navidromelle ja mahdollisesti
myöhemmin Jellyfinille. Tavoitteena on saada sovelluksesta riittävän toimiva, minimaalisesti bugeja, paljon toimivuutta, mutta silti panostaen siihen, että sovellusta on helppo käyttää.

## 2. Lähtötilanne ja tausta

### 2.1 Ongelma

Olin halunnut jo tehdä pitkään oman musiikkisoittimen, koska kaikkissa muissa sovelluksissa oli paljon bugeja, virheitä, visuaalisia ongelmia ja ominaisuuksia, jota normaali käyttäjä ei oikeastaan tarvinnut. Siksi päätin aloittaa tämän sovelluksen kehittämisen.

### 2.2 Ratkaisu
Minun mielestä Symphonic ratkaisee sen, että sovellusta on todella helppo käyttää ei tarvitse miettiä paljon käyttöä. Myös iso ominaisuus mitä muissa sovelluksissa ei ole niin on Lyrics eli sanoitukset.

### 2.3 Lähtötilanne projektin alussa

Sovellus oli jo 60–70% valmis. On jo tehty: streaming, selaus, soittojono, lyriikat, tykkäykset, soittolistat, scrobblaus, artistibiot.

## 3. Tekninen toteutus

### 3.1 Teknologiat
- Python 3.13
- PySide6 (Qt 6)
- Subsonic API / Navidrome
- LRCLIB (synkronoidut lyriikat)
- Last.fm API (artistibiot)

### 3.2 Arkkitehtuuri
Kaikki Python tiedostot sovelluksesta.

Tällä hetkellä: main.py, main_window.py, player.py, subsonic.py, settings.py, style.qss, widgets/settings_dialog.py
Huom: Tiedostoja tullaan jakamaan PIENEMPIIN osiin.

### 3.3 Keskeiset toiminnallisuudet
- albumit, artistit, kappaleet -selaus
- Streaming
- Soittojono
- Lyriikat synkronoituna
- Tykkäykset, soittolistat
- Artistibiot
- Scrobblaus

### 3.4 Kuvakaappaukset


## 4. Tavoitetila 7 viikon jälkeen

### 4.1 Mitä valmistuu
- Sovellus on vakaa ja jaettava (.exe-asennusohjelma)
- Koodi on jaettu selkeisiin moduuleihin
- Perustoiminnot testattu
- Dokumentaatio (README, käyttöohje) valmis

### 4.2 Mitä EI tehdä

- Ei mobiiliversiota
- Ei offline-latausta

## 5. Työsuunnitelma viikoittain



## 6. Riskit ja niiden hallinta

| Riski | Todennäköisyys | Vaikutus | Hallintakeino |
|---|---|---|---|
| LRCLIB API alhaalla | Keskitaso | Lyriikat eivät toimi | Fallback lyrics.ovh, virheilmoitus käyttäjälle |
| Aika ei riitä kaikkeen | Korkea | Osa ominaisuuksista jää kesken | Priorisointi: vakaus > ominaisuudet |
| Koodi on liian keskittynyttä | Korkea | Refaktorointi vie aikaa | Aloitetaan viikolla 1 |
| Testaus jää vähäiseksi | Keskitaso | Bugeja jää julkaisuun | Päivittäinen käyttö + kaverin testaus |

## 7. Arviointikriteerit

Miten mittaan projektin onnistumista?

- Sovellus käynnistyy alle 2 sekunnissa
- Kaikki keskeiset toiminnot toimivat ilman kaatumisia
- 1 tunnin testiajo ilman virheitä
- Asennusohjelma toimii puhtaalla Windows-koneella
- Koodi on jaettu moduuleihin (ei yhtään tiedostoa yli 500 riviä)
- README ja käyttöohje ovat olemassa


### 2.11.2026

Siistetty bugeja, luettu koodia läpi tarkemmin ja dokumentointia.

### 3.11.2026

Lisätty Kirjaudu ulos "Log Out" ominaisuus, käyttäjä voi halutessaan vaihtaa IP osoitetta yms.

### 4.11.2026 

Aloitin puhtaalta pöydältä, viimeiset 5 päivää lisäsin muutamia ominaisuuksia, mutta sekoitin, niin paljon sovellusta, että oli pakko palata Gitin avulla takaisin.

Luen nyt koodin kunnolla läpi ja pidän pienen tauon koodaamisesta ja mietin mikä on tärkeää tälle sovellukselle.

### 5.11.2026

Muutettu sovelluksen tyyliä hieman, lisätty scroll viivaan valkoista väriä, muutettu painikkeiden emojia ja hover / pääväriä paremmaksi. 
Muutama emoji vaihdettu minimaalisemmaksi. Vähennetty border-radius Scroll baarista, lisätty border-radius joihinkin nappeihin.