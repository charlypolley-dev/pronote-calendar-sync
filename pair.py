import base64
import datetime
import json
import os
import subprocess
import sys
import uuid
import cv2
import pronotepy
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes

CREDENTIALS_FILE = "credentials.json"
ENCRYPTED_FILE = "credentials.enc"

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

def read_qr_from_image(image_path="qrcode.png"):
    if not os.path.exists(image_path):
        return None
    detector = cv2.QRCodeDetector()
    img = cv2.imread(image_path)
    if img is None:
        return None
    data, _, _ = detector.detectAndDecode(img)
    if not data:
        h, w, _ = img.shape
        crop = img[int(h*0.3):, :]
        data, _, _ = detector.detectAndDecode(crop)
    if data:
        try:
            return json.loads(data)
        except Exception:
            return None
    return None

def pair_qr(qr_data: dict, pin: str):
    device_uuid = str(uuid.uuid4())
    print("⏳ Connexion officielle à Pronote via le jeton mobile...")
    
    client = pronotepy.Client.qrcode_login(
        qr_code=qr_data,
        pin=pin,
        uuid=device_uuid,
        device_name="Apple Calendar Sync"
    )

    if not client.logged_in:
        print("❌ Échec de l'association.")
        return False

    print(f"✅ Association réussie pour {client.info.name} (Classe: {client.info.class_name}) !")
    creds = client.export_credentials()

    with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
        json.dump(creds, f, indent=2)

    # Chiffrer pour GitHub Actions
    if os.path.exists(".secret_key"):
        with open(".secret_key", "r") as f:
            passphrase = f.read().strip()
        enc = encrypt_data(creds, passphrase)
        with open(ENCRYPTED_FILE, "w", encoding="utf-8") as f:
            f.write(enc)
        print("🔒 Jeton chiffré dans credentials.enc pour GitHub Actions.")

    return True

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        # CLI usage: python pair.py <image_or_json> <pin>
        first_arg = sys.argv[1]
        pin = sys.argv[2]
        if os.path.exists(first_arg):
            qr_data = read_qr_from_image(first_arg)
        else:
            qr_data = json.loads(first_arg)
        if qr_data:
            pair_qr(qr_data, pin)
    else:
        # Interactive
        qr_data = read_qr_from_image("qrcode.png")
        if not qr_data:
            raw = input("Colle le texte du QR code ou chemin de l'image : ").strip()
            if os.path.exists(raw):
                qr_data = read_qr_from_image(raw)
            else:
                qr_data = json.loads(raw)
        pin = input("PIN (4 chiffres) : ").strip()
        pair_qr(qr_data, pin)
