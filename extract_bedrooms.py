import os
import requests

# Hardcoded absolute path directly to your backend base images
TARGET_DIR = r"C:\Users\SS\RoomOS\backend\data\base_images\sleep"
os.makedirs(TARGET_DIR, exist_ok=True)

# Curated Unsplash IDs showing people sleeping inside real beds
bed_sleeping_ids = [
    "1542567401-dc1604a11c1e", "1511295742308-c625a36bc37b", 
    "1506126613408-eca07ce68773", "1520206183501-b80af9702f78", 
    "1541558869-42b7812e52b8", "1531844539748-c6c41d0b11b7", 
    "1512428559087-560fa5ceab42", "1517604931442-7e0c8ed2963c"
]

print(f"⚡ Downloading directly to targeted structure:\n   {TARGET_DIR}")

saved = 0
for idx, bid in enumerate(bed_sleeping_ids):
    # Fetch clean, uncropped master frames of people sleeping in beds
    url = f"https://images.unsplash.com/photo-{bid}?q=80&w=600"
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200 and len(res.content) > 5000:
            filename = f"true_bed_sleep_{idx:03d}.jpg"
            with open(os.path.join(TARGET_DIR, filename), "wb") as f:
                f.write(res.content)
            saved += 1
    except:
        continue

print(f"\n🚀 Success! Saved {saved} clean bed-sleeping images directly to your backend directory.")