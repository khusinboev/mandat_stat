from PIL import Image, ImageDraw, ImageFont
import os

def split_text_by_words(text, max_len=45):
    words = text.split()
    result = ''
    line = ''

    for word in words:
        # Agar yangi so‘zni qo‘shganda line uzunligi max_len'dan oshmasa
        if len(line) + len(word) + 1 <= max_len:
            if line:
                line += ' ' + word
            else:
                line = word
        else:
            # Yangi qatorga o'tamiz
            result += line + '\n'
            line = word

    # Oxirgi qatorni ham qo‘shamiz
    if line:
        result += line

    return result

def create_university_card(univer, faculty, lang, edu, grand, kont, olmp, name):
    univer = split_text_by_words(univer)
    faculty = split_text_by_words(faculty)
    template_path = "edu.png"
    output_path = f"{name}.png"
    try:
        # Rasmni ochish
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template image '{template_path}' not found!")

        image = Image.open(template_path)
        draw = ImageDraw.Draw(image)

        # Shriftlarni yuklash (o'zingizga mos fayllarni ko'rsating)
        try:
            title_font = ImageFont.truetype("../src/handlers/users/Quicksand-Bold.otf", 100)
            main_font = ImageFont.truetype("../src/handlers/users/Quicksand-Bold.otf", 90)
            small_font = ImageFont.truetype("../src/handlers/users/Quicksand-Bold.otf", 50)
        except:
            # Agar shriftlar topilmasa, standart shriftlardan foydalanish
            title_font = ImageFont.load_default()
            main_font = ImageFont.load_default()
            small_font = ImageFont.load_default()

        # 1. Universitet nomi (binoning ustidagi ochiq maydonga)
        draw.text((500, 200), univer, font=title_font, fill="black")

        # 2. Ta'lim yo'nalishi ("AJ" yozuvi o'rniga)
        # "AJ" ni o'chirish uchun uning joyiga oq rangda to'rtburchak chizamiz
        draw.text((300, 800), faculty, font=main_font, fill="black")

        # 3. Ta'lim tili (oldingi yozuv ostida)
        draw.text((550, 1600), lang, font=main_font, fill="white")

        # 4. Ta'lim shakli
        draw.text((1500, 1600), edu, font=main_font, fill="white")

        # 5. Mandat yili
        draw.text((2450, 1600), "2025", font=main_font, fill="white")

        # 6. Grantlar
        draw.text((650, 2120), grand, font=main_font, fill="black")

        # 7. Kontraktlar
        draw.text((1420, 2120), kont, font=main_font, fill="black")

        # 8. Olimpiada g'oliblari soni
        draw.text((2550, 2170), str(olmp), font=main_font, fill="black")

        # Natijani saqlash
        image.save(output_path)
        print(f"Karta muvaffaqiyatli yaratildi: {output_path}")

    except Exception as e:
        print(f"Xatolik yuz berdi: {str(e)}")


# Namuna sifatida foydalanish
if __name__ == "__main__":
    create_university_card(
        univer="O'zbekiston davlat konservatoriyasi O'zbekiston davlat konservatoriyasi ",
        faculty="60211511 - Cholg'u ijrochiligi",
        lang="O'zbek",
        edu="Kunduzgi",
        grand="77.1 ball",
        kont="56.7 ball",
        olmp="0"
    )