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

# Fayllar va ma'lumotlar bazasi
DB_FILE = r"F:\AI\chatbot.db"
TEMPLATES_FILE = r"F:\AI\sentence_templates.json"

# O'zbek tilidagi stop-so'zlar
STOP_WORDS = {"va", "bu", "u", "bilan", "uchun", "da", "dan", "ga", "ni", "bir", "lekin"}

# O'zbek tiliga mos boshlang'ich ma'lumotlar
INITIAL_MEMORY = {
    "patterns": {
        "salom": ["salom", "assalomu alaykum"],
        "nima": ["nima gap", "nima yangilik", "nima qilyapsan", "bugun nima kun"],
        "gap": ["nima gap"],
        "yaxshimisiz": ["yaxshimisiz"],
        "rahmat": ["rahmat"],
        "qalesan": ["qalesan", "qandaysan"],
        "isming": ["isming nima"],
        "qayerda": ["qayerdasan", "qayerdansan"],
        "yosh": ["yoshing nechada"],
        "bugun": ["bugun nima kun"],
        "kun": ["bugun nima kun"],
        "vaqt": ["hozir soat necha"],
        "soat": ["hozir soat necha"],
        "ob": ["ob-havo qanday"],
        "havo": ["ob-havo qanday"],
        "qanday": ["qandaysan", "ob-havo qanday"],
        "shahar": ["qaysi shahar"],
        "qaysi": ["qaysi shahar"],
        "o'zbek": ["o'zbek tilida gaplashasanmi"],
        "til": ["o'zbek tilida gaplashasanmi"],
        "yordam": ["qanday yordam bera olasan"],
        "xayr": ["xayr", "xayrli kun"]
        "salom": ["salom", "assalomu alaykum"],
        "nima": ["nima gap", "nima yangilik", "nima qilyapsan", "nima qilayapti bot"],
        "qalesan": ["qalesan", "qandaysan", "nima hol"],
        "isming": ["isming nima"],
        "hayron": ["hayronman", "nima bu"],
        "yaxshi": ["yaxshisan", "yaxshi", "zo‘r"],
        "rahmat": ["rahmat", "tashakkur"]
    },
    "responses": {
        "salom": "Salom! Qanday yordam bera olaman?",
        "assalomu alaykum": "Va alaykum assalom! Qanday yordam kerak?",
        "nima gap": "Hammasi zo'r! Senda nima gap?",
        "nima yangilik": "Hech qanday yangilik yo'q, sen aytsang-chi!",
        "nima qilyapsan": "Suhbatlashyapman, sen nima qilyapsan?",
        "bugun nima kun": "Bugun dushanba! Yana nima bilmoqchisan?",
        "yaxshimisiz": "Yaxshi, rahmat! Siz yaxshimisiz?",
        "rahmat": "Arzimaydi!",
        "qalesan": "Zo'r, sen qalesan?",
        "qandaysan": "Yaxshi, sen qandaysan?",
        "isming nima": "Men DTBOTman! 😊 Isming nima?",
        "qayerdasan": "Men bulutlarda, sen qayerdasan? 😄",
        "qayerdansan": "Men Toshkentdanman! Sen qayerdansan?",
        "yoshing nechada": "Men abadiy yoshman! 😄 Senchi?",
        "hozir soat necha": "Hozir vaqtni bilish uchun telefoningga qarasang-chi! 😜",
        "ob-havo qanday": "Ob-havo haqida aniq bilmayman, lekin derazadan qarasang bo'ladi! 😊",
        "qaysi shahar": "Men Toshkentni yaxshi ko'raman, sen qaysi shahardan?",
        "o'zbek tilida gaplashasanmi": "Albatta, o'zbek tilida gaplashaman! Yana nima so'raymiz?",
        "qanday yordam bera olasan": "Savollarga javob beraman, yangi narsalarni o'rganaman! Nima so'ramoqchisan?",
        "xayr": "Xayr, yana ko'rishamiz!",
        "xayrli kun": "Senga ham xayrli kun!"
        "salom": "Salom! Qanday yordam bera olaman?",
        "nima": "Hozir shu yerda sen bilan suhbatlashyapman! 😊 Senda nima gap?",
        "qalesan": "Yaxshi, sen qandaysan?",
        "isming": "Men DTBOTman! 😊 Isming nima?",
        "hayron": "Hayron bo‘lishga hojat yo‘q, hammasini tuzatamiz! 😊",
        "yaxshi": "Zo‘r, yaxshi kayfiyatda bo‘l! 😎",
        "rahmat": "Arzimaydi, doim yordam beraman!"
    }
}

