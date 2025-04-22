import json
import re
import os
import sys
import signal
import sqlite3
import random
from collections import Counter
from datetime import datetime
from Levenshtein import distance
from uznlp.morphology import MorphAnalyzer

# Fayl yo'llari
DB_FILE = r"F:\AI\chatbot.db"
TEMPLATES_FILE = r"F:\AI\sentence_templates.json"

# Stop-so'zlar
STOP_WORDS = {"va", "bu", "u", "bilan", "uchun", "da", "dan", "ga", "ni", "bir", "lekin"}

# Boshlang'ich xotira
INITIAL_MEMORY = {
    "patterns": {
        "salom": ["salom", "assalomu alaykum", "slm"],
        "nima": ["nima gap", "nima yangilik", "nima qilyapsan", "nima qilayapti bot"],
        "qalesan": ["qalesan", "qandaysan", "nima hol"],
        "isming": ["isming nima"],
        "hayron": ["hayronman", "nima bu"],
        "yaxshi": ["yaxshisan", "yaxshi", "zo‘r"],
        "rahmat": ["rahmat", "tashakkur"],
        "nima qila olasan": ["nima qila olasan", "qanday yordam berasan"],
        "kod": ["kod yoz", "python o'rgat", "kod o'rgat", "dastur yoz"]
    },
    "responses": {
        "salom": "Salom! Qanday yordam bera olaman?",
        "nima": "Hozir shu yerda sen bilan suhbatlashyapman! 😊 Senda nima gap?",
        "qalesan": "Yaxshi, sen qandaysan?",
        "isming": "Men DTBOTman! 😊 Isming nima?",
        "hayron": "Hayron bo‘lishga hojat yo‘q, hammasini tuzatamiz! 😊",
        "yaxshi": "Zo‘r, yaxshi kayfiyatda bo‘l! 😎",
        "rahmat": "Arzimaydi, doim yordam beraman!",
        "nima qila olasan": "Men suhbatlashaman, xato so‘zlarni tuzataman, kod yozishni o‘rgataman va yangi so‘zlarni o‘rganaman! 😊 Masalan, 'kod yoz' yoki 'matn o'rgan: F:\\AI\\kitob.txt' deb so‘ra.",
        "kod": "Python kodini o‘rgataman yoki senga kod yozib beraman! 😊 Nima o‘rganmoqchisan? Masalan, 'print ni o‘rgat' yoki 'oddiy kalkulyator yoz' deb so‘ra."
    }
}

