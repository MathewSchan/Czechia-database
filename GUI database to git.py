import psycopg2
import csv
import matplotlib.pyplot as plt


# ---------------------------------------------------------
# 1) Připojení k databázi
# ---------------------------------------------------------
def connect():
    """Vytvoří a vrátí připojení do PostgreSQL databáze."""
    try:
        conn = psycopg2.connect(
            host="192.168.135.10",
            database="obce",
            user="student",
            password="bluemonkey3"  # Doplň heslo, pokud ho vaše databáze vyžaduje
        )
        return conn
    except Exception as e:
        print(f"❌ Chyba při připojování k databázi: {e}")
        return None


# ---------------------------------------------------------
# 2) Výpis okresů
# ---------------------------------------------------------
def vypis_okresu(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id_okres, nazev FROM okresy ORDER BY id_okres;")
        okresy = cur.fetchall()
        print("\n--- Seznam okresů ---")
        for id_okres, nazev in okresy:
            print(f"{id_okres} {nazev}")


# ---------------------------------------------------------
# 3) Zobrazení obcí v okrese (SQL JOIN)
# ---------------------------------------------------------
def obce_v_okrese(conn):
    id_okr = input("Zadej kód okresu (např. CZ0100): ").strip()

    with conn.cursor() as cur:
        # Použití JOIN ke zjištění názvu okresu i obcí zároveň
        dotaz = """
            SELECT o.nazev AS nazev_okresu, p.nazev, p.pocet_obyvatel, p.prumerny_vek
            FROM obce_pob p
            JOIN okresy o ON p.id_okres = o.id_okres
            WHERE o.id_okres = %s
            ORDER BY p.pocet_obyvatel DESC;
        """
        cur.execute(dotaz, (id_okr,))
        obce = cur.fetchall()

        if not obce:
            print("❌ Okres nenalezen nebo v něm nejsou žádné obce.")
            return

        nazev_okresu = obce[0][0]
        celkem_obci = len(obce)
        celkem_obyv = sum(obec[2] for obec in obce if obec[2])

        print(f"\n{nazev_okresu} — počet obcí: {celkem_obci}")
        print(f"{nazev_okresu} — obyvatel: {celkem_obyv:,}".replace(',', ' '))
        print("-" * 50)
        print(f"{'Název obce':<30} | {'Obyvatel':<10} | {'Průměrný věk'}")
        print("-" * 50)

        for radek in obce:
            print(f"{radek[1]:<30} | {radek[2]:<10} | {radek[3]}")


# ---------------------------------------------------------
# 4) Vyhledání obce podle názvu (SQL LIKE)
# ---------------------------------------------------------
def hledani_obce(conn):
    hledano = input("Zadej část názvu obce: ").strip()

    with conn.cursor() as cur:
        # ILIKE zajistí, že vyhledávání ignoruje velikost písmen (case-insensitive)
        cur.execute("SELECT nazev FROM obce_pob WHERE nazev ILIKE %s ORDER BY nazev;", (f"%{hledano}%",))
        vysledky = cur.fetchall()

        print("\n--- Nalezené obce ---")
        if vysledky:
            for v in vysledky:
                print(v[0])
        else:
            print("Žádná obec nebyla nalezena.")


# ---------------------------------------------------------
# 5) Statistika okresu (Agregační funkce + GROUP BY)
# ---------------------------------------------------------
def statistika_okresu(conn):
    id_okr = input("Zadej kód okresu pro statistiku: ").strip()

    with conn.cursor() as cur:
        dotaz = """
            SELECT o.nazev, 
                   SUM(p.pocet_obyvatel), 
                   AVG(p.prumerny_vek), 
                   SUM(p.pocet_muzi), 
                   SUM(p.pocet_zeny)
            FROM obce_pob p
            JOIN okresy o ON p.id_okres = o.id_okres
            WHERE o.id_okres = %s
            GROUP BY o.nazev;
        """
        cur.execute(dotaz, (id_okr,))
        stat = cur.fetchone()

        if stat:
            nazev, celkem, prum_vek, muzi, zeny = stat
            print(f"\n--- Statistika pro okres: {nazev} ---")
            print(f"Celkový počet obyvatel: {celkem:,}".replace(',', ' '))
            print(f"Průměrný věk:           {prum_vek:.2f} let")
            print(f"Počet mužů:             {muzi:,}".replace(',', ' '))
            print(f"Počet žen:              {zeny:,}".replace(',', ' '))
            if zeny and zeny > 0:
                print(f"Poměr mužů na 1 ženu:   {muzi / zeny:.2f}")
        else:
            print("❌ Okres nenalezen.")


# ---------------------------------------------------------
# ⭐ Bonus 1: Export do CSV
# ---------------------------------------------------------
def export_do_csv(conn):
    id_okr = input("Zadej kód okresu pro export: ").strip()

    with conn.cursor() as cur:
        dotaz = """
            SELECT o.nazev, p.nazev, p.pocet_obyvatel, p.pocet_muzi, p.pocet_zeny, p.prumerny_vek
            FROM obce_pob p
            JOIN okresy o ON p.id_okres = o.id_okres
            WHERE o.id_okres = %s
            ORDER BY p.nazev;
        """
        cur.execute(dotaz, (id_okr,))
        data = cur.fetchall()

        if not data:
            print("❌ Žádná data k exportu.")
            return

        nazev_okresu_soubor = data[0][0].lower().replace(" ", "_") + ".csv"

        with open(nazev_okresu_soubor, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file, delimiter=';')
            writer.writerow(["Okres", "Obec", "Pocet_obyvatel", "Muzi", "Zeny", "Prumerny_vek"])
            writer.writerows(data)

        print(f"✅ Data byla úspěšně exportována do souboru: {nazev_okresu_soubor}")


# ---------------------------------------------------------
# ⭐ Bonus 2: Top 10 největších obcí
# ---------------------------------------------------------
def top_10_obci(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT nazev, pocet_obyvatel FROM obce_pob ORDER BY pocet_obyvatel DESC LIMIT 10;")
        obce = cur.fetchall()

        print("\n--- TOP 10 největších obcí v ČR ---")
        for i, obec in enumerate(obce, 1):
            print(f"{i:2}. {obec[0]:<25} - {obec[1]:>8,} obyvatel".replace(',', ' '))


# ---------------------------------------------------------
# ⭐ Bonus 3: Graf (matplotlib)
# ---------------------------------------------------------
def zobrazit_graf(conn):
    id_okr = input("Zadej kód okresu pro graf (muži vs. ženy): ").strip()

    with conn.cursor() as cur:
        dotaz = """
            SELECT SUM(pocet_muzi), SUM(pocet_zeny), o.nazev
            FROM obce_pob p
            JOIN okresy o ON p.id_okres = o.id_okres
            WHERE o.id_okres = %s
            GROUP BY o.nazev;
        """
        cur.execute(dotaz, (id_okr,))
        vysledek = cur.fetchone()

        if not vysledek or not vysledek[0]:
            print("❌ Okres nenalezen nebo chybí data pro graf.")
            return

        muzi, zeny, nazev_okresu = vysledek

        # Vykreslení grafu
        labels = ['Muži', 'Ženy']
        values = [muzi, zeny]
        colors = ['#3498db', '#e74c3c']

        plt.figure(figsize=(6, 4))
        plt.bar(labels, values, color=colors)
        plt.title(f'Porovnání počtu mužů a žen - {nazev_okresu}')
        plt.ylabel('Počet obyvatel')

        # Zobrazení přesných hodnot nad sloupci
        for i, v in enumerate(values):
            plt.text(i, v + (max(values) * 0.01), str(v), ha='center', fontweight='bold')

        plt.tight_layout()
        plt.show()


# ---------------------------------------------------------
# HLAVNÍ MENU APLIKACE
# ---------------------------------------------------------
def menu():
    print("\n" + "=" * 25)
    print("DEMOGRAFIE ČR")
    print("=" * 25)
    print("1 - Seznam okresů")
    print("2 - Obce v okrese")
    print("3 - Hledat obec")
    print("4 - Statistiky okresu")
    print("5 - ⭐ Export do CSV (Bonus)")
    print("6 - ⭐ Top 10 obcí (Bonus)")
    print("7 - ⭐ Zobrazit graf (Bonus)")
    print("0 - Konec")

    volba = input("Vyber: ").strip()
    return volba


def main():
    conn = connect()
    if not conn:
        return  # Pokud se nepřipojíme, program skončí

    while True:
        volba = menu()

        if volba == '1':
            vypis_okresu(conn)
        elif volba == '2':
            obce_v_okrese(conn)
        elif volba == '3':
            hledani_obce(conn)
        elif volba == '4':
            statistika_okresu(conn)
        elif volba == '5':
            export_do_csv(conn)
        elif volba == '6':
            top_10_obci(conn)
        elif volba == '7':
            zobrazit_graf(conn)
        elif volba == '0':
            print("Ukončuji aplikaci. Měj se!")
            break
        else:
            print("❌ Neplatná volba, zkus to znovu.")

    # Úklid a uzavření spojení po konci while smyčky
    conn.close()


if __name__ == "__main__":
    main()