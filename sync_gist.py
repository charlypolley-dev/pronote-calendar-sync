import json
import os
import sys
import urllib.request

def update_gist():
    gist_id = os.environ.get("GIST_ID")
    github_token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    
    if not os.path.exists("pronote.ics"):
        print("❌ Fichier pronote.ics introuvable.")
        sys.exit(1)

    with open("pronote.ics", "r", encoding="utf-8") as f:
        ics_content = f.read()

    if not gist_id or not github_token:
        print("ℹ️ GIST_ID ou GITHUB_TOKEN non configuré. Le fichier 'pronote.ics' reste local.")
        return

    url = f"https://api.github.com/gists/{gist_id}"
    payload = {
        "description": "Emploi du temps Pronote pour Apple Calendrier (Auto-Sync)",
        "files": {
            "pronote.ics": {
                "content": ics_content
            }
        }
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "Pronote-Calendar-Sync"
        },
        method="PATCH"
    )

    try:
        with urllib.request.urlopen(req) as resp:
            if resp.status == 200:
                print("✅ Gist mis à jour avec succès dans le cloud !")
            else:
                print(f"⚠️ Réponse API GitHub : {resp.status}")
    except Exception as e:
        print(f"❌ Erreur mise à jour Gist : {e}")

if __name__ == "__main__":
    update_gist()
