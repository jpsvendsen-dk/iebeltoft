# Nissepige: prøve på låge 1

Kun video `N8NcQzMQN_U` indlæser danseren. Andre låger og kalenderens første
indlæsning henter hverken dansemoduler, rytmeplan eller atlas.

Grafikken er en original imagegen-illustration med 16 cutouts, samlet af
`scripts/build_elf_assets.py` til et lossless WebP-atlas på cirka 638 KB.
Prompten ligger i `static/jul2026/elf-artwork-prompt.txt`. Der anvendes ingen
lydoptagelse, mikrofon eller udtræk af YouTube-lyd.

## Vigtig status på rytmen

`elf-feliz-navidad-v1.json` er mærket `draft-needs-listening`. Tempoet 148,75 BPM
er et foreløbigt estimat. Første slag (0,12 s), slutpunkt og de seks skiftende
dansefraser er **ikke** verificeret ved gennemlytning af den præcise video.
Der er ikke registreret musikpauser eller vers/omkvæd. Dansen følger videoens
afspilningstid, men det er ikke det samme som en verificeret slagtransskription.
Opgrader ikke denne status eller påstå en præcision på 100 ms uden en øretest.

Åbn låge 1 i `/admin/jul2026`, og afspil videoen. Under nissen findes
“Justér rytmen i prøven”. Tempo/første slag kan ændres under afspilning.
“Markér et taktslag nu” måler medianintervallet af mindst fire tryk på slagene.
Indstillingerne er midlertidige og gælder kun den åbne adminprøve; de gemmes
ikke til andre besøgende. Afspil hele sangen og kontrollér især start, midte
og slutning. Ved tempoændringer oprettes flere `{time, beat}`-ankre i JSON,
og pauser registreres i `rests`. Gem derpå de verificerede værdier i kilden,
opdatér filens version og alle berørte `?v=`-referencer, og udgiv ændringen.

## Drift og kontrol

YouTube-state styrer start/pause/buffering/slut. PlayerClock aflæser videoens
tid og hastighed hvert 150 ms og interpolerer kun kort mellem aflæsninger.
Spoling beregner derfor figuren direkte på det nye tidspunkt. Ved stagneret
tid fryses figuren. Pause, skjult fane og reduceret bevægelse stopper rAF.
Lukning og lågeskift fjerner eventlyttere og afviser forsinkede indlæsninger.

`tests/elf-client.mjs` tester synkronisering og bevægelsesberegning med en
simuleret afspiller. `tests/calendar-client.mjs` tester kalenderintegration.
De tests validerer ikke den musikalske placering af taktslagene. Test på en
fysisk iPhone/Safari og faktisk gennemlytning skal rapporteres særskilt.
