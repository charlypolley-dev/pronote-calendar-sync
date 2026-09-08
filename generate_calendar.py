import datetime
import json
import os
import sys
import warnings
from icalendar import Calendar, Event
import pronotepy

warnings.filterwarnings("ignore")

CREDENTIALS_FILE = "credentials.json"

def load_credentials():
    if "PRONOTE_CREDENTIALS" in os.environ:
        try:
            return json.loads(os.environ["PRONOTE_CREDENTIALS"])
        except Exception as e:
            print(f"Erreur parsing variable PRONOTE_CREDENTIALS: {e}")

    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
            
    return None

def main():
    creds = load_credentials()
    if not creds:
        print("❌ Fichier de jeton 'credentials.json' introuvable.")
        print("👉 Lance d'abord : python3 pair.py")
        sys.exit(1)

    print("⏳ Connexion sécurisée à Pronote avec le jeton officiel...")
    
    try:
        # Token login using exported credentials
        client = pronotepy.Client.token_login(**creds)
    except Exception as e:
        print(f"❌ Erreur lors du token_login : {e}")
        sys.exit(1)

    if not client.logged_in:
        print("❌ Le jeton n'est plus valide.")
        sys.exit(1)

    print(f"✅ Connecté avec succès : {client.info.name} (Classe : {client.info.class_name})")

    # --- CRÉATION DE L'AGENDA APPLE CALENDAR ---
    cal = Calendar()
    cal.add('prodid', '-//Pronote to Apple Calendar//FR')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'Emploi du temps Pronote')
    cal.add('x-wr-timezone', 'Europe/Paris')

    # Plage de dates : du début de la semaine en cours jusqu'à dans 4 semaines (28 jours)
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
        
        # UID unique et immuable pour mise à jour automatique sans doublons
        uid_base = lesson.id if lesson.id else f"{lesson.start.isoformat()}-{subject_name}"
        lesson_uid = f"pronote-{uid_base}@pronote-sync"
        
        event.add('uid', lesson_uid)
        event.add('dtstart', lesson.start)
        event.add('dtend', lesson.end)
        event.add('dtstamp', datetime.datetime.now())

        # Gestion des profs absents et cours annulés
        if lesson.canceled:
            canceled_count += 1
            event.add('summary', f"❌ [ANNULÉ] {subject_name}")
            event.add('status', 'CANCELLED')
        else:
            event.add('summary', subject_name)
            event.add('status', 'CONFIRMED')

        # Construction de la description détaillée
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
    print(f"📊 Résumé : {len(lessons)} cours au total, dont {canceled_count} cours annulé(s)/absent(s).")

if __name__ == "__main__":
    main()
