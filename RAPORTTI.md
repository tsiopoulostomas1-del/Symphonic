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

### 6.11.2026

Korjattu isohkoja bugeja main_window.py, services, settings, subsonic yms.

- Kappaleet ja albumit latautuvat nyt 500 sivun välein, joten kirjastot voivat ylittää vanhat 5 000 kappaleen/500 albumin rajoitukset.

- Käynnistyskirjaston lataus, sanoitusten haku ja scrobble-toisto tapahtuvat nyt taustalla. Scrobble-toistot lähetetään riittävän todellisen toistoajan jälkeen. Eteenpäin kelaaminen ei laukaise niitä.

- Sanoitusten vara-URL-osoitteet koodaavat artistin ja kappaleen nimet oikein.

- Windowsissa tallennetut salasanat on suojattu DPAPI:lla.

    OSA 2

        - Jaettu main_window.py neljään tiedostoon jotta on helpompi kehittää ja ylläpitää sovellusta.

        - Lisätty pieni minimaalinen napautus animaatio kun painaa jotain albumia.

        - Lisätty ominaisuus jolla säästetään internettiä, jos sovellus lataa albumien kuvat, se ei lataa niitä uudestaan verkosta, vaan tiedostosta.

    OSA 3

        - Lisätty muutama teksti Log In / Settings osioon, aina 2.5 sekunnin jälkeen vaihtuu teksti toiseen pienellä fade in animaatiolla.

### 9.11.2026

Korjattu sovelluksessa muutama error ja bugi jonka takia kirjasto kuten albumit ja muut asiat eivät latautuneet

- Ohjelma lataa nyt oikein tiedot

- Vaihdoin kappaleiden haun tyhjästä search3-haun kyselystä albumien kappalelistojen hakuun app/subsonic.py.

- Lisäsin tarkemmat lataustilat ja virheilmoituksen, jos odotettu API-vastaus puuttuu, sekä tein tilatekstistä näkyvämmän app/window_ui.py.

    OSA 4

    - Haku ja artistitietojen lataus toimivat taustalla, joten ne eivät jumita käyttöliittymää.

    - Hakutuloksen toisto käyttää valittua kappaletta suoraan eikä hae tuloksia uudelleen.

    - Kun avaat sovelluksen, se skaalautuu Full Screen moodissa, eli sovellus ei ole pienennettynä ikkunana.


    OSA 5

    Tehtäväpalkissa sovelluksessa näkyy Play/Pause, Previous ja Next painikkeet. Toimivat myös oikein.

    OSA 6

    Toiston tauottamiseen ja jatkamiseen lisättiin lyhyt äänenvoimakkuuden häivytys. Häivytys säilyttää käyttäjän valitseman äänenvoimakkuuden.


### 10.11.2026

    OSA 7 

Tänään on enimmäkseen suunniteltu seuraavia vaiheita ja opeteltu ja luettu koodia läpi. Mahdollisesti pieniä muutoksia tulossa.

    OSA 8

    Lisätty kolme erilaista kieltä sovellukseen, jotka voi vaihtaa Asetukset valikosta sovelluksessa.

    Kielet:

        - Suomi
    
        - Englanti (Vakio)

        - Venäjä

    Huom. Tulen lisäämään myöhemmin enemmän.


### 11.11.2026

    OSA 9

    Lisätty muutama kieli vielä lisää kuten ranska, hollanti, kreikka, unkari yms.

### 13.11.2026

    OSA 10

    Lisätty muutama teema sovellukseen "UI Settings" valikkoon

        - Ember

        - Violet

        - Midnight Cyan

        -  Soft Light

    Sovellukselle lisätty myös logo jota tullaan vielä korjailemaan graafisesti.

    OSA 11

    Lisätty Shuffle albumeille, genre valikko, fixattu pikku bugeja, Korjailtu playbaarin emojikokoja, toimivuutta ja selkeyttä. 