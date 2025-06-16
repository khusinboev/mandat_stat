'''
OTM bo‘yicha o‘tish ballari 2024

https://mandat.uzbmb.uz/Mandat2024/GetRegions?lang=uz
https://mandat.uzbmb.uz/BallVuz2024/GetUniversities?RegionID=4
https://mandat.uzbmb.uz/BallVuz2024/GetTypes?UniversityID=344
https://mandat.uzbmb.uz/BallVuz2024/GetLangs?UniversityID=344
https://mandat.uzbmb.uz/BallVuz2024/GetAll?RegionID=4&UniversityID=344&EdTypeID=1&EdLangID=1


Kengaytirilgan qidiruv

https://mandat.uzbmb.uz/Mandat2024/GetUniversitiesByRegion?lang=uz&regionid=1
https://mandat.uzbmb.uz/Mandat2024/GetFacultiesByUniversity?lang=uz&universityid=352
https://mandat.uzbmb.uz/Mandat2024/GetEdlangsByMvdir?mvdir=6054020094&universityid=352
https://mandat.uzbmb.uz/Mandat2024/GetEdTypesByMvdirEdLang?lang=uz&universityid=352&mvdir=6054020094&educlangid=3
https://mandat.uzbmb.uz/Mandat2024/GetAll?lang=uz&universityid=352&mvdir=6054020094&educlangid=3


ID bo'yicha

# # Foydalaniladigan form ma'lumotlari
# data = {
#     "pageNumber":"3",
#     "pageSize":"100",
#     "region":"3",
#     "univer":"309",
#     "faculty":"60410100",
#     "edlang":"1",
#     "edtype":"1",
#     "lang":"uz"
# }
#
# # POST so'rov yuborish
# response = requests.post("https://mandat.uzbmb.uz/Mandat2024/MainSearch", data=data)
#
# # HTML sahifani BeautifulSoup bilan parse qilish
# soup = BeautifulSoup(response.text, "html.parser")
#
# # Natijalarni topish
# rows = soup.find_all("tr", class_="table-secondary")
#
# # Natijalarni chiqarish
# for row in rows:
#     columns = row.find_all("td")
#     text_data = [col.text.strip() for col in columns]
#     print(text_data)
'''


