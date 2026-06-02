import psycopg2
import csv
import getpass
import matplotlib.pyplot as plt

# Globální konfigurace pro databázi
DB_CONFIG = {}

# Pomocný SQL řetězec pro odstranění české diakritiky přímo v PostgreSQL
SQL_UNACCENT = "lower(translate({column}, 'áčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ', 'acdeeinrstuuizACDEEINRSTUUIZ'))"


# =====================================================================
# 1. DATABÁZOVÁ VRSTVA (DB)
# =====================================================================

def db_test_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.close()
        return True
    except Exception:
        return False


def db_fetch_all(query, params=None):
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()
    finally:
        conn.close()


def db_fetch_one(query, params=None):
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchone()
    finally:
        conn.close()


# =====================================================================
# 2. APLIKAČNÍ VRSTVA (APP)
# =====================================================================

def app_resolve_okres_id(vstup):
    vstup = vstup.strip()
    if not vstup:
        return None

    vstup_upper = vstup.upper()

    query = f"""
        SELECT id_okres FROM okresy 
        WHERE id_okres ILIKE %s 
           OR {SQL_UNACCENT.format(column='nazev')} LIKE {SQL_UNACCENT.format(column='%s')}
        LIMIT 1;
    """
    vysledek = db_fetch_one(query, (f"%{vstup_upper}%", f"%{vstup}%"))
    return vysledek[0] if vysledek else None


def app_get_okresy_list():
    query = "SELECT id_okres, nazev FROM okresy ORDER BY id_okres;"
    raw_data = db_fetch_all(query)
    return [{"id": r[0], "nazev": r[1]} for r in raw_data]


def app_get_obce_v_okrese(vstup_uzivatele):
    id_okr = app_resolve_okres_id(vstup_uzivatele)
    if not id_okr:
        return None

    query = """
        SELECT o.nazev, p.nazev, p.pocet_obyvatel, p.prumerny_vek
        FROM obce_pob p JOIN okresy o ON p.id_okres = o.id_okres
        WHERE o.id_okres = %s ORDER BY p.pocet_obyvatel DESC;
    """
    raw_data = db_fetch_all(query, (id_okr,))
    if not raw_data:
        return None

    return {
        "okres_nazev": raw_data[0][0],
        "obce": [{"nazev": r[1], "obyvatele": r[2], "vek": r[3]} for r in raw_data]
    }


def app_hledat_obec(nazev_cast):
    # SQL dotaz upraven o JOIN na okresy a CASE podmínku porovnávající názvy
    query = f"""
        SELECT p.nazev, 
               CASE WHEN p.nazev = o.nazev THEN 1 ELSE 0 END as shoda
        FROM obce_pob p
        JOIN okresy o ON p.id_okres = o.id_okres
        WHERE {SQL_UNACCENT.format(column='p.nazev')} LIKE {SQL_UNACCENT.format(column='%s')}
        ORDER BY p.nazev;
    """
    raw_data = db_fetch_all(query, (f"%{nazev_cast}%",))
    return [{"nazev": r[0], "je_stejny_jako_okres": bool(r[1])} for r in raw_data]


def app_get_statistika(vstup_uzivatele):
    id_okr = app_resolve_okres_id(vstup_uzivatele)
    if not id_okr:
        return None

    query = """
        SELECT o.nazev, SUM(p.pocet_obyvatel), AVG(p.prumerny_vek), SUM(p.pocet_muzi), SUM(p.pocet_zeny)
        FROM obce_pob p JOIN okresy o ON p.id_okres = o.id_okres
        WHERE o.id_okres = %s GROUP BY o.nazev;
    """
    raw = db_fetch_one(query, (id_okr,))
    if not raw:
        return None
    return {
        "nazev": raw[0], "celkem": int(raw[1]), "vek": round(float(raw[2]), 2),
        "muzi": int(raw[3]), "zeny": int(raw[4])
    }