# Ma'lumotlar bazasini ishga tushirish
def init_db():
    try:
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
        print(f"Ma'lumotlar bazasi {DB_FILE} muvaffaqiyatli ishga tushirildi.")
        return conn
    except Exception as e:
        print(f"Xato: Ma'lumotlar bazasini ishga tushirishda muammo: {e}")
        sys.exit(1)

# So'zlarni yuklash
def load_words(conn):
    try:
        c = conn.cursor()
        c.execute("SELECT word, type, unli, kopluk, forms FROM words")
        words = []
        for row in c.fetchall():
            word_data = {
                "word": row[0],
                "type": row[1],
                "unli": row[2],
                "kopluk": row[3],
                "forms": json.loads(row[4]) if row[4] else None
            }
            words.append(word_data)
        print(f"So'zlar ma'lumotlar bazasidan yuklandi: {len(words)} ta")
        return words
    except Exception as e:
        print(f"Xato: So'zlarni yuklashda muammo: {e}")
        return []

# So'zlarni saqlash
def save_word(conn, word, word_type, unli, kopluk, forms=None):
    try:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO words (word, type, unli, kopluk, forms) VALUES (?, ?, ?, ?, ?)",
                  (word, word_type, unli, kopluk, json.dumps(forms) if forms else None))
        conn.commit()
    except Exception as e:
        print(f"Xato: So'zni saqlashda muammo: {e}")

# Gap shablonlarini yuklash
def load_templates():
    try:
        if os.path.exists(TEMPLATES_FILE):
            with open(TEMPLATES_FILE, 'r', encoding='utf-8') as file:
                templates = json.load(file)
                print(f"Gap shablonlari {TEMPLATES_FILE} dan muvaffaqiyatli yuklandi.")
                return templates.get("sentence_templates", [])
        else:
            print(f"{TEMPLATES_FILE} fayli topilmadi.")
            return []
    except json.JSONDecodeError as e:
        print(f"Xato: {TEMPLATES_FILE} fayli JSON formatida emas: {e}")
        return []
    except Exception as e:
        print(f"Xato: Gap shablonlarini yuklashda muammo: {e}")
        return []

# Noto'g'ri so'zlarni tuzatish
from uznlp.morphology import MorphAnalyzer

analyzer = MorphAnalyzer()

def advanced_correct_word(word, conn):
    # Birinchi uzNLP bilan so'z shaklini tahlil qilish
    analysis = analyzer.analyze(word)
    if analysis.get("root"):
        return analysis["root"]
    # Agar uzNLP topmasa, Levenshtein bilan tuzatish
    c = conn.cursor()
    c.execute("SELECT word FROM words")
    known_words = [row[0] for row in c.fetchall()]
    if not word or word in known_words:
        return word
    min_distance = float('inf')
    corrected = word
    for known in known_words:
        dist = distance(word.lower(), known.lower())
        if dist < min_distance and dist <= 3:  # Masofa chegarasini kengaytirdik
            min_distance = dist
            corrected = known
    return corrected

def correct_input(user_input, conn):
    words = re.findall(r'\w+', user_input.lower())
    corrected_words = [advanced_correct_word(w, conn) for w in words]
    return ' '.join(corrected_words)

