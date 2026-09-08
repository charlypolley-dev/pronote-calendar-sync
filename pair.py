import json
import os
import sys
import uuid
import cv2
import pronotepy

CREDENTIALS_FILE = "credentials.json"

def read_qr_from_image(image_path="qrcode.png"):
    if not os.path.exists(image_path):
        return None
    detector = cv2.QRCodeDetector()
    img = cv2.imread(image_path)
    if img is None:
        return None
    data, _, _ = detector.detectAndDecode(img)
    if data:
        try:
            return json.loads(data)
        except Exception:
            return None
    return None

def main():
    print("==================================================")
    print("🔑 ASSOCIATION OFFICIELLE PRONOTE (SANS RISQUE)")
    print("==================================================")
    
    # 1. Check if image qrcode.png exists
    qr_data = None
    if os.path.exists("qrcode.png"):
        print("📸 Image 'qrcode.png' détectée...")
        qr_data = read_qr_from_image("qrcode.png")
        if qr_data:
            print("✅ QR Code décodé avec succès depuis l'image !")

    # 2. If no image or decode failed, ask for text / JSON
    if not qr_data:
        print("\nSi tu as une capture d'écran du QR Code de Pronote :")
        print("👉 Place l'image nommée 'qrcode.png' dans ce dossier.")
        print("\nOU scanne le QR code avec ton téléphone et colle le texte ici.")
        raw_input_text = input("\nColle le texte du QR code (ou appuie sur Entrée si qrcode.png est prêt) : ").strip()
        
        if raw_input_text:
            try:
                qr_data = json.loads(raw_input_text)
            except Exception:
                print("❌ Format de texte invalide. Assure-toi de copier tout le texte du QR Code.")
                sys.exit(1)
        else:
            qr_data = read_qr_from_image("qrcode.png")
            if not qr_data:
                print("❌ Impossible de trouver ou lire 'qrcode.png'.")
                sys.exit(1)

    pin = input("Saisis le code PIN à 4 chiffres défini sur Pronote : ").strip()
    if len(pin) != 4 or not pin.isdigit():
        print("❌ Le code PIN doit comporter 4 chiffres.")
        sys.exit(1)

    device_uuid = str(uuid.uuid4())
    print("\n⏳ Connexion et génération du jeton officiel auprès de Pronote...")

    try:
        client = pronotepy.Client.qrcode_login(
            qr_code=qr_data,
            pin=pin,
            uuid=device_uuid,
            device_name="Apple Calendar Sync"
        )
    except Exception as e:
        print(f"❌ Erreur lors de l'association : {e}")
        print("Vérifie que le QR code n'a pas expiré (génère-en un nouveau si besoin) et que le PIN est exact.")
        sys.exit(1)

    if not client.logged_in:
        print("❌ Échec de connexion.")
        sys.exit(1)

    credentials = client.export_credentials()
    with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
        json.dump(credentials, f, indent=2)

    print("\n" + "="*50)
    print(f"🎉 SUCCÈS ! Appareil associé pour : {client.info.name}")
    print(f"📁 Jeton sauvegardé dans '{CREDENTIALS_FILE}'")
    print("Tu n'auras plus JAMAIS besoin de scanner de QR code ni d'entrer ton mot de passe.")
    print("="*50)

if __name__ == "__main__":
    main()
