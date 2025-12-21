"""Region code mappings from FIPS 10-4 to ISO 3166-2.

Matomo uses MaxMind GeoIP which historically returned FIPS 10-4 region codes.
Umami expects ISO 3166-2 subdivision codes.

This mapping converts common FIPS codes to ISO 3166-2 codes.
US and CA already use ISO codes in Matomo, so they're not included.
"""

from typing import Final

# France: Old regions (pre-2016) to new regions (post-2016 reform)
# France merged 22 regions into 13 in 2016
REGION_FIPS_TO_ISO: Final[dict[str, dict[str, str]]] = {
    "FR": {
        "97": "NAQ",  # Aquitaine -> Nouvelle-Aquitaine
        "98": "ARA",  # Auvergne -> Auvergne-Rhône-Alpes
        "99": "NOR",  # Basse-Normandie -> Normandie
        "A1": "BFC",  # Bourgogne -> Bourgogne-Franche-Comté
        "A2": "BRE",  # Bretagne
        "A3": "CVL",  # Centre -> Centre-Val de Loire
        "A4": "GES",  # Champagne-Ardenne -> Grand Est
        "A5": "20R",  # Corse
        "A6": "BFC",  # Franche-Comté -> Bourgogne-Franche-Comté
        "A7": "NOR",  # Haute-Normandie -> Normandie
        "A8": "IDF",  # Île-de-France
        "A9": "OCC",  # Languedoc-Roussillon -> Occitanie
        "B1": "NAQ",  # Limousin -> Nouvelle-Aquitaine
        "B2": "GES",  # Lorraine -> Grand Est
        "B3": "OCC",  # Midi-Pyrénées -> Occitanie
        "B4": "HDF",  # Nord-Pas-de-Calais -> Hauts-de-France
        "B5": "PDL",  # Pays de la Loire
        "B6": "HDF",  # Picardie -> Hauts-de-France
        "B7": "NAQ",  # Poitou-Charentes -> Nouvelle-Aquitaine
        "B8": "PAC",  # Provence-Alpes-Côte d'Azur
        "B9": "ARA",  # Rhône-Alpes -> Auvergne-Rhône-Alpes
        "C1": "GES",  # Alsace -> Grand Est
    },
    # China: FIPS to ISO 3166-2
    "CN": {
        "01": "AH",  # Anhui
        "02": "ZJ",  # Zhejiang
        "03": "JX",  # Jiangxi
        "04": "JS",  # Jiangsu
        "05": "JL",  # Jilin
        "06": "QH",  # Qinghai
        "07": "FJ",  # Fujian
        "08": "HL",  # Heilongjiang
        "09": "HA",  # Henan
        "10": "HE",  # Hebei
        "11": "HN",  # Hunan
        "12": "HB",  # Hubei
        "13": "XJ",  # Xinjiang
        "14": "XZ",  # Xizang (Tibet)
        "15": "GS",  # Gansu
        "16": "GX",  # Guangxi
        "18": "GZ",  # Guizhou
        "19": "LN",  # Liaoning
        "20": "NM",  # Nei Mongol (Inner Mongolia)
        "21": "NX",  # Ningxia
        "22": "BJ",  # Beijing
        "23": "SH",  # Shanghai
        "24": "SX",  # Shanxi
        "25": "SD",  # Shandong
        "26": "SN",  # Shaanxi
        "28": "TJ",  # Tianjin
        "29": "YN",  # Yunnan
        "30": "GD",  # Guangdong
        "31": "HI",  # Hainan
        "32": "SC",  # Sichuan
        "33": "CQ",  # Chongqing
    },
    # Germany: FIPS to ISO 3166-2
    "DE": {
        "01": "BW",  # Baden-Württemberg
        "02": "BY",  # Bayern (Bavaria)
        "03": "HB",  # Bremen
        "04": "HH",  # Hamburg
        "05": "HE",  # Hessen
        "06": "NI",  # Niedersachsen
        "07": "NW",  # Nordrhein-Westfalen
        "08": "RP",  # Rheinland-Pfalz
        "09": "SL",  # Saarland
        "10": "SH",  # Schleswig-Holstein
        "11": "BB",  # Brandenburg
        "12": "MV",  # Mecklenburg-Vorpommern
        "13": "SN",  # Sachsen
        "14": "ST",  # Sachsen-Anhalt
        "15": "TH",  # Thüringen
        "16": "BE",  # Berlin
    },
    # Russia: FIPS to ISO 3166-2 (partial - most common regions)
    "RU": {
        "48": "MOW",  # Moscow City
        "66": "SPE",  # Saint Petersburg
        "47": "MOS",  # Moscow Oblast
    },
    # Spain: FIPS to ISO 3166-2
    "ES": {
        "51": "AN",  # Andalucía
        "52": "AR",  # Aragón
        "53": "AS",  # Asturias
        "54": "IB",  # Islas Baleares
        "55": "PV",  # País Vasco
        "56": "CN",  # Canarias
        "57": "CB",  # Cantabria
        "58": "CL",  # Castilla y León
        "59": "CM",  # Castilla-La Mancha
        "60": "CT",  # Cataluña
        "61": "EX",  # Extremadura
        "62": "GA",  # Galicia
        "63": "MD",  # Madrid
        "64": "MC",  # Murcia
        "65": "NC",  # Navarra
        "66": "RI",  # La Rioja
        "67": "VC",  # Valencia
    },
    # Italy: FIPS to ISO 3166-2
    "IT": {
        "01": "65",  # Abruzzo
        "02": "77",  # Basilicata
        "03": "78",  # Calabria
        "04": "72",  # Campania
        "05": "45",  # Emilia-Romagna
        "06": "36",  # Friuli Venezia Giulia
        "07": "62",  # Lazio
        "08": "42",  # Liguria
        "09": "25",  # Lombardia
        "10": "57",  # Marche
        "11": "67",  # Molise
        "12": "21",  # Piemonte
        "13": "75",  # Puglia
        "14": "88",  # Sardegna
        "15": "82",  # Sicilia
        "16": "52",  # Toscana
        "17": "32",  # Trentino-Alto Adige
        "18": "55",  # Umbria
        "19": "23",  # Valle d'Aosta
        "20": "34",  # Veneto
    },
    # Belgium: FIPS to ISO 3166-2
    "BE": {
        "01": "VAN",  # Antwerpen
        "03": "BRU",  # Brussels
        "04": "WHT",  # Hainaut
        "05": "WLG",  # Liège
        "06": "VLI",  # Limburg
        "07": "WLX",  # Luxembourg
        "08": "WNA",  # Namur
        "09": "VOV",  # Oost-Vlaanderen
        "10": "VBR",  # Vlaams-Brabant
        "11": "VWV",  # West-Vlaanderen
        "12": "WBR",  # Brabant wallon
    },
    # Netherlands: FIPS to ISO 3166-2
    "NL": {
        "01": "DR",  # Drenthe
        "02": "FL",  # Flevoland
        "03": "FR",  # Friesland
        "04": "GE",  # Gelderland
        "05": "GR",  # Groningen
        "06": "LI",  # Limburg
        "07": "NB",  # Noord-Brabant
        "09": "NH",  # Noord-Holland
        "10": "OV",  # Overijssel
        "11": "UT",  # Utrecht
        "13": "ZE",  # Zeeland
        "14": "ZH",  # Zuid-Holland
    },
    # Switzerland: FIPS to ISO 3166-2
    "CH": {
        "01": "AG",  # Aargau
        "02": "AI",  # Appenzell Innerrhoden
        "03": "AR",  # Appenzell Ausserrhoden
        "04": "BE",  # Bern
        "05": "BL",  # Basel-Landschaft
        "06": "BS",  # Basel-Stadt
        "07": "FR",  # Fribourg
        "08": "GE",  # Genève
        "09": "GL",  # Glarus
        "10": "GR",  # Graubünden
        "11": "JU",  # Jura
        "12": "LU",  # Luzern
        "13": "NE",  # Neuchâtel
        "14": "NW",  # Nidwalden
        "15": "OW",  # Obwalden
        "16": "SG",  # Sankt Gallen
        "17": "SH",  # Schaffhausen
        "18": "SO",  # Solothurn
        "19": "SZ",  # Schwyz
        "20": "TG",  # Thurgau
        "21": "TI",  # Ticino
        "22": "UR",  # Uri
        "23": "VD",  # Vaud
        "24": "VS",  # Valais
        "25": "ZG",  # Zug
        "26": "ZH",  # Zürich
    },
}


def convert_region_to_iso(country: str, fips_region: str) -> str:
    """Convert a FIPS region code to ISO 3166-2 format.

    Args:
        country: ISO 3166-1 alpha-2 country code (uppercase)
        fips_region: FIPS 10-4 region code

    Returns:
        ISO 3166-2 region code, or original code if no mapping exists
    """
    country_mappings = REGION_FIPS_TO_ISO.get(country, {})
    return country_mappings.get(fips_region, fips_region)