def correct_input(user_input, conn):
    c = conn.cursor()
    c.execute("SELECT word FROM words")
    known_words = [row[0] for row in c.fetchall()]
    words = re.findall(r'\w+', user_input.lower())
    corrected_words = [correct_word(w, known_words) for w in words]
    return ' '.join(corrected_words)

# Matn faylini qayta ishlash
def process_text_file(file_path, conn):
    try:
        file_path = file_path.replace('\\', os.sep).replace('/', os.sep)
        if not os.path.exists(file_path):
            return f"Xato: {file_path} fayli topilmadi. Iltimos, yo‘lni tekshiring."
        
        if os.path.getsize(file_path) == 0:
            return f"Xato: {file_path} fayli bo‘sh."
        
        word_counts = Counter()
        chunk_size = 1024 * 1024
        with open(file_path, 'r', encoding='utf-8', errors='replace') as file:
            while True:
                chunk = file.read(chunk_size)
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
    except UnicodeDecodeError:
        return f"Xato: Fayl UTF-8 kodlashida emas. Iltimos, faylni UTF-8 formatiga o‘tkazing."
    except PermissionError:
        return f"Xato: {file_path} fayliga kirish huquqi yo‘q."
    except Exception as e:
        return f"Xato: Matn faylini qayta ishlashda muammo: {str(e)}"

# Yangi so'zni o'rganish
def learn_new_word(conn, word, word_type="ot"):
    try:
        c = conn.cursor()
        c.execute("SELECT word FROM words WHERE word = ?", (word,))
        if not c.fetchone():
            unli = "qalin" if any(c in "aou" for c in word) else "ingichka"
            kopluk = word + ("lar" if word_type == "ot" else "")
            save_word(conn, word, word_type, unli, kopluk)
            print(f"So'z o'rgandi: {word}")
    except Exception as e:
        print(f"Xato: So'zni o'rganishda muammo: {e}")

