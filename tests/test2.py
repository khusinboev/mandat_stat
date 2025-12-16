import requests
import sqlite3

conn = sqlite3.connect("../src/db/mandat.db")
cursor = conn.cursor()

# Chet kalitlarni yoqamiz
cursor.execute("PRAGMA foreign_keys = ON")

# REGIONS jadvali
cursor.execute('''
CREATE TABLE IF NOT EXISTS regions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    region_id INTEGER UNIQUE,
    region_name TEXT UNIQUE
)
''')

# UNIVERSITIES jadvali
cursor.execute('''
CREATE TABLE IF NOT EXISTS universities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    region_id INTEGER,
    un_disabled TEXT,
    un_group TEXT,
    un_selected TEXT,
    un_text TEXT,
    un_id TEXT UNIQUE,
    UNIQUE(region_id, un_text, un_id)
)
''')

# GETTYPES jadvali
cursor.execute('''
CREATE TABLE IF NOT EXISTS gettypes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    region_id INTEGER,
    un_id INTEGER,
    ty_disabled TEXT,
    ty_group TEXT,
    ty_selected TEXT,
    ty_text TEXT,
    ty_id TEXT,
    UNIQUE(region_id, un_id, ty_text, ty_id)
)
''')

# GETLANGS jadvali
cursor.execute('''
CREATE TABLE IF NOT EXISTS getlangs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    region_id INTEGER,
    un_id INTEGER,
    ty_id INTEGER,
    lan_disabled TEXT,
    lan_group TEXT,
    lan_selected TEXT,
    lan_text TEXT,
    lan_id TEXT, -- <<< shu yerda UNIQUE qo'shildi
    UNIQUE(region_id, un_id, ty_id, lan_text, lan_id)
)
''')

# MANDAT jadvali
cursor.execute('''
CREATE TABLE IF NOT EXISTS mandat (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    region_id INTEGER,
    un_id TEXT,
    ty_id TEXT,
    lan_id TEXT,
    mvdir INTEGER,
    nomi TEXT,
    gr_k INTEGER,
    con_k INTEGER,
    gr_b REAL,
    con_b REAL,
    olimp INTEGER,
    UNIQUE(region_id, un_id, ty_id, lan_id, mvdir, nomi)
)
''')

cursor.execute("""
CREATE TABLE IF NOT EXISTS photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    un_id TEXT NOT NULL,
    ty_id TEXT NOT NULL,
    lan_id TEXT NOT NULL,
    mvdir TEXT NOT NULL,
    file_id TEXT NOT NULL,
    UNIQUE(un_id, ty_id, lan_id, mvdir, file_id)
);
""")
conn.commit()


url1 = 'https://mandat.uzbmb.uz/Mandat2025/GetRegions?lang=uz'
response = requests.get(url1)

regions = response.json()
shifr = []
for region in regions:
    region_name = region['region_name']
    region_id = region['region_id'] # OR IGNORE
    cursor.execute('''
        INSERT INTO regions (region_id, region_name)
        VALUES (?, ?)
        ''', (region_id, region_name))
    conn.commit()

    url2 = f"https://mandat.uzbmb.uz/BallVuz2025/GetUniversities?RegionID={region_id}"
    response = requests.get(url2)
    univers = response.json()
    for univer in univers:
        un_disabled = univer['disabled']
        un_group = univer['group']
        un_selected = univer["selected"]
        un_text = univer["text"]
        un_id = univer["value"]
        cursor.execute('''
            INSERT INTO universities (region_id, un_disabled, un_group, un_selected, un_text, un_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (region_id, un_disabled, un_group, un_selected, un_text, un_id))
        conn.commit()

        url3 = f"https://mandat.uzbmb.uz/BallVuz2025/GetTypes?UniversityID={un_id}"
        response = requests.get(url3)
        get_types = response.json()
        for get_type in get_types:
            ty_disabled = get_type['disabled']
            ty_group = get_type['group']
            ty_selected = get_type['selected']
            ty_text = get_type['text']
            ty_id = get_type['value']
            cursor.execute('''
                INSERT INTO gettypes (region_id, un_id, ty_disabled, ty_group, ty_selected, ty_text, ty_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (region_id, un_id, ty_disabled, ty_group, ty_selected, ty_text, ty_id))
            conn.commit()

            url4 = f"https://mandat.uzbmb.uz/BallVuz2025/GetLangs?UniversityID={un_id}"
            response = requests.get(url4)
            get_langs = response.json()
            for get_lang in get_langs:
                lan_disabled = get_lang['disabled']
                lan_group = get_lang['group']
                lan_selected = get_lang['selected']
                lan_text = get_lang['text']
                lan_id = get_lang['value']

                cursor.execute('''
                    INSERT INTO getlangs (region_id, un_id, ty_id, lan_disabled, lan_group, lan_selected, lan_text, lan_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (region_id, un_id, ty_id, lan_disabled, lan_group, lan_selected, lan_text, lan_id))

                # so'nggi API chaqiruv:
                url5 = f"https://mandat.uzbmb.uz/BallVuz2025/GetAll?RegionID={region_id}&UniversityID={un_id}&EdTypeID={ty_id}&EdLangID={lan_id}"
                response = requests.get(url5)
                get_datas = response.json()
                for get_data in get_datas:
                    mvdir = get_data["mvdir"]
                    nomi = get_data["nomi"]
                    gr_k = get_data['gr_k']
                    con_k = get_data['con_k']
                    gr_b = get_data["gr_b"]
                    con_b = get_data["con_b"]
                    olimp = get_data["olimp"]

                    cursor.execute('''
                        INSERT INTO mandat (region_id, un_id, ty_id, lan_id, mvdir, nomi, gr_k, con_k, gr_b, con_b, olimp)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (region_id, un_id, ty_id, lan_id, mvdir, nomi, gr_k, con_k, gr_b, con_b, olimp))

                    conn.commit()
conn.close()
print("bo'ldi")
