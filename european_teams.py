"""
european_teams.py — Diccionario de equipos de ligas europeas
=============================================================
Ligas incluidas:
- Eredivisie (Holanda)
- Primeira Liga (Portugal)  
- Süper Lig (Turquía)
- Scottish Premiership (Escocia)
- Belgian Pro League (Bélgica)
- Austrian Bundesliga (Austria)
- Swiss Super League (Suiza)
- Ekstraklasa (Polonia)
- Czech First League (República Checa)
- Superliga (Dinamarca)
- Allsvenskan (Suecia)
- Eliteserien (Noruega)
- Veikkausliiga (Finlandia)
- Super League (Grecia)
- SuperLiga (Serbia)
- Ukrainian Premier League (Ucrania)
- Russian Premier League (Rusia)
- Liga Profesional (Argentina) — para partidos internacionales
- Brasileirão (Brasil)
"""

EUROPEAN_TEAMS = {

    # =========================================================================
    # EREDIVISIE (HOLANDA)
    # =========================================================================
    "Ajax":                 {"city": "Ámsterdam",       "country": "Netherlands", "papers": ["De Telegraaf", "AD Sportwereld"]},
    "PSV":                  {"city": "Eindhoven",        "country": "Netherlands", "papers": ["Eindhovens Dagblad", "De Telegraaf"]},
    "Feyenoord":            {"city": "Róterdam",         "country": "Netherlands", "papers": ["AD Rotterdams Dagblad", "De Telegraaf"]},
    "AZ Alkmaar":           {"city": "Alkmaar",          "country": "Netherlands", "papers": ["Noordhollands Dagblad", "De Telegraaf"]},
    "Utrecht":              {"city": "Utrecht",          "country": "Netherlands", "papers": ["Algemeen Dagblad", "De Telegraaf"]},
    "Twente":               {"city": "Enschede",         "country": "Netherlands", "papers": ["Tubantia", "De Telegraaf"]},
    "Vitesse":              {"city": "Arnhem",           "country": "Netherlands", "papers": ["De Gelderlander", "De Telegraaf"]},
    "Groningen":            {"city": "Groninga",         "country": "Netherlands", "papers": ["Dagblad van het Noorden", "De Telegraaf"]},
    "Heerenveen":           {"city": "Heerenveen",       "country": "Netherlands", "papers": ["Leeuwarder Courant", "De Telegraaf"]},
    "Sparta Rotterdam":     {"city": "Róterdam",         "country": "Netherlands", "papers": ["AD Rotterdams Dagblad", "De Telegraaf"]},

    # =========================================================================
    # PRIMEIRA LIGA (PORTUGAL)
    # =========================================================================
    "Benfica":              {"city": "Lisboa",           "country": "Portugal", "papers": ["Record", "A Bola", "O Jogo"]},
    "FC Porto":             {"city": "Oporto",           "country": "Portugal", "papers": ["O Jogo", "Record", "A Bola"]},
    "Sporting CP":          {"city": "Lisboa",           "country": "Portugal", "papers": ["Record", "A Bola", "O Jogo"]},
    "Braga":                {"city": "Braga",            "country": "Portugal", "papers": ["Correio do Minho", "Record"]},
    "Vitória SC":           {"city": "Guimarães",        "country": "Portugal", "papers": ["Record", "A Bola"]},
    "Guimarães":            {"city": "Guimarães",        "country": "Portugal", "papers": ["Record", "A Bola"]},
    "Famalicão":            {"city": "Famalicão",        "country": "Portugal", "papers": ["Record", "A Bola"]},
    "Boavista":             {"city": "Oporto",           "country": "Portugal", "papers": ["O Jogo", "Record"]},
    "Gil Vicente":          {"city": "Barcelos",         "country": "Portugal", "papers": ["Record", "A Bola"]},
    "Casa Pia":             {"city": "Lisboa",           "country": "Portugal", "papers": ["Record", "A Bola"]},

    # =========================================================================
    # SÜPER LIG (TURQUÍA)
    # =========================================================================
    "Galatasaray":          {"city": "Estambul",         "country": "Turkey", "papers": ["Fanatik", "Fotomaç", "Milliyet"]},
    "Fenerbahçe":           {"city": "Estambul",         "country": "Turkey", "papers": ["Fanatik", "Fotomaç", "Milliyet"]},
    "Beşiktaş":             {"city": "Estambul",         "country": "Turkey", "papers": ["Fanatik", "Fotomaç", "Milliyet"]},
    "Trabzonspor":          {"city": "Trabzon",          "country": "Turkey", "papers": ["Fanatik", "Karadeniz Gazetesi"]},
    "Başakşehir":           {"city": "Estambul",         "country": "Turkey", "papers": ["Fanatik", "Fotomaç"]},
    "Sivasspor":            {"city": "Sivas",            "country": "Turkey", "papers": ["Fanatik", "Fotomaç"]},
    "Konyaspor":            {"city": "Konya",            "country": "Turkey", "papers": ["Fanatik", "Yeni Konya"]},
    "Kayserispor":          {"city": "Kayseri",          "country": "Turkey", "papers": ["Fanatik", "Yeni Kayseri"]},

    # =========================================================================
    # SCOTTISH PREMIERSHIP (ESCOCIA)
    # =========================================================================
    "Celtic":               {"city": "Glasgow",          "country": "Scotland", "papers": ["Daily Record", "The Herald", "BBC Scotland"]},
    "Rangers":              {"city": "Glasgow",          "country": "Scotland", "papers": ["Daily Record", "The Herald", "BBC Scotland"]},
    "Hearts":               {"city": "Edimburgo",        "country": "Scotland", "papers": ["Edinburgh Evening News", "Daily Record"]},
    "Hibernian":            {"city": "Edimburgo",        "country": "Scotland", "papers": ["Edinburgh Evening News", "Daily Record"]},
    "Aberdeen":             {"city": "Aberdeen",         "country": "Scotland", "papers": ["Press and Journal", "Daily Record"]},
    "Motherwell":           {"city": "Motherwell",       "country": "Scotland", "papers": ["Daily Record", "BBC Scotland"]},
    "St Mirren":            {"city": "Paisley",          "country": "Scotland", "papers": ["Daily Record", "BBC Scotland"]},
    "Dundee":               {"city": "Dundee",           "country": "Scotland", "papers": ["The Courier", "Daily Record"]},

    # =========================================================================
    # BELGIAN PRO LEAGUE (BÉLGICA)
    # =========================================================================
    "Club Brugge":          {"city": "Brujas",           "country": "Belgium", "papers": ["Het Nieuwsblad", "Het Laatste Nieuws"]},
    "Anderlecht":           {"city": "Bruselas",         "country": "Belgium", "papers": ["La Dernière Heure", "Het Laatste Nieuws"]},
    "Gent":                 {"city": "Gante",            "country": "Belgium", "papers": ["Het Nieuwsblad", "Het Laatste Nieuws"]},
    "Standard Liège":       {"city": "Lieja",            "country": "Belgium", "papers": ["La Meuse", "La Dernière Heure"]},
    "Union SG":             {"city": "Bruselas",         "country": "Belgium", "papers": ["La Dernière Heure", "Het Laatste Nieuws"]},
    "Antwerp":              {"city": "Amberes",          "country": "Belgium", "papers": ["Gazet van Antwerpen", "Het Laatste Nieuws"]},
    "Genk":                 {"city": "Genk",             "country": "Belgium", "papers": ["Het Belang van Limburg", "Het Laatste Nieuws"]},
    "Mechelen":             {"city": "Malinas",          "country": "Belgium", "papers": ["Het Nieuwsblad", "Het Laatste Nieuws"]},

    # =========================================================================
    # AUSTRIAN BUNDESLIGA (AUSTRIA)
    # =========================================================================
    "Red Bull Salzburg":    {"city": "Salzburgo",        "country": "Austria", "papers": ["Salzburger Nachrichten", "Kronen Zeitung"]},
    "Sturm Graz":           {"city": "Graz",             "country": "Austria", "papers": ["Kleine Zeitung", "Kronen Zeitung"]},
    "Rapid Wien":           {"city": "Viena",            "country": "Austria", "papers": ["Kronen Zeitung", "Der Standard"]},
    "Austria Wien":         {"city": "Viena",            "country": "Austria", "papers": ["Kronen Zeitung", "Der Standard"]},
    "LASK":                 {"city": "Linz",             "country": "Austria", "papers": ["Oberösterreichische Nachrichten", "Kronen Zeitung"]},
    "Wolfsberger AC":       {"city": "Wolfsberg",        "country": "Austria", "papers": ["Kleine Zeitung", "Kronen Zeitung"]},

    # =========================================================================
    # SWISS SUPER LEAGUE (SUIZA)
    # =========================================================================
    "Young Boys":           {"city": "Berna",            "country": "Switzerland", "papers": ["Berner Zeitung", "Blick"]},
    "Basel":                {"city": "Basilea",          "country": "Switzerland", "papers": ["Basler Zeitung", "Blick"]},
    "Zürich":               {"city": "Zúrich",           "country": "Switzerland", "papers": ["Tages-Anzeiger", "Blick"]},
    "Servette":             {"city": "Ginebra",          "country": "Switzerland", "papers": ["Tribune de Genève", "Blick"]},
    "Lugano":               {"city": "Lugano",           "country": "Switzerland", "papers": ["Corriere del Ticino", "Blick"]},
    "Grasshoppers":         {"city": "Zúrich",           "country": "Switzerland", "papers": ["Tages-Anzeiger", "Blick"]},
    "Lausanne":             {"city": "Lausana",          "country": "Switzerland", "papers": ["24 Heures", "Blick"]},
    "Luzern":               {"city": "Lucerna",          "country": "Switzerland", "papers": ["Luzerner Zeitung", "Blick"]},

    # =========================================================================
    # EKSTRAKLASA (POLONIA)
    # =========================================================================
    "Legia Warsaw":         {"city": "Varsovia",         "country": "Poland", "papers": ["Gazeta Wyborcza", "Przegląd Sportowy"]},
    "Lech Poznań":          {"city": "Poznań",           "country": "Poland", "papers": ["Głos Wielkopolski", "Przegląd Sportowy"]},
    "Wisła Kraków":         {"city": "Cracovia",         "country": "Poland", "papers": ["Gazeta Krakowska", "Przegląd Sportowy"]},
    "Raków Częstochowa":    {"city": "Częstochowa",      "country": "Poland", "papers": ["Gazeta Wyborcza", "Przegląd Sportowy"]},
    "Pogoń Szczecin":       {"city": "Szczecin",         "country": "Poland", "papers": ["Kurier Szczeciński", "Przegląd Sportowy"]},
    "Śląsk Wrocław":        {"city": "Wrocław",          "country": "Poland", "papers": ["Gazeta Wrocławska", "Przegląd Sportowy"]},

    # =========================================================================
    # CZECH FIRST LEAGUE (REPÚBLICA CHECA)
    # =========================================================================
    "Slavia Praha":         {"city": "Praga",            "country": "Czech Republic", "papers": ["Sport.cz", "iSport.cz"]},
    "Sparta Praha":         {"city": "Praga",            "country": "Czech Republic", "papers": ["Sport.cz", "iSport.cz"]},
    "Viktoria Plzeň":       {"city": "Plzeň",            "country": "Czech Republic", "papers": ["Sport.cz", "Plzeňský deník"]},
    "Baník Ostrava":        {"city": "Ostrava",          "country": "Czech Republic", "papers": ["Sport.cz", "Moravskoslezský deník"]},
    "Mlada Boleslav":       {"city": "Mladá Boleslav",   "country": "Czech Republic", "papers": ["Sport.cz", "iSport.cz"]},

    # =========================================================================
    # SUPERLIGA (DINAMARCA)
    # =========================================================================
    "FC Copenhagen":        {"city": "Copenhague",       "country": "Denmark", "papers": ["Ekstra Bladet", "BT Sport"]},
    "Brøndby":              {"city": "Brøndby",          "country": "Denmark", "papers": ["Ekstra Bladet", "BT Sport"]},
    "Midtjylland":          {"city": "Herning",          "country": "Denmark", "papers": ["Herning Folkeblad", "BT Sport"]},
    "Nordsjælland":         {"city": "Farum",            "country": "Denmark", "papers": ["Ekstra Bladet", "BT Sport"]},
    "Silkeborg":            {"city": "Silkeborg",        "country": "Denmark", "papers": ["Midtjyllands Avis", "BT Sport"]},
    "AGF":                  {"city": "Aarhus",           "country": "Denmark", "papers": ["Aarhus Stiftstidende", "BT Sport"]},

    # =========================================================================
    # ALLSVENSKAN (SUECIA)
    # =========================================================================
    "Malmö FF":             {"city": "Malmö",            "country": "Sweden", "papers": ["Sydsvenskan", "Expressen"]},
    "AIK":                  {"city": "Estocolmo",        "country": "Sweden", "papers": ["Aftonbladet", "Expressen"]},
    "Djurgården":           {"city": "Estocolmo",        "country": "Sweden", "papers": ["Aftonbladet", "Expressen"]},
    "Hammarby":             {"city": "Estocolmo",        "country": "Sweden", "papers": ["Aftonbladet", "Expressen"]},
    "IFK Göteborg":         {"city": "Gotemburgo",       "country": "Sweden", "papers": ["Göteborgs-Posten", "Expressen"]},
    "IF Elfsborg":          {"city": "Borås",            "country": "Sweden", "papers": ["Borås Tidning", "Expressen"]},

    # =========================================================================
    # ELITESERIEN (NORUEGA)
    # =========================================================================
    "Rosenborg":            {"city": "Trondheim",        "country": "Norway", "papers": ["Adresseavisen", "VG Sport"]},
    "Molde":                {"city": "Molde",            "country": "Norway", "papers": ["Romsdals Budstikke", "VG Sport"]},
    "Bodø/Glimt":           {"city": "Bodø",             "country": "Norway", "papers": ["Avisa Nordland", "VG Sport"]},
    "Brann":                {"city": "Bergen",           "country": "Norway", "papers": ["Bergens Tidende", "VG Sport"]},
    "Lillestrøm":           {"city": "Lillestrøm",       "country": "Norway", "papers": ["Romerikes Blad", "VG Sport"]},
    "Viking":               {"city": "Stavanger",        "country": "Norway", "papers": ["Stavanger Aftenblad", "VG Sport"]},

    # =========================================================================
    # SUPER LEAGUE (GRECIA)
    # =========================================================================
    "Olympiakos":           {"city": "El Pireo",         "country": "Greece", "papers": ["Sport24", "Sportime"]},
    "Panathinaikos":        {"city": "Atenas",           "country": "Greece", "papers": ["Sport24", "Sportime"]},
    "AEK Athens":           {"city": "Atenas",           "country": "Greece", "papers": ["Sport24", "Sportime"]},
    "PAOK":                 {"city": "Salónica",         "country": "Greece", "papers": ["Makedonia", "Sport24"]},
    "Aris":                 {"city": "Salónica",         "country": "Greece", "papers": ["Makedonia", "Sport24"]},
    "Atromitos":            {"city": "Atenas",           "country": "Greece", "papers": ["Sport24", "Sportime"]},

    # =========================================================================
    # SUPERLIGA (SERBIA)
    # =========================================================================
    "Red Star Belgrade":    {"city": "Belgrado",         "country": "Serbia", "papers": ["Sportski žurnal", "Večernje novosti"]},
    "Partizan":             {"city": "Belgrado",         "country": "Serbia", "papers": ["Sportski žurnal", "Večernje novosti"]},
    "FK Vojvodina":         {"city": "Novi Sad",         "country": "Serbia", "papers": ["Dnevnik", "Sportski žurnal"]},

    # =========================================================================
    # UKRANIAN PREMIER LEAGUE
    # =========================================================================
    "Shakhtar Donetsk":     {"city": "Donetsk/Kiev",     "country": "Ukraine", "papers": ["Sportarena", "Football.ua"]},
    "Dynamo Kyiv":          {"city": "Kiev",             "country": "Ukraine", "papers": ["Football.ua", "Sportarena"]},
    "Metalist":             {"city": "Járkov",           "country": "Ukraine", "papers": ["Football.ua", "Sportarena"]},

    # =========================================================================
    # ISRAEL PREMIER LEAGUE
    # =========================================================================
    "Maccabi Tel Aviv":     {"city": "Tel Aviv",         "country": "Israel", "papers": ["Sport5", "One.co.il"]},
    "Maccabi Haifa":        {"city": "Haifa",            "country": "Israel", "papers": ["Sport5", "One.co.il"]},
    "Hapoel Beer Sheva":    {"city": "Beer Sheva",       "country": "Israel", "papers": ["Sport5", "One.co.il"]},
    "Beitar Jerusalem":     {"city": "Jerusalén",        "country": "Israel", "papers": ["Sport5", "One.co.il"]},

    # =========================================================================
    # CROACIA HNL
    # =========================================================================
    "Dinamo Zagreb":        {"city": "Zagreb",           "country": "Croatia", "papers": ["Sportske novosti", "Večernji list"]},
    "Hajduk Split":         {"city": "Split",            "country": "Croatia", "papers": ["Slobodna Dalmacija", "Sportske novosti"]},
    "Rijeka":               {"city": "Rijeka",           "country": "Croatia", "papers": ["Novi list", "Sportske novosti"]},

    # =========================================================================
    # SCOTLAND / NORTHERN IRELAND
    # =========================================================================
    "Linfield":             {"city": "Belfast",          "country": "N.Ireland", "papers": ["Belfast Telegraph", "Irish News"]},
    "Glentoran":            {"city": "Belfast",          "country": "N.Ireland", "papers": ["Belfast Telegraph", "Irish News"]},

    # =========================================================================
    # LIGA PROFESIONAL (ARGENTINA) — Interamericana/Mundial
    # =========================================================================
    "River Plate":          {"city": "Buenos Aires",     "country": "Argentina", "papers": ["Olé", "La Nación Deportes"]},
    "Boca Juniors":         {"city": "Buenos Aires",     "country": "Argentina", "papers": ["Olé", "La Nación Deportes"]},
    "Racing Club":          {"city": "Avellaneda",       "country": "Argentina", "papers": ["Olé", "La Nación Deportes"]},
    "Independiente":        {"city": "Avellaneda",       "country": "Argentina", "papers": ["Olé", "La Nación Deportes"]},
    "San Lorenzo":          {"city": "Buenos Aires",     "country": "Argentina", "papers": ["Olé", "La Nación Deportes"]},
    "Estudiantes":          {"city": "La Plata",         "country": "Argentina", "papers": ["Olé", "El Día"]},

    # =========================================================================
    # BRASILEIRÃO (BRASIL)
    # =========================================================================
    "Flamengo":             {"city": "Río de Janeiro",   "country": "Brazil", "papers": ["O Globo Esporte", "Lance!"]},
    "Palmeiras":            {"city": "São Paulo",        "country": "Brazil", "papers": ["Folha de S.Paulo", "Lance!"]},
    "Fluminense":           {"city": "Río de Janeiro",   "country": "Brazil", "papers": ["O Globo Esporte", "Lance!"]},
    "Corinthians":          {"city": "São Paulo",        "country": "Brazil", "papers": ["Folha de S.Paulo", "Lance!"]},
    "Santos":               {"city": "Santos",           "country": "Brazil", "papers": ["A Tribuna", "Lance!"]},
    "Grêmio":               {"city": "Porto Alegre",     "country": "Brazil", "papers": ["Zero Hora", "Lance!"]},
    "Internacional":        {"city": "Porto Alegre",     "country": "Brazil", "papers": ["Zero Hora", "Lance!"]},
    "Atlético Mineiro":     {"city": "Belo Horizonte",   "country": "Brazil", "papers": ["Estado de Minas", "Lance!"]},
}