def app_get_top_10():
    query = "SELECT nazev, pocet_obyvatel FROM obce_pob ORDER BY pocet_obyvatel DESC LIMIT 10;"
    raw = db_fetch_all(query)
    return [{"nazev": r[0], "obyvatele": r[1]} for r in raw]


def app_export_csv_file(vstup_uzivatele):
    id_okr = app_resolve_okres_id(vstup_uzivatele)
    if not id_okr:
        return None

    query = """
        SELECT o.nazev, p.nazev, p.pocet_obyvatel, p.pocet_muzi, p.pocet_zeny, p.prumerny_vek
        FROM obce_pob p JOIN okresy o ON p.id_okres = o.id_okres WHERE o.id_okres = %s;
    """
    raw_data = db_fetch_all(query, (id_okr,))
    if not raw_data:
        return None

    filename = raw_data[0][0].lower().replace(" ", "_") + ".csv"
    with open(filename, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(["Okres", "Obec", "Obyvatele", "Muzi", "Zeny", "Vek"])
        writer.writerows(raw_data)
    return filename


# =====================================================================
# 3. API VRSTVA
# =====================================================================

def api_get_okresy():
    return {"status": 200, "data": app_get_okresy_list()}


def api_get_obce(vstup_okres):
    data = app_get_obce_v_okrese(vstup_okres)
    return {"status": 200, "data": data} if data else {"status": 404,
                                                       "error": "Okres nebyl podle vašeho zadání nalezen."}


def api_hledat_obec(nazev):
    return {"status": 200, "data": app_hledat_obec(nazev)}


def api_get_statistika(vstup_okres):
    data = app_get_statistika(vstup_okres)
    return {"status": 200, "data": data} if data else {"status": 404,
                                                       "error": "Okres nebyl podle vašeho zadání nalezen."}


def api_get_top10():
    return {"status": 200, "data": app_get_top_10()}


def api_export_csv(vstup_okres):
    filename = app_export_csv_file(vstup_okres)
    return {"status": 200, "filename": filename} if filename else {"status": 404,
                                                                   "error": "Export selhal, okres nenalezen."}


# =====================================================================
# 4. UŽIVATELSKÉ ROZHRANÍ (UI)
# =====================================================================

def ui_vypis_okresu():
    response = api_get_okresy()
    print("\n--- Seznam okresů ---")
    for okr in response["data"]:
        print(f"{okr['id']} {okr['nazev']}")


def ui_obce_v_okrese():
    vstup = input("Zadej okres (název, kód nebo číslo): ")
    response = api_get_obce(vstup)

    if response["status"] != 200:
        print(f"❌ {response['error']}")
        return

    data = response["data"]
    celkem_obyv = sum(o["obyvatele"] for o in data["obce"])

    print(f"\n{data['okres_nazev']} — počet obcí: {len(data['obce'])}")
    print(f"{data['okres_nazev']} — obyvatel: {celkem_obyv:,}".replace(',', ' '))
    print("-" * 55)
    print(f"{'Název obce':<30} | {'Obyvatel':<10} | {'Průměrný věk'}")
    print("-" * 55)
    for o in data["obce"]:
        print(f"{o['nazev']:<30} | {o['obyvatele']:<10} | {o['vek']}")


def ui_hledat_obec():
    text = input("Zadej název obce (stačí část, bez diakritiky): ")
    response = api_hledat_obec(text)
    print("\n--- Nalezené obce (* = obec se jmenuje stejně jako její okres) ---")
    if response["data"]:
        for obec in response["data"]:
            # Pokud se název obce shoduje s názvem okresu, přidáme hvězdičku
            oznaceni = " *" if obec["je_stejny_jako_okres"] else ""
            print(f"{obec['nazev']}{oznaceni}")
    else:
        print("Žádná obec nebyla nalezena.")


def ui_statistika_okresu():
    vstup = input("Zadej okres pro statistiku (kód nebo název): ")
    response = api_get_statistika(vstup)

    if response["status"] != 200:
        print(f"❌ {response['error']}")
        return

    d = response["data"]
    pomer = d["muzi"] / d["zeny"] if d["zeny"] > 0 else 0
    print(f"\n--- Statistika pro okres: {d['nazev']} ---")
    print(f"Celkový počet obyvatel: {d['celkem']:,}".replace(',', ' '))
    print(f"Průměrný věk:           {d['vek']} let")
    print(f"Počet mužů / žen:       {d['muzi']:,} / {d['zeny']:,}".replace(',', ' '))
    print(f"Poměr mužů na 1 ženu:   {pomer:.2f}")


def ui_export_csv():
    vstup = input("Zadej okres pro export do CSV: ")
    response = api_export_csv(vstup)
    if response["status"] == 200:
        print(f"✅ Soubor '{response['filename']}' byl úspěšně vygenerován.")
    else:
        print(f"❌ {response['error']}")


def ui_top_10():
    response = api_get_top10()
    print("\n--- TOP 10 největších obcí v ČR ---")
    for i, o in enumerate(response["data"], 1):
        print(f"{i:2}. {o['nazev']:<25} - {o['obyvatele']:>8,} obyvatel".replace(',', ' '))


def ui_zobraz_graf():
    vstup = input("Zadej okres pro zobrazení grafu pohlaví: ")
    response = api_get_statistika(vstup)

    if response["status"] != 200:
        print(f"❌ {response['error']}")
        return

    d = response["data"]
    plt.figure(figsize=(5, 4))
    plt.bar(['Muži', 'Ženy'], [d['muzi'], d['zeny']], color=['#3498db', '#e74c3c'])
    plt.title(f"Poměr pohlaví - {d['nazev']}")
    plt.ylabel('Počet obyvatel')
    plt.tight_layout()
    plt.show()


def ui_menu():
    print("\n=========================\nDEMOGRAFIE ČR\n=========================")
    print("1 - Seznam okresů\n2 - Obce v okrese\n3 - Hledat obec\n4 - Statistiky okresu")
    print("5 - ⭐ Export do CSV\n6 - ⭐ Top 10 obcí\n7 - ⭐ Zobrazit graf\n0 - Konec")
    return input("Vyber: ").strip()


# =====================================================================
# VSTUPNÍ BOD PROGRAMU
# =====================================================================

def main():
    print("=== JEDNORÁZOVÉ PŘIHLÁŠENÍ K DATABÁZI ===")
    global DB_CONFIG
    DB_CONFIG['host'] = input("Zadej IP adresu serveru: ").strip()
    DB_CONFIG['user'] = input("Zadej uživatelské jméno: ").strip()

    # Poznámka: Pokud tvé IDE nepodporuje getpass, znaky se mohou zobrazovat.
    # Pro 100% skrytí spusť skript přímo přes systémový Terminál / Příkazovou řádku.
    DB_CONFIG['password'] = getpass.getpass("Zadej heslo: ").strip()
    DB_CONFIG['database'] = input("Zadej název databáze: ").strip()

    print("\n🔄 Připojování k PostgreSQL...")
    if not db_test_connection():
        print("❌ Přihlášení selhalo! Zkontroluj zadané údaje a síť.")
        return

    print("✅ Úspěšně ověřeno. Vítejte!")

    while True:
        volba = ui_menu()
        if volba == '1':
            ui_vypis_okresu()
        elif volba == '2':
            ui_obce_v_okrese()
        elif volba == '3':
            ui_hledat_obec()
        elif volba == '4':
            ui_statistika_okresu()
        elif volba == '5':
            ui_export_csv()
        elif volba == '6':
            ui_top_10()
        elif volba == '7':
            ui_zobraz_graf()
        elif volba == '0':
            print("Nashledanou!")
            break
        else:
            print("Neplatná volba, zkuste to znovu.")


if __name__ == "__main__":
    main()