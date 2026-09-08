import base64
import datetime
import json
import os
import sys
import warnings
from icalendar import Calendar, Event
import pronotepy
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes

warnings.filterwarnings("ignore")

CREDENTIALS_FILE = "credentials.json"
ENCRYPTED_FILE = "credentials.enc"
SECRET_KEY_ENV = "PRONOTE_SECRET_KEY"

def derive_key(passphrase: str, salt: bytes) -> bytes:
    return PBKDF2(passphrase, salt, dkLen=32, count=1000)

def encrypt_data(data: dict, passphrase: str) -> str:
    raw = json.dumps(data).encode("utf-8")
    salt = get_random_bytes(16)
    key = derive_key(passphrase, salt)
    cipher = AES.new(key, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(raw)
    payload = {
        "salt": base64.b64encode(salt).decode("utf-8"),
        "nonce": base64.b64encode(cipher.nonce).decode("utf-8"),
        "tag": base64.b64encode(tag).decode("utf-8"),
        "data": base64.b64encode(ciphertext).decode("utf-8"),
    }
    return json.dumps(payload)

def decrypt_data(encrypted_str: str, passphrase: str) -> dict:
    payload = json.loads(encrypted_str)
    salt = base64.b64decode(payload["salt"])
    nonce = base64.b64decode(payload["nonce"])
    tag = base64.b64decode(payload["tag"])
    ciphertext = base64.b64decode(payload["data"])
    key = derive_key(passphrase, salt)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    decrypted = cipher.decrypt_and_verify(ciphertext, tag)
    return json.loads(decrypted.decode("utf-8"))

def load_credentials():
    passphrase = os.environ.get(SECRET_KEY_ENV)
    
    # 1. From encrypted file
    if passphrase and os.path.exists(ENCRYPTED_FILE):
        try:
            with open(ENCRYPTED_FILE, "r", encoding="utf-8") as f:
                return decrypt_data(f.read(), passphrase)
        except Exception as e:
            print(f"Erreur déchiffrement {ENCRYPTED_FILE}: {e}")

    # 2. From local credentials.json
    if os.path.exists(CREDENTIALS_FILE):
        try:
            with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Erreur lecture {CREDENTIALS_FILE}: {e}")

    return None

def save_credentials(creds: dict):
    # Save locally
    with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
        json.dump(creds, f, indent=2)

    # Save encrypted if passphrase present
    passphrase = os.environ.get(SECRET_KEY_ENV)
    if passphrase:
        encrypted = encrypt_data(creds, passphrase)
        with open(ENCRYPTED_FILE, "w", encoding="utf-8") as f:
            f.write(encrypted)
        print("🔒 Jeton renouvelé et chiffré dans credentials.enc")

def main():
    creds = load_credentials()
    if not creds:
        print("❌ Identifiants introuvables. Lance d'abord pair.py.")
        sys.exit(1)

    print("⏳ Connexion sécurisée à Pronote avec le jeton officiel...")
    try:
        client = pronotepy.Client.token_login(**creds)
    except Exception as e:
        print(f"❌ Erreur lors du token_login : {e}")
        sys.exit(1)

    if not client.logged_in:
        print("❌ Le jeton n'est plus valide.")
        sys.exit(1)

    print(f"✅ Connecté : {client.info.name} (Classe : {client.info.class_name})")

    # Mise à jour et persistance immédiate du nouveau jeton renouvelé par Pronote
    updated_creds = client.export_credentials()
    save_credentials(updated_creds)

    # --- CRÉATION DE L'AGENDA APPLE CALENDAR ---
    cal = Calendar()
    cal.add('prodid', '-//Pronote to Apple Calendar//FR')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'Emploi du temps Pronote')
    cal.add('x-wr-timezone', 'Europe/Paris')

    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=today.weekday())
    end_date = start_date + datetime.timedelta(days=28)

    print(f"📅 Récupération des cours du {start_date.strftime('%d/%m')} au {end_date.strftime('%d/%m')}...")
    lessons = client.lessons(start_date, end_date)
    print(f"✨ {len(lessons)} cours trouvés.")

    canceled_count = 0
    for lesson in lessons:
        event = Event()
        subject_name = lesson.subject.name if lesson.subject else "Cours"
        uid_base = lesson.id if lesson.id else f"{lesson.start.isoformat()}-{subject_name}"
        lesson_uid = f"pronote-{uid_base}@pronote-sync"
        
        event.add('uid', lesson_uid)
        event.add('dtstart', lesson.start)
        event.add('dtend', lesson.end)
        event.add('dtstamp', datetime.datetime.now())

        if lesson.canceled:
            canceled_count += 1
            event.add('summary', f"❌ [ANNULÉ] {subject_name}")
            event.add('status', 'CANCELLED')
        else:
            event.add('summary', subject_name)
            event.add('status', 'CONFIRMED')

        desc_lines = []
        if lesson.canceled:
            motif = lesson.status if lesson.status else "Professeur absent / Cours annulé"
            desc_lines.append(f"⚠️ STATUT : {motif}")
        elif lesson.status:
            desc_lines.append(f"ℹ️ Statut : {lesson.status}")

        if lesson.teacher_names:
            desc_lines.append(f"👨‍🏫 Professeur : {', '.join(lesson.teacher_names)}")

        if lesson.classroom:
            event.add('location', lesson.classroom)
            desc_lines.append(f"📍 Salle : {lesson.classroom}")

        if hasattr(lesson, 'group_names') and lesson.group_names:
            desc_lines.append(f"👥 Groupe : {', '.join(lesson.group_names)}")

        if hasattr(lesson, 'memo') and lesson.memo:
            desc_lines.append(f"📝 Remarque : {lesson.memo}")

        event.add('description', "\n".join(desc_lines))
        cal.add_component(event)

    output_path = "pronote.ics"
    with open(output_path, "wb") as f:
        f.write(cal.to_ical())

    print(f"🎉 Agenda généré avec succès dans '{output_path}' !")
    print(f"📊 Résumé : {len(lessons)} cours au total, dont {canceled_count} annulé(s)/absent(s).")

if __name__ == "__main__":
    main()
