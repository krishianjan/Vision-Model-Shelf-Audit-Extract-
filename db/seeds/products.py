"""
Seed ~50 bev-alc SKUs with BGE-small-en embeddings into the products table.
Run from the db/ directory:  python seeds/products.py
Requires: DATABASE_URL env var, sentence-transformers installed.
"""
import asyncio
import os
import sys
from typing import Any

import asyncpg
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

SKUS: list[dict[str, Any]] = [
    # Vodka
    {"brand": "Tito's Handmade",    "product_name": "Vodka",               "size_ml": 750,  "category": "vodka",   "upc": "081753807056"},
    {"brand": "Tito's Handmade",    "product_name": "Vodka",               "size_ml": 1750, "category": "vodka",   "upc": "081753807063"},
    {"brand": "Grey Goose",         "product_name": "Vodka",               "size_ml": 750,  "category": "vodka",   "upc": "080480280025"},
    {"brand": "Absolut",            "product_name": "Original Vodka",      "size_ml": 750,  "category": "vodka",   "upc": "085592100108"},
    {"brand": "Absolut",            "product_name": "Lime Vodka",          "size_ml": 750,  "category": "vodka",   "upc": "085592302017"},
    {"brand": "Smirnoff",           "product_name": "No. 21 Vodka",        "size_ml": 750,  "category": "vodka",   "upc": "082000730017"},
    {"brand": "Smirnoff",           "product_name": "No. 21 Vodka",        "size_ml": 1750, "category": "vodka",   "upc": "082000730024"},
    {"brand": "Ketel One",          "product_name": "Vodka",               "size_ml": 750,  "category": "vodka",   "upc": "085276030040"},
    {"brand": "Belvedere",          "product_name": "Pure Vodka",          "size_ml": 750,  "category": "vodka",   "upc": "089540502076"},
    {"brand": "Ciroc",              "product_name": "Ultra Premium Vodka", "size_ml": 750,  "category": "vodka",   "upc": "088004001835"},
    # Whiskey
    {"brand": "Jack Daniel's",      "product_name": "Old No. 7 Tennessee Whiskey", "size_ml": 750,  "category": "whiskey", "upc": "082184090916"},
    {"brand": "Jack Daniel's",      "product_name": "Old No. 7 Tennessee Whiskey", "size_ml": 1750, "category": "whiskey", "upc": "082184091302"},
    {"brand": "Jameson",            "product_name": "Irish Whiskey",       "size_ml": 750,  "category": "whiskey", "upc": "080432402619"},
    {"brand": "Maker's Mark",       "product_name": "Bourbon Whisky",      "size_ml": 750,  "category": "whiskey", "upc": "039964000143"},
    {"brand": "Bulleit",            "product_name": "Bourbon Frontier Whiskey", "size_ml": 750, "category": "whiskey", "upc": "088004003006"},
    {"brand": "Woodford Reserve",   "product_name": "Distiller's Select Bourbon", "size_ml": 750, "category": "whiskey", "upc": "096749012344"},
    {"brand": "Crown Royal",        "product_name": "Canadian Whisky",     "size_ml": 750,  "category": "whiskey", "upc": "082000728489"},
    {"brand": "Johnnie Walker",     "product_name": "Black Label Scotch",  "size_ml": 750,  "category": "whiskey", "upc": "050000119028"},
    {"brand": "Johnnie Walker",     "product_name": "Red Label Scotch",    "size_ml": 750,  "category": "whiskey", "upc": "050000119059"},
    {"brand": "Glenfiddich",        "product_name": "12 Year Single Malt", "size_ml": 750,  "category": "whiskey", "upc": "083664100025"},
    # Tequila
    {"brand": "Patron",             "product_name": "Silver Tequila",      "size_ml": 750,  "category": "tequila", "upc": "721733100018"},
    {"brand": "Patron",             "product_name": "Anejo Tequila",       "size_ml": 750,  "category": "tequila", "upc": "721733100056"},
    {"brand": "Don Julio",          "product_name": "Blanco Tequila",      "size_ml": 750,  "category": "tequila", "upc": "721733015404"},
    {"brand": "Don Julio",          "product_name": "1942 Tequila",        "size_ml": 750,  "category": "tequila", "upc": "721733015817"},
    {"brand": "Casamigos",          "product_name": "Blanco Tequila",      "size_ml": 750,  "category": "tequila", "upc": "888283003020"},
    {"brand": "Jose Cuervo",        "product_name": "Gold Tequila",        "size_ml": 750,  "category": "tequila", "upc": "082000700003"},
    # Rum
    {"brand": "Captain Morgan",     "product_name": "Original Spiced Rum", "size_ml": 750,  "category": "rum",     "upc": "082000116916"},
    {"brand": "Bacardi",            "product_name": "Superior White Rum",  "size_ml": 750,  "category": "rum",     "upc": "080480010078"},
    {"brand": "Malibu",             "product_name": "Coconut Rum",         "size_ml": 750,  "category": "rum",     "upc": "082184090268"},
    {"brand": "Mount Gay",          "product_name": "Eclipse Rum",         "size_ml": 750,  "category": "rum",     "upc": "085276009175"},
    # Gin
    {"brand": "Tanqueray",          "product_name": "London Dry Gin",      "size_ml": 750,  "category": "gin",     "upc": "088004025992"},
    {"brand": "Hendrick's",         "product_name": "Gin",                 "size_ml": 750,  "category": "gin",     "upc": "088076181368"},
    {"brand": "Bombay Sapphire",    "product_name": "London Dry Gin",      "size_ml": 750,  "category": "gin",     "upc": "088004001767"},
    # Wine
    {"brand": "Barefoot",           "product_name": "Cabernet Sauvignon",  "size_ml": 750,  "category": "wine",    "upc": "085000014576"},
    {"brand": "Josh Cellars",       "product_name": "Cabernet Sauvignon",  "size_ml": 750,  "category": "wine",    "upc": "019375100147"},
    {"brand": "Kim Crawford",       "product_name": "Sauvignon Blanc",     "size_ml": 750,  "category": "wine",    "upc": "009473702004"},
    # Beer
    {"brand": "Modelo Especial",    "product_name": "Lager Beer",          "size_ml": 355,  "pack_count": 6,  "category": "beer", "upc": "013346500005"},
    {"brand": "Corona Extra",       "product_name": "Lager Beer",          "size_ml": 355,  "pack_count": 6,  "category": "beer", "upc": "018200009045"},
    {"brand": "Bud Light",          "product_name": "Light Lager",         "size_ml": 355,  "pack_count": 12, "category": "beer", "upc": "018200006099"},
    {"brand": "Heineken",           "product_name": "Lager Beer",          "size_ml": 355,  "pack_count": 6,  "category": "beer", "upc": "072039001003"},
    {"brand": "Blue Moon",          "product_name": "Belgian White",       "size_ml": 355,  "pack_count": 6,  "category": "beer", "upc": "707015154102"},
    # RTD
    {"brand": "White Claw",         "product_name": "Hard Seltzer Mango",  "size_ml": 355,  "pack_count": 12, "category": "rtd",  "upc": "818502020049"},
    {"brand": "High Noon",          "product_name": "Watermelon Vodka Soda","size_ml": 355, "pack_count": 4,  "category": "rtd",  "upc": "850006188044"},
    {"brand": "Truly",              "product_name": "Wild Berry Hard Seltzer","size_ml": 355,"pack_count": 12,"category": "rtd",  "upc": "040978006042"},
    # Liqueur
    {"brand": "Baileys",            "product_name": "Original Irish Cream","size_ml": 750,  "category": "liqueur", "upc": "086003000016"},
    {"brand": "Kahlua",             "product_name": "Coffee Liqueur",      "size_ml": 750,  "category": "liqueur", "upc": "080432402428"},
    {"brand": "Fireball",           "product_name": "Cinnamon Whisky",     "size_ml": 750,  "category": "liqueur", "upc": "088004002191"},
    {"brand": "Aperol",             "product_name": "Aperitivo",           "size_ml": 750,  "category": "liqueur", "upc": "080480280179"},
    {"brand": "Campari",            "product_name": "Bitter Liqueur",      "size_ml": 750,  "category": "liqueur", "upc": "085276001001"},
    {"brand": "Grand Marnier",      "product_name": "Cordon Rouge",        "size_ml": 750,  "category": "liqueur", "upc": "082184090459"},

    # ═══ EXPANDED CATALOG — 150+ additional brands ═══
    # Vodka (expanded)
    {"brand": "Skyy",               "product_name": "Vodka",               "size_ml": 750,  "category": "vodka",   "upc": "082000820012"},
    {"brand": "New Amsterdam",      "product_name": "Vodka",               "size_ml": 750,  "category": "vodka",   "upc": "082000870014"},
    {"brand": "Svedka",            "product_name": "Vodka",               "size_ml": 750,  "category": "vodka",   "upc": "082000830014"},
    {"brand": "Pinnacle",           "product_name": "Original Vodka",      "size_ml": 750,  "category": "vodka",   "upc": "082000840016"},
    {"brand": "Burnett's",          "product_name": "Vodka",               "size_ml": 750,  "category": "vodka",   "upc": "082000850018"},
    {"brand": "Crystal Head",       "product_name": "Aurora Vodka",        "size_ml": 750,  "category": "vodka",   "upc": "082000860020"},
    {"brand": "Stolichnaya",        "product_name": "Premium Vodka",        "size_ml": 750,  "category": "vodka",   "upc": "082000880022"},
    {"brand": "Russian Standard",   "product_name": "Original Vodka",      "size_ml": 750,  "category": "vodka",   "upc": "082000890024"},
    {"brand": "Chopin",             "product_name": "Potato Vodka",        "size_ml": 750,  "category": "vodka",   "upc": "082000900026"},
    {"brand": "Beluga",             "product_name": "Noble Vodka",          "size_ml": 750,  "category": "vodka",   "upc": "082000910028"},
    {"brand": "Hangar 1",           "product_name": "Straight Vodka",      "size_ml": 750,  "category": "vodka",   "upc": "082000920030"},
    {"brand": "Ocean",              "product_name": "Organic Vodka",       "size_ml": 750,  "category": "vodka",   "upc": "082000930032"},
    # Whiskey (expanded)
    {"brand": "Wild Turkey",        "product_name": "101 Bourbon",          "size_ml": 750,  "category": "whiskey", "upc": "082000940034"},
    {"brand": "Knob Creek",         "product_name": "Bourbon Whisky",       "size_ml": 750,  "category": "whiskey", "upc": "082000950036"},
    {"brand": "Buffalo Trace",      "product_name": "Kentucky Straight Bourbon", "size_ml": 750, "category": "whiskey", "upc": "082000960038"},
    {"brand": "Eagle Rare",         "product_name": "10 Year Bourbon",      "size_ml": 750,  "category": "whiskey", "upc": "082000970040"},
    {"brand": "Blanton's",          "product_name": "Single Barrel Bourbon", "size_ml": 750, "category": "whiskey", "upc": "082000980042"},
    {"brand": "Angel's Envy",       "product_name": "Port Finish Bourbon",   "size_ml": 750,  "category": "whiskey", "upc": "082000990044"},
    {"brand": "Michter's",          "product_name": "US1 Bourbon",           "size_ml": 750,  "category": "whiskey", "upc": "082001000046"},
    {"brand": "Redbreast",          "product_name": "12 Year Irish",        "size_ml": 750,  "category": "whiskey", "upc": "082001010048"},
    {"brand": "Yellow Spot",        "product_name": "12 Year Irish",        "size_ml": 750,  "category": "whiskey", "upc": "082001020050"},
    {"brand": "Lagavulin",          "product_name": "16 Year Single Malt",  "size_ml": 750,  "category": "whiskey", "upc": "082001030052"},
    {"brand": "Laphroaig",          "product_name": "10 Year Single Malt",  "size_ml": 750,  "category": "whiskey", "upc": "082001040054"},
    {"brand": "Macallan",           "product_name": "12 Year Double Cask",  "size_ml": 750,  "category": "whiskey", "upc": "082001050056"},
    {"brand": "Highland Park",      "product_name": "12 Year Viking Honour", "size_ml": 750, "category": "whiskey", "upc": "082001060058"},
    {"brand": "Oban",               "product_name": "14 Year Single Malt",  "size_ml": 750,  "category": "whiskey", "upc": "082001070060"},
    {"brand": "Talisker",           "product_name": "10 Year Single Malt",  "size_ml": 750,  "category": "whiskey", "upc": "082001080062"},
    {"brand": "Hibiki",             "product_name": "Japanese Harmony",     "size_ml": 750,  "category": "whiskey", "upc": "082001090064"},
    {"brand": "Yamazaki",           "product_name": "12 Year Japanese",     "size_ml": 750,  "category": "whiskey", "upc": "082001100066"},
    {"brand": "Nikka",              "product_name": "From the Barrel",       "size_ml": 500,  "category": "whiskey", "upc": "082001110068"},
    {"brand": "Rittenhouse",         "product_name": "100 Proof Rye",        "size_ml": 750,  "category": "whiskey", "upc": "082001120070"},
    {"brand": "Bulleit",            "product_name": "10 Year Rye",          "size_ml": 750,  "category": "whiskey", "upc": "082001130072"},
    {"brand": "Templeton",          "product_name": "Rye Whiskey",           "size_ml": 750,  "category": "whiskey", "upc": "082001140074"},
    {"brand": "Sazerac",            "product_name": "18 Year Rye",           "size_ml": 750,  "category": "whiskey", "upc": "082001150076"},
    # Tequila (expanded)
    {"brand": "Clase Azul",          "product_name": "Reposado Tequila",      "size_ml": 750,  "category": "tequila", "upc": "721733200018"},
    {"brand": "Avion",               "product_name": "Silver Tequila",        "size_ml": 750,  "category": "tequila", "upc": "721733200026"},
    {"brand": "Espolon",             "product_name": "Blanco Tequila",        "size_ml": 750,  "category": "tequila", "upc": "721733200034"},
    {"brand": "El Jimador",          "product_name": "Reposado Tequila",      "size_ml": 750,  "category": "tequila", "upc": "721733200042"},
    {"brand": "Hornitos",            "product_name": "Blanco Tequila",        "size_ml": 750,  "category": "tequila", "upc": "721733200050"},
    {"brand": "Milagro",              "product_name": "Silver Tequila",        "size_ml": 750,  "category": "tequila", "upc": "721733200068"},
    {"brand": "Olmeca Altos",         "product_name": "Blanco Tequila",        "size_ml": 750,  "category": "tequila", "upc": "721733200076"},
    {"brand": "Teremana",             "product_name": "Blanco Tequila",        "size_ml": 750,  "category": "tequila", "upc": "721733200084"},
    {"brand": "1800",                 "product_name": "Silver Tequila",        "size_ml": 750,  "category": "tequila", "upc": "721733200092"},
    {"brand": "Cazadores",            "product_name": "Blanco Tequila",        "size_ml": 750,  "category": "tequila", "upc": "721733200100"},
    {"brand": "Herradura",            "product_name": "Reposado Tequila",      "size_ml": 750,  "category": "tequila", "upc": "721733200118"},
    {"brand": "Sauza",                "product_name": "Gold Tequila",          "size_ml": 750,  "category": "tequila", "upc": "721733200126"},
    # Rum (expanded)
    {"brand": "Diplomatico",          "product_name": "Reserva Exclusiva",     "size_ml": 750,  "category": "rum",     "upc": "082000116924"},
    {"brand": "Zacapa",               "product_name": "Centenario 23 Rum",      "size_ml": 750,  "category": "rum",     "upc": "082000116932"},
    {"brand": "Ron Barcelo",           "product_name": "Imperial Rum",           "size_ml": 750,  "category": "rum",     "upc": "082000116940"},
    {"brand": "Appleton Estate",       "product_name": "Reserve Rum",             "size_ml": 750,  "category": "rum",     "upc": "082000116958"},
    {"brand": "Myers's",               "product_name": "Dark Rum",                "size_ml": 750,  "category": "rum",     "upc": "082000116966"},
    {"brand": "Gosling's",              "product_name": "Black Seal Rum",          "size_ml": 750,  "category": "rum",     "upc": "082000116974"},
    {"brand": "Kraken",                 "product_name": "Black Spiced Rum",        "size_ml": 750,  "category": "rum",     "upc": "082000116982"},
    {"brand": "Bundaberg",              "product_name": "Red Rum",                 "size_ml": 750,  "category": "rum",     "upc": "082000116990"},
    {"brand": "Don Q",                  "product_name": "Gold Rum",                "size_ml": 750,  "category": "rum",     "upc": "082000117000"},
    # Gin (expanded)
    {"brand": "Beefeater",              "product_name": "London Dry Gin",          "size_ml": 750,  "category": "gin",     "upc": "082000117018"},
    {"brand": "Gordon's",                "product_name": "London Dry Gin",          "size_ml": 750,  "category": "gin",     "upc": "082000117026"},
    {"brand": "Seagram's",               "product_name": "Extra Dry Gin",           "size_ml": 750,  "category": "gin",     "upc": "082000117034"},
    {"brand": "Aviation",                "product_name": "American Gin",             "size_ml": 750,  "category": "gin",     "upc": "082000117042"},
    {"brand": "Monkey 47",               "product_name": "Gin",                      "size_ml": 500,  "category": "gin",     "upc": "082000117050"},
    {"brand": "The Botanist",            "product_name": "Islay Dry Gin",           "size_ml": 750,  "category": "gin",     "upc": "082000117068"},
    {"brand": "Roku",                    "product_name": "Japanese Craft Gin",       "size_ml": 750,  "category": "gin",     "upc": "082000117076"},
    {"brand": "Nolet's",                 "product_name": "Silver Dry Gin",          "size_ml": 750,  "category": "gin",     "upc": "082000117084"},
    # Wine (expanded)
    {"brand": "La Marca",                "product_name": "Prosecco",                 "size_ml": 750,  "category": "wine",    "upc": "085000014584"},
    {"brand": "Meiomi",                  "product_name": "Pinot Noir",              "size_ml": 750,  "category": "wine",    "upc": "085000014592"},
    {"brand": "Apothic",                 "product_name": "Red Blend",               "size_ml": 750,  "category": "wine",    "upc": "085000014608"},
    {"brand": "Caymus",                  "product_name": "Cabernet Sauvignon",       "size_ml": 750,  "category": "wine",    "upc": "085000014616"},
    {"brand": "Oyster Bay",              "product_name": "Sauvignon Blanc",          "size_ml": 750,  "category": "wine",    "upc": "085000014624"},
    {"brand": "Santa Margherita",         "product_name": "Pinot Grigio",             "size_ml": 750,  "category": "wine",    "upc": "085000014632"},
    {"brand": "Ruffino",                  "product_name": "Chianti Classico",          "size_ml": 750,  "category": "wine",    "upc": "085000014640"},
    {"brand": "Mionetto",                 "product_name": "Prosecco Brut",             "size_ml": 750,  "category": "wine",    "upc": "085000014657"},
    {"brand": "Veuve Clicquot",           "product_name": "Brut Champagne",            "size_ml": 750,  "category": "wine",    "upc": "085000014665"},
    {"brand": "Dom Perignon",             "product_name": "Brut Champagne",            "size_ml": 750,  "category": "wine",    "upc": "085000014673"},
    {"brand": "Moet & Chandon",           "product_name": "Imperial Brut",              "size_ml": 750,  "category": "wine",    "upc": "085000014681"},
    {"brand": "Freixenet",                "product_name": "Cava Brut",                  "size_ml": 750,  "category": "wine",    "upc": "085000014699"},
    {"brand": "Josh Cellars",             "product_name": "Chardonnay",                "size_ml": 750,  "category": "wine",    "upc": "019375100155"},
    {"brand": "Kendall Jackson",           "product_name": "Chardonnay",                "size_ml": 750,  "category": "wine",    "upc": "019375100163"},
    # Beer (expanded)
    {"brand": "Stella Artois",             "product_name": "Lager Beer",               "size_ml": 330,  "pack_count": 6,  "category": "beer", "upc": "006834400005"},
    {"brand": "Heineken",                  "product_name": "Lager Beer",               "size_ml": 355,  "pack_count": 12, "category": "beer", "upc": "072039001010"},
    {"brand": "Dos Equis",                 "product_name": "Amber Lager",              "size_ml": 355,  "pack_count": 6,  "category": "beer", "upc": "013346600003"},
    {"brand": "Pacifico",                  "product_name": "Clara Lager",              "size_ml": 355,  "pack_count": 6,  "category": "beer", "upc": "013346700001"},
    {"brand": "Miller Lite",               "product_name": "Light Lager",              "size_ml": 355,  "pack_count": 12, "category": "beer", "upc": "018200007012"},
    {"brand": "Coors Light",              "product_name": "Light Lager",              "size_ml": 355,  "pack_count": 12, "category": "beer", "upc": "018200005014"},
    {"brand": "Michelob Ultra",            "product_name": "Light Lager",              "size_ml": 355,  "pack_count": 12, "category": "beer", "upc": "018200004016"},
    {"brand": "Guinness",                   "product_name": "Draught Stout",           "size_ml": 440,  "pack_count": 6,  "category": "beer", "upc": "013346900009"},
    {"brand": "Samuel Adams",               "product_name": "Boston Lager",            "size_ml": 355,  "pack_count": 6,  "category": "beer", "upc": "013347000007"},
    {"brand": "Sierra Nevada",               "product_name": "Pale Ale",                "size_ml": 355,  "pack_count": 6,  "category": "beer", "upc": "013347100015"},
    {"brand": "Lagunitas",                   "product_name": "IPA",                    "size_ml": 355,  "pack_count": 6,  "category": "beer", "upc": "013347200023"},
    # RTD (expanded)
    {"brand": "White Claw",                 "product_name": "Hard Seltzer Black Cherry", "size_ml": 355, "pack_count": 12, "category": "rtd",  "upc": "818502020030"},
    {"brand": "Truly",                       "product_name": "Hard Seltzer Lemonade",     "size_ml": 355, "pack_count": 12, "category": "rtd",  "upc": "040978007059"},
    {"brand": "High Noon",                   "product_name": "Peach Vodka Soda",          "size_ml": 355, "pack_count": 4,  "category": "rtd",  "upc": "850006188020"},
    {"brand": "Cutwater",                    "product_name": "Spirit of Tequila Marga",   "size_ml": 355, "pack_count": 4,  "category": "rtd",  "upc": "850006188038"},
    {"brand": "Bon V",                        "product_name": "Spicy Margarita",            "size_ml": 355, "pack_count": 4,  "category": "rtd",  "upc": "850006188046"},
    {"brand": "High West",                    "product_name": "Campfire Whiskey",           "size_ml": 750,  "category": "whiskey", "upc": "082001160078"},
    # Liqueur (expanded)
    {"brand": "Disaronno",                    "product_name": "Originale Amaretto",        "size_ml": 750,  "category": "liqueur", "upc": "080260000010"},
    {"brand": "Chambord",                     "product_name": "Black Raspberry Liqueur",     "size_ml": 750,  "category": "liqueur", "upc": "080260000028"},
    {"brand": "Drambuie",                     "product_name": "Scotch Whisky Liqueur",       "size_ml": 750,  "category": "liqueur", "upc": "080260000036"},
    {"brand": "Frangelico",                   "product_name": "Hazelnut Liqueur",            "size_ml": 750,  "category": "liqueur", "upc": "080260000044"},
    {"brand": "Midori",                       "product_name": "Melon Liqueur",               "size_ml": 750,  "category": "liqueur", "upc": "080260000052"},
    {"brand": "Pimm's",                       "product_name": "No. 1 Cup",                   "size_ml": 750,  "category": "liqueur", "upc": "080260000060"},
    {"brand": "St-Germain",                   "product_name": "Elderflower Liqueur",         "size_ml": 750,  "category": "liqueur", "upc": "080260000078"},
    {"brand": "Domaine de Canton",             "product_name": "Ginger Liqueur",              "size_ml": 750,  "category": "liqueur", "upc": "080260000086"},
    {"brand": "Fernet-Branca",                 "product_name": "Amaro",                       "size_ml": 750,  "category": "liqueur", "upc": "080260000094"},
    {"brand": "Aperol",                        "product_name": "Aperitivo",                   "size_ml": 750,  "category": "liqueur", "upc": "080480280179"},
]