# Suhbatni saqlash
def save_conversation(conn, user_input, response):
    try:
        c = conn.cursor()
        c.execute("INSERT INTO conversation_history (user_input, response, timestamp) VALUES (?, ?, ?)",
                  (user_input, response, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    except Exception as e:
        print(f"Xato: Suhbatni saqlashda muammo: {e}")

# Grammatik shakl generatsiyasi
def generate_grammar_form(conn, word, form_type, details=None):
    try:
        c = conn.cursor()
        c.execute("SELECT type, kopluk, forms FROM words WHERE word = ?", (word,))
        result = c.fetchone()
        if not result:
            return f"{word} so'zlar ro'yxatida topilmadi."
        
        word_type, kopluk, forms = result
        forms = json.loads(forms) if forms else None
        
        if form_type == "kopluk" and word_type == "ot":
            return kopluk
        if form_type in ["otgan", "hozirgi", "kelasi"] and word_type == "fel":
            if forms and details in forms.get(form_type, {}):
                return forms[form_type][details]
            return f"{form_type} zamon uchun {details} shaxs topilmadi."
        return f"{word} uchun {form_type} shakli topilmadi."
    except Exception as e:
        return f"Xato: Grammatik shakl generatsiyasida muammo: {e}"

# Gap generatsiyasi
def generate_sentence(conn, templates, keywords):
    try:
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
            if part == "fel" and forms:
                form = forms.get("hozirgi", {}).get("3s", selected_word)
                result.append(form)
            else:
                result.append(selected_word)
        
        return " ".join(result)
    except Exception as e:
        return f"Xato: Gap generatsiyasida muammo: {e}"

# Javob generatsiya qilish
def generate_response(conn, templates, user_input):
    corrected_input = correct_input(user_input, conn)
    user_input_lower = corrected_input.lower()
    # Suhbat tarixini saqlash
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

    # Shablon bo'yicha javob
    for pattern, responses in INITIAL_MEMORY["responses"].items():
        if any(p in user_input_lower for p in INITIAL_MEMORY["patterns"][pattern]):
            response = responses
            save_conversation(conn, user_input, response)
            return response

    # Kontekst asosida javob
    if "nima" in user_input_lower and "bot" in context.lower():
        response = "Men DTBOTman, sen bilan suhbatlashyapman! 😊"
        save_conversation(conn, user_input, response)
        return response

    # Yangi so'zlarni o'rganish va gap tuzish
    words_input = re.findall(r'\w+', user_input_lower)
    for word in words_input:
        learn_new_word(conn, word)
    response = generate_sentence(conn, templates, words_input)
    save_conversation(conn, user_input, response)
    return response

# Dastur to'xtatilganda ma'lumotlarni saqlash
def signal_handler(sig, frame, conn):
    print("\nChatbot: Dastur to'xtatildi. Ma'lumotlar saqlandi.")
    conn.close()
    sys.exit(0)

# Asosiy dastur
def main():
    print("Salom, Abror! Men o'zbek tilidagi DTBOTman! 😊 Savol bering yoki yangi so'zlarni o'rgating.")
    print("Chiqish uchun 'hayr' yoki 'chiqish' deb yozing.")
    print("Yangi so'zlarni o'rganish uchun: 'eslab qol' yoki 'o'rgan' deb yozing.")
    print("Matn faylini o'rganish uchun: 'matn o'rgan: fayl_yo'li' (masalan, matn o'rgan: F:\\AI\\kitob.txt)")
    print("Grammatika so'rovlari: 'kitob kopluk', 'yozmoq otgan 1s'")
    print("Gap tuzish: 'kitob bilan gap tuz', 'yozmoq bilan gap tuz'")
    print("Misol suhbat: 'salom', 'ishlar qanday', 'eslab qol', 'matn o'rgan: F:\\AI\\kitob.txt'")
    
    conn = init_db()
    templates = load_templates()
    
    # Boshlang'ich ma'lumotlarni ma'lumotlar bazasiga qo'shish
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
        except EOFError:
            print("Chatbot: Kiritish tugadi. Ma'lumotlar saqlandi.")
            conn.close()
            break
        except KeyboardInterrupt:
            print("Chatbot: Dastur to'xtatildi. Ma'lumotlar saqlandi.")
            conn.close()
            break
        
        if user_input.lower() in ["hayr", "chiqish"]:
            print("Chatbot: Hayr, ko'rishguncha!")
            conn.close()
            break
        
        if user_input.lower().startswith("o'rgat:"):
            try:
                parts = user_input.split(":", 2)
                if len(parts) != 3:
                    print("Chatbot: Noto'g'ri format! Quyidagi formatdan foydalaning: o'rgat: savol : javob")
                    print("Misol: o'rgat: bugun nima kun : Bugun dushanba!")
                    continue
                _, learn_input, response = parts
                learn_input = learn_input.strip().lower()
                response = response.strip()
                if not learn_input or not response:
                    print("Chatbot: Savol yoki javob bo'sh bo'lmasligi kerak!")
                    continue
                c = conn.cursor()
                words = re.findall(r'\w+', learn_input)
                for word in words:
                    c.execute("INSERT OR IGNORE INTO patterns (word, pattern) VALUES (?, ?)", (word, learn_input))
                c.execute("INSERT OR REPLACE INTO responses (pattern, response) VALUES (?, ?)", (learn_input, response))
                conn.commit()
                print(f"Chatbot: O'rgandim! '{learn_input}' uchun javob: {response}")
                save_conversation(conn, user_input, f"O'rgandim! '{learn_input}' uchun javob: {response}")
            except Exception as e:
                print(f"Chatbot: O'rgatishda xato yuz berdi: {e}")
            continue
        
        response = generate_response(conn, templates, user_input)
        print("Chatbot:", response)

if __name__ == "__main__":
    main()
