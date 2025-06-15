import requests
from bs4 import BeautifulSoup

data = {
    "pageNumber":"3",
    "pageSize":"100",
    "region":"3",
    "univer":"309",
    "faculty":"60410100",
    "edlang":"1",
    "edtype":"1",
    "lang":"uz"
}

# POST so'rov yuborish
response = requests.post("https://mandat.uzbmb.uz/Mandat2024/MainSearch", data=data)

# HTML sahifani BeautifulSoup bilan parse qilish
soup = BeautifulSoup(response.text, "html.parser")

# Natijalarni topish
rows = soup.find_all("tr", class_="table-secondary")

# Natijalarni chiqarish
for row in rows:
    columns = row.find_all("td")
    text_data = [col.text.strip() for col in columns]
    print(text_data)