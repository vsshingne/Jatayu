import firebase_admin
from firebase_admin import credentials, firestore, storage
from google.cloud.firestore_v1.base_query import FieldFilter
import requests
import os
from datetime import datetime
import math
from ultralytics import YOLO

GARBAGE_MODEL_PATH = "models/besta.pt"
MAX_DISTANCE_METERS = 300

cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    "storageBucket": "project2-962fe.appspot.com"
})
db = firestore.client(database_id="swachhdrone")
bucket = storage.bucket()

model = YOLO(GARBAGE_MODEL_PATH)

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

def download_image(file_url, local_path="temp.jpg"):
    r = requests.get(file_url, stream=True)
    if r.status_code == 200:
        with open(local_path, 'wb') as f:
            for chunk in r.iter_content(1024):
                f.write(chunk)
        return local_path
    return None

def garbage_found(image_path):
    results = model(image_path)
    for r in results:
        if len(r.boxes) > 0:
            return True
    return False

def validate_and_move_tasks():
    query = db.collection("ongoingTasks").where(filter=FieldFilter("status", "==", "processing"))
    ongoing_tasks = query.stream()

    for doc in ongoing_tasks:
        task = doc.to_dict()
        task_id = doc.id
        print(f"Processing task: {task_id}")

        passes_all = True
        local_img = None

        try:
            image_url = task.get("finalImg")
            if not image_url:
                print(f"Task {task_id} failed: No finalImgUrl.")
                passes_all = False
            else:
                local_img = download_image(image_url)
                if not local_img:
                    print(f"Task {task_id} failed: Image download failed.")
                    passes_all = False
                elif garbage_found(local_img):
                    print(f"Task {task_id} failed: Garbage found in image.")
                    passes_all = False

            init_time = task["timestamp"]
            final_time = task["finalTime"]
            if final_time <= init_time:
                print(f"Task {task_id} failed: Final time is not after initial time.")
                passes_all = False

            # init_loc = task["location"]
            # final_loc = task["finalLoco"]
            # distance = haversine(init_loc.latitude, init_loc.longitude, final_loc.latitude, final_loc.longitude)
            # if distance > MAX_DISTANCE_METERS:
            #     print(f"Task {task_id} failed: Distance ({distance:.2f}m) exceeds limit of {MAX_DISTANCE_METERS}m.")
            #     passes_all = False

        except (KeyError, TypeError, ValueError) as e:
            print(f"Task {task_id} failed validation with an error: {e}")
            passes_all = False
        finally:
            if local_img and os.path.exists(local_img):
                os.remove(local_img)

        if passes_all:
            print(f"Task {task_id} passed. Moving to completedTasks.")
            task["status"] = "completed"
            db.collection("completedTasks").document(task_id).set(task)
            db.collection("ongoingTasks").document(task_id).delete()
        else:
            print(f"Task {task_id} failed. Resetting status to pending.")
            db.collection("ongoingTasks").document(task_id).update({"status": "ongoing"})

if __name__ == "__main__":
    validate_and_move_tasks()