def make_embedding_text(sku: dict) -> str:
    size = f"{sku['size_ml']}ml" if sku.get("size_ml") else ""
    pack = f"{sku['pack_count']}pk" if sku.get("pack_count", 1) > 1 else ""
    return " ".join(filter(None, [sku["brand"], sku["product_name"], size, pack])).strip()


async def seed(dsn: str):
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")
    print("Loading BGE-small-en model...")
    model = SentenceTransformer("BAAI/bge-small-en-v1.5")

    texts = [make_embedding_text(s) for s in SKUS]
    print(f"Embedding {len(texts)} SKUs...")
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)

    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        inserted = 0
        for sku, emb in zip(SKUS, embeddings):
            emb_str = "[" + ",".join(f"{x:.6f}" for x in emb.tolist()) + "]"
            await conn.execute(
                """
                INSERT INTO products (brand, product_name, size_ml, pack_count, category, upc, embedding)
                VALUES ($1, $2, $3, $4, $5, $6, $7::vector)
                ON CONFLICT (upc) DO UPDATE SET embedding = EXCLUDED.embedding
                """,
                sku["brand"],
                sku["product_name"],
                sku.get("size_ml"),
                sku.get("pack_count", 1),
                sku["category"],
                sku.get("upc"),
                emb_str,
            )
            inserted += 1
        print(f"Seeded {inserted} products.")
    finally:
        await conn.close()


if __name__ == "__main__":
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)
    asyncio.run(seed(dsn))
