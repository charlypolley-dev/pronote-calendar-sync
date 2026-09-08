import base64
import datetime
import hashlib
import json
import os
import sys
import warnings
import zoneinfo
from icalendar import Calendar, Event, Timezone, TimezoneStandard, TimezoneDaylight
import pronotepy
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2

warnings.filterwarnings("ignore")

CREDENTIALS_FILE = "credentials.json"
ENCRYPTED_FILE = "credentials.enc"
SECRET_KEY_ENV = "PRONOTE_SECRET_KEY"
PARIS_TZ = zoneinfo.ZoneInfo("Europe/Paris")

def derive_key(passphrase: str, salt: bytes) -> bytes:
    return PBKDF2(passphrase, salt, dkLen=32, count=1000)

def encrypt_data(data: dict, passphrase: str) -> str:
    raw = json.dumps(data).encode("utf-8")
    salt = os.urandom(16)
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
    if not passphrase and os.path.exists(".secret_key"):
        with open(".secret_key", "r") as f:
            passphrase = f.read().strip()

    if passphrase and os.path.exists(ENCRYPTED_FILE):
        try:
            with open(ENCRYPTED_FILE, "r", encoding="utf-8") as f:
                return decrypt_data(f.read(), passphrase)
        except Exception as e:
            print(f"Erreur déchiffrement {ENCRYPTED_FILE}: {e}")

    if os.path.exists(CREDENTIALS_FILE):
        try:
            with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Erreur lecture {CREDENTIALS_FILE}: {e}")

    return None

def save_credentials(creds: dict):
    with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
        json.dump(creds, f, indent=2)

    passphrase = os.environ.get(SECRET_KEY_ENV)
    if not passphrase and os.path.exists(".secret_key"):
        with open(".secret_key", "r") as f:
            passphrase = f.read().strip()

    if passphrase:
        encrypted = encrypt_data(creds, passphrase)
        with open(ENCRYPTED_FILE, "w", encoding="utf-8") as f:
            f.write(encrypted)

def build_vtimezone():
    tz = Timezone()
    tz.add('tzid', 'Europe/Paris')
    tz.add('x-lic-location', 'Europe/Paris')

    # Standard time (CET = UTC+1)
    tz_standard = TimezoneStandard()
    tz_standard.add('tzname', 'CET')
    tz_standard.add('dtstart', datetime.datetime(1971, 10, 31, 3, 0, 0))
    tz_standard.add('rrule', {'freq': 'yearly', 'bymonth': 10, 'byday': '-1su'})
    tz_standard.add('tzoffsetfrom', datetime.timedelta(hours=2))
    tz_standard.add('tzoffsetto', datetime.timedelta(hours=1))
    tz.add_component(tz_standard)

    # Daylight saving time (CEST = UTC+2)
    tz_daylight = TimezoneDaylight()
    tz_daylight.add('tzname', 'CEST')
    tz_daylight.add('dtstart', datetime.datetime(1971, 3, 28, 2, 0, 0))
    tz_daylight.add('rrule', {'freq': 'yearly', 'bymonth': 3, 'byday': '-1su'})
    tz_daylight.add('tzoffsetfrom', datetime.timedelta(hours=1))
    tz_daylight.add('tzoffsetto', datetime.timedelta(hours=2))
    tz.add_component(tz_daylight)

    return tz