# Ma'lumotlar bazasi
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS words
                 (word TEXT PRIMARY KEY, type TEXT, unli TEXT, kopluk TEXT, forms TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS patterns
                 (word TEXT, pattern TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS responses
                 (pattern TEXT PRIMARY KEY, response TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS conversation_history
                 (user_input TEXT, response TEXT, timestamp DATETIME)''')
    conn.commit()
    print(f"Ma'lumotlar bazasi {DB_FILE} ishga tushirildi.")
    return conn

def load_words(conn):
    c = conn.cursor()
    c.execute("SELECT word, type, unli, kopluk, forms FROM words")
    words = [{"word": row[0], "type": row[1], "unli": row[2], "kopluk": row[3], "forms": json.loads(row[4]) if row[4] else None} for row in c.fetchall()]
    return words

def save_word(conn, word, word_type, unli, kopluk, forms=None):
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO words (word, type, unli, kopluk, forms) VALUES (?, ?, ?, ?, ?)",
              (word, word_type, unli, kopluk, json.dumps(forms) if forms else None))
    conn.commit()

def load_templates():
    try:
        with open(TEMPLATES_FILE, 'r', encoding='utf-8') as file:
            templates = json.load(file)
            return templates.get("sentence_templates", [])
    except Exception as e:
        print(f"Xato: {TEMPLATES_FILE} faylini o'qishda muammo: {e}")
        return []

# Xato so'zlarni tuzatish
analyzer = MorphAnalyzer()

def advanced_correct_word(word, conn):
    # uzNLP bilan tahlil
    analysis = analyzer.analyze(word)
    if analysis.get("root"):
        return analysis["root"]
    # Levenshtein bilan tuzatish
    c = conn.cursor()
    c.execute("SELECT word FROM words")
    known_words = [row[0] for row in c.fetchall()]
    if not word or word in known_words:
        return word
    min_distance = float('inf')
    corrected = word
    for known in known_words:
        dist = distance(word.lower(), known.lower())
        if dist < min_distance and dist <= 3:
            min_distance = dist
            corrected = known
    return corrected

def correct_input(user_input, conn):
    words = re.findall(r'\w+', user_input.lower())
    corrected_words = [advanced_correct_word(w, conn) for w in words]
    return ' '.join(corrected_words)

# Matn faylidan o'rganish
def process_text_file(file_path, conn):
    try:
        file_path = file_path.replace('\\', os.sep).replace('/', os.sep)
        if not os.path.exists(file_path):
            return f"Xato: {file_path} fayli topilmadi."
        if os.path.getsize(file_path) == 0:
            return f"Xato: {file_path} fayli bo‘sh."
        word_counts = Counter()
        with open(file_path, 'r', encoding='utf-8', errors='replace') as file:
            while True:
                chunk = file.read(1024 * 1024)
                if not chunk:
                    break
                word_list = [w for w in re.findall(r'[a-zA-Z\'-]+\w*', chunk.lower())
                            if w not in STOP_WORDS and len(w) > 1]
                word_counts.update(word_list)
        if not word_counts:
            return f"Xato: Faylda foydali so‘zlar topilmadi."
        new_words_count = 0
        c = conn.cursor()
        for word, _ in word_counts.most_common(5000):
            c.execute("SELECT word FROM words WHERE word = ?", (word,))
            if not c.fetchone():
                word_type = "fel" if word.endswith(("moq", "di", "yapti")) else "ot"
                unli = "qalin" if any(c in "aou" for c in word) else "ingichka"
                kopluk = word + ("lar" if word_type == "ot" else "")
                save_word(conn, word, word_type, unli, kopluk)
                new_words_count += 1
        return f"Matn faylidagi so‘zlar muvaffaqiyatli o‘rganildi. Yangi so‘zlar: {new_words_count}"
    except Exception as e:
        return f"Xato: Matn faylini qayta ishlashda muammo: {str(e)}"

# Yangi so'z o'rganish
def learn_new_word(conn, word, word_type="ot"):
    c = conn.cursor()
    c.execute("SELECT word FROM words WHERE word = ?", (word,))
    if not c.fetchone():
        unli = "qalin" if any(c in "aou" for c in word) else "ingichka"
        kopluk = word + ("lar" if word_type == "ot" else "")
        save_word(conn, word, word_type, unli, kopluk)
        print(f"So'z o'rgandi: {word}")

# Suhbat tarixi
def save_conversation(conn, user_input, response):
    c = conn.cursor()
    c.execute("INSERT INTO conversation_history (user_input, response, timestamp) VALUES (?, ?, ?)",
              (user_input, response, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

# Yangi shablon o'rganish
def save_pattern(conn, word, pattern, response):
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO patterns (word, pattern) VALUES (?, ?)", (word, pattern))
    c.execute("INSERT OR REPLACE INTO responses (pattern, response) VALUES (?, ?)", (pattern, response))
    conn.commit()

# Gap tuzish
def generate_sentence(conn, templates, keywords):
    if not templates:
        return "Gap shablonlari topilmadi."
    template = random.choice(templates)
    pattern = template["pattern"]
    result = []
    c = conn.cursor()
    for part in pattern:
        c.execute("SELECT word, type, forms FROM words WHERE type = ? AND word NOT IN (?)",
                  (part, ",".join(STOP_WORDS)))
        candidates = [(row[0], json.loads(row[2]) if row[2] else None) for row in c.fetchall()
                     if not keywords or row[0] in keywords]
        if not candidates:
            return f"{part} turidagi so'z topilmadi."
        selected_word, forms = random.choice(candidates)
        result.append(selected_word)
    return " ".join(result)

# Kod yozish va o'rgatish
def teach_code(user_input, conn):
    user_input_lower = user_input.lower()
    if "kod yoz" in user_input_lower or "python o'rgat" in user_input_lower or "kod o'rgat" in user_input_lower:
        # Oddiy tushunchalar
        code_lessons = {
            "print": {
                "description": "'print' funksiyasi matn yoki qiymatlarni ekranga chiqaradi.",
                "example": "print('Salom, dunyo!')  # Chiqish: Salom, dunyo!"
            },
            "if": {
                "description": "'if' sharti bilan shartli kod yoziladi.",
                "example": "x = 10\nif x > 5:\n    print('x katta!')  # Chiqish: x katta!"
            },
            "for": {
                "description": "'for' tsikli ro'yxat yoki diapazon bo'yicha takrorlaydi.",
                "example": "for i in range(3):\n    print(i)  # Chiqish: 0, 1, 2"
            },
            "funksiya": {
                "description": "Funksiyalar kodni qayta ishlatish uchun ishlatiladi.",
                "example": "def salom():\n    print('Salom!')\nsalom()  # Chiqish: Salom!"
            }
        }
        # Tushunchalarni o'rgatish
        for key, lesson in code_lessons.items():
            if key in user_input_lower:
                response = f"{lesson['description']}\nMisol:\n{lesson['example']}"
                save_conversation(conn, user_input, response)
                return response
        # Maxsus kod yozish
        if "kalkulyator" in user_input_lower:
            code = """# Oddiy kalkulyator
def kalkulyator(a, b, amal):
    if amal == '+':
        return a + b
    elif amal == '-':
        return a - b
    elif amal == '*':
        return a * b
    elif amal == '/':
        return a / b if b != 0 else "Nolga bo'lib bo'lmaydi!"
    else:
        return "Noto'g'ri amal!"

# Misol
print(kalkulyator(10, 5, '+'))  # Chiqish: 15
print(kalkulyator(10, 5, '/'))  # Chiqish: 2.0
"""
            response = f"Oddiy kalkulyator kodi:\n```python\n{code}\n```\nBu kodni sinab ko‘rish uchun uni faylga saqlang (masalan, `kalkulyator.py`) va `python kalkulyator.py` bilan ishlating."
            save_conversation(conn, user_input, response)
            return response
        if "todo list" in user_input_lower:
            code = """# Oddiy To-Do List
todo_list = []

def qosh(ish):
    todo_list.append(ish)
    print(f"{ish} ro'yxatga qo'shildi.")

def olib_tashla(index):
    if 0 <= index < len(todo_list):
        olindi = todo_list.pop(index)
        print(f"{olindi} ro'yxatdan o'chirildi.")
    else:
        print("Noto'g'ri indeks!")

def kor():
    if todo_list:
        for i, ish in enumerate(todo_list):
            print(f"{i}: {ish}")
    else:
        print("Ro'yxat bo'sh!")

# Misol
qosh("Kitob o'qish")
qosh("Dars qilish")
kor()  # Chiqish: 0: Kitob o'qish, 1: Dars qilish
olib_tashla(0)
kor()  # Chiqish: 0: Dars qilish
"""
            response = f"Oddiy To-Do List kodi:\n```python\n{code}\n```\nBu kodni sinab ko‘rish uchun uni faylga saqlang (masalan, `todo.py`) va `python todo.py` bilan ishlating."
            save_conversation(conn, user_input, response)
            return response
        # Umumiy javob
        response = "Python kodini o‘rgataman yoki senga kod yozib beraman! 😊 Nima qilmoqchisan? Masalan, 'print ni o‘rgat', 'oddiy kalkulyator yoz' yoki 'todo list yoz' deb so‘ra."
        save_conversation(conn, user_input, response)
        return response
    return None

# Javob generatsiyasi
def generate_response(conn, templates, user_input):
    corrected_input = correct_input(user_input, conn)
    user_input_lower = corrected_input.lower()

    # Kod o'rgatish yoki yozish
    code_response = teach_code(user_input, conn)
    if code_response:
        return code_response

    # Suhbat tarixi
    c = conn.cursor()
    c.execute("SELECT user_input, response FROM conversation_history ORDER BY timestamp DESC LIMIT 1")
    last_convo = c.fetchone()
    context = last_convo[0] if last_convo else ""

    # Matn o'rganish
    if user_input_lower.startswith("matn o'rgan:"):
        file_path = user_input_lower.split(":", 1)[1].strip()
        response = process_text_file(file_path, conn)
        save_conversation(conn, user_input, response)
        return response

    # Yangi so'z o'rganish
    if "eslab qol" in user_input_lower or "o'rgan" in user_input_lower:
        words_to_learn = re.findall(r'\w+', user_input_lower)
        for word in words_to_learn:
            if word not in ["eslab", "qol", "o'rgan"]:
                learn_new_word(conn, word)
        response = "Yangi so'zlar eslab qolindi!"
        save_conversation(conn, user_input, response)
        return response

    # Yangi javob o'rgatish
    if "o'rgat" in user_input_lower and "dey" in user_input_lower:
        parts = user_input_lower.split("dey")
        if len(parts) > 1:
            pattern = parts[0].strip()
            response = parts[1].strip()
            save_pattern(conn, pattern, pattern, response)
            save_conversation(conn, user_input, f"Yangi javob o'rgatildi: {pattern} → {response}")
            return f"Yangi javob o'rgatildi: {pattern} → {response}"

    # Shablon bo'yicha javob
    for pattern, responses in INITIAL_MEMORY["responses"].items():
        if any(p in user_input_lower for p in INITIAL_MEMORY["patterns"][pattern]):
            response = responses
            save_conversation(conn, user_input, response)
            return response

    # Kontekst asosida javob
    if "nima" in user_input_lower and "bot" in context.lower():
        response = "Men DTBOTman, sen bilan suhbatlashyapman va kod yozishni o‘rgatyapman! 😊"
        save_conversation(conn, user_input, response)
        return response

    # Yangi so'zlarni o'rganish va gap tuzish
    words_input = re.findall(r'\w+', user_input_lower)
    for word in words_input:
        learn_new_word(conn, word)
    response = generate_sentence(conn, templates, words_input)
    save_conversation(conn, user_input, response)
    return response

# Signal handler
def signal_handler(sig, frame, conn):
    print("\nChatbot: Dastur to'xtatildi.")
    conn.close()
    sys.exit(0)

# Asosiy dastur
def main():
    print("Salom, Abror! Men DTBOTman! 😊 Savol bering, kod yozishni o‘rgating yoki yangi so‘zlarni o‘rgating.")
    print("Chiqish: 'hayr' yoki 'chiqish'.")
    print("Matn o'rganish: 'matn o'rgan: F:\\AI\\kitob.txt'")
    print("Kod o'rgatish: 'print ni o'rgat', 'oddiy kalkulyator yoz'")
    print("Misol: 'salom', 'ktoob bilan gap tuz', 'slm ishlar qanday', 'todo list yoz'")
    conn = init_db()
    templates = load_templates()
    c = conn.cursor()
    for word, patterns in INITIAL_MEMORY["patterns"].items():
        for pattern in patterns:
            c.execute("INSERT OR IGNORE INTO patterns (word, pattern) VALUES (?, ?)", (word, pattern))
    for pattern, response in INITIAL_MEMORY["responses"].items():
        c.execute("INSERT OR REPLACE INTO responses (pattern, response) VALUES (?, ?)", (pattern, response))
    conn.commit()
    signal.signal(signal.SIGINT, lambda sig, frame: signal_handler(sig, frame, conn))
    while True:
        try:
            user_input = input("Siz: ")
            if user_input.lower() in ["hayr", "chiqish"]:
                print("Chatbot: Hayr, ko'rishguncha!")
                conn.close()
                break
            response = generate_response(conn, templates, user_input)
            print("Chatbot:", response)
        except KeyboardInterrupt:
            print("Chatbot: Dastur to'xtatildi.")
            conn.close()
            break

if __name__ == "__main__":
    main()