def main():
    creds = load_credentials()
    if not creds:
        print("❌ Identifiants introuvables.")
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

    # Mise à jour et rotation du jeton
    updated_creds = client.export_credentials()
    save_credentials(updated_creds)

    # --- CRÉATION DE L'AGENDA APPLE CALENDAR OPTIMISÉ ---
    cal = Calendar()
    cal.add('prodid', '-//Pronote to Apple Calendar Sync//FR')
    cal.add('version', '2.0')
    cal.add('calscale', 'GREGORIAN')
    cal.add('method', 'PUBLISH')
    cal.add('x-wr-calname', 'Emploi du temps Pronote')
    cal.add('x-wr-timezone', 'Europe/Paris')
    cal.add('x-wr-caldesc', 'Emploi du temps synchronisé automatiquement depuis Pronote avec gestion des absences.')
    cal.add_component(build_vtimezone())

    # Plage de dates : du début de l'année scolaire jusqu'à dans 10 semaines
    today = datetime.date.today()
    start_date = client.start_day if hasattr(client, 'start_day') and client.start_day else (today - datetime.timedelta(days=14))
    end_date = today + datetime.timedelta(days=70)

    print(f"📅 Récupération intégrale des cours du {start_date.strftime('%d/%m/%Y')} au {end_date.strftime('%d/%m/%Y')}...")
    
    try:
        lessons = client.lessons(start_date, end_date)
    except Exception as e:
        print(f"⚠️ Erreur lors de la récupération : {e}")
        lessons = client.lessons(today - datetime.timedelta(days=7), today + datetime.timedelta(days=28))

    print(f"✨ {len(lessons)} cours récupérés au total.")

    canceled_count = 0
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    seen_uids = set()

    for idx, lesson in enumerate(lessons):
        event = Event()
        
        # 1. Fuseau horaire Europe/Paris
        start_dt = lesson.start
        end_dt = lesson.end
        
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=PARIS_TZ)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=PARIS_TZ)

        event.add('dtstart', start_dt)
        event.add('dtend', end_dt)
        event.add('dtstamp', now_utc)

        # 2. UID 100% UNIQUE PAR INSTANCE DE COURS (CRITIQUE POUR APPLE CALENDAR !)
        # Si les UIDs ne sont pas uniques par date/heure, Apple Calendar écrase tous les cours !
        subj_clean = lesson.subject.name if lesson.subject else "Cours"
        time_slot = start_dt.strftime('%Y%m%d%H%M')
        raw_uid_str = f"{lesson.id}_{time_slot}_{subj_clean}"
        uid_hash = hashlib.md5(raw_uid_str.encode('utf-8')).hexdigest()
        lesson_uid = f"pronote-{time_slot}-{uid_hash[:12]}@pronote-sync"
        
        # Sécurité anti-doublon absolu
        if lesson_uid in seen_uids:
            lesson_uid = f"pronote-{time_slot}-{uid_hash[:12]}-{idx}@pronote-sync"
        seen_uids.add(lesson_uid)

        event.add('uid', lesson_uid)

        # 3. Formatage du Titre (SUMMARY)
        if lesson.canceled:
            canceled_count += 1
            motif_court = f" ({lesson.status})" if lesson.status else ""
            event.add('summary', f"❌ [ANNULÉ] {subj_clean}{motif_court}")
            event.add('status', 'CANCELLED')
            event.add('transp', 'TRANSPARENT')
        else:
            event.add('summary', subj_clean)
            event.add('status', 'CONFIRMED')
            event.add('transp', 'OPAQUE')

        # 4. Lieu / Salle (LOCATION)
        if lesson.classroom:
            room = lesson.classroom.strip()
            if room.lower().startswith("salle") or room.lower().startswith("tp") or room.lower().startswith("labo"):
                event.add('location', room)
            else:
                event.add('location', f"Salle {room}")
        elif "SPORT" in subj_clean.upper() or "EPS" in subj_clean.upper():
            event.add('location', "Gymnase / EPS")

        # 5. Description enrichie et structurée
        desc_lines = []
        if lesson.canceled:
            desc_lines.append("❌ COURS ANNULÉ")
            if lesson.status:
                desc_lines.append(f"⚠️ Motif : {lesson.status}")
            desc_lines.append("─────────────────────")

        if lesson.teacher_names:
            desc_lines.append(f"👨‍🏫 Professeur : {', '.join(lesson.teacher_names)}")

        if lesson.classroom:
            desc_lines.append(f"📍 Salle : {lesson.classroom}")

        if hasattr(lesson, 'group_names') and lesson.group_names:
            desc_lines.append(f"👥 Groupe : {', '.join(lesson.group_names)}")

        if hasattr(lesson, 'memo') and lesson.memo:
            desc_lines.append(f"📝 Remarque : {lesson.memo}")

        if lesson.status and not lesson.canceled:
            desc_lines.append(f"ℹ️ Statut : {lesson.status}")

        event.add('description', "\n".join(desc_lines))
        cal.add_component(event)

    output_path = "pronote.ics"
    with open(output_path, "wb") as f:
        f.write(cal.to_ical())

    print(f"🎉 Fichier '{output_path}' généré avec succès !")
    print(f"📊 Bilan : {len(lessons)} cours (tous avec UID unique). Dont {canceled_count} cours annulés.")

if __name__ == "__main__":
    main()
