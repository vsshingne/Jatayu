#!/usr/bin/env python3
"""
Drone Garbage Detection Edge Device Script
Processes drone video with GPS coordinates to detect garbage and create cleanup tasks.
"""

import cv2
import numpy as np
import gpxpy
import firebase_admin
from firebase_admin import credentials, firestore, storage
from ultralytics import YOLO
from PIL import Image
import os
import time
from datetime import datetime, timedelta
import logging
from typing import List, Tuple, Optional
import argparse
import requests

# Configuration
MODEL_PATH = "models/besta.pt"
VIDEO_PATH = "vid/footage.mp4"
GPX_PATH = "gpx/latest.gpx"
FIREBASE_CRED_PATH = "serviceAccountKey.json"
DUPLICATE_TIME_WINDOW = timedelta(seconds=10)
DETECTION_CONFIDENCE_THRESHOLD = 0.5
GOOGLE_MAPS_API_KEY = "AIzaSyApkrIWmDdT0elJF-Y56FaFpuBhZYcT6dk" 
FRAME_SKIP = 5  # Process every 5th frame (adjust as needed)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('drone_detection.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def remove_pink_tint(frame):
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    a = cv2.subtract(a, 10)
    lab = cv2.merge((l, a, b))
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

def enhance_frame(frame):
    yuv = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV)
    yuv[:, :, 0] = cv2.equalizeHist(yuv[:, :, 0])
    frame = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)
    kernel = np.array([[0, -1, 0],
                       [-1, 5, -1],
                       [0, -1, 0]])
    return cv2.filter2D(frame, -1, kernel)

def preprocess_drone_frame(frame):
    return enhance_frame(remove_pink_tint(frame))

class DroneGarbageDetector:
    def __init__(self):
        self.model = None
        self.db = None
        self.bucket = None
        self.gpx_data = []
        self.recent_detections = []
        
    def initialize_firebase(self):
        """Initialize Firebase connection"""
        try:
            if not firebase_admin._apps:
                cred = credentials.Certificate(FIREBASE_CRED_PATH)
                firebase_admin.initialize_app(cred, {
                    'storageBucket': 'project2-962fe.firebasestorage.app'
                })
            
            self.db = firestore.client(database_id='swachhdrone')
            self.bucket = storage.bucket()
            logger.info("Firebase initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Firebase initialization failed: {e}")
            return False
    
    def load_model(self):
        """Load YOLOv8 model"""
        try:
            self.model = YOLO(MODEL_PATH)
            logger.info(f"Model loaded from {MODEL_PATH}")
            return True
        except Exception as e:
            logger.error(f"Model loading failed: {e}")
            return False
    
    def parse_gpx_file(self, gpx_path: str) -> List[Tuple[datetime, float, float]]:
        """Parse GPX file and extract timestamped GPS coordinates"""
        try:
            with open(gpx_path, 'r') as gpx_file:
                gpx = gpxpy.parse(gpx_file)
            
            gpx_data = []
            for track in gpx.tracks:
                for segment in track.segments:
                    for point in segment.points:
                        gpx_data.append((
                            point.time,
                            point.latitude,
                            point.longitude
                        ))
            
            logger.info(f"Parsed {len(gpx_data)} GPS points from {gpx_path}")
            return gpx_data
        except Exception as e:
            logger.error(f"GPX parsing failed: {e}")
            return []
    
    def find_closest_gps_point(self, target_time: datetime) -> Optional[Tuple[float, float]]:
        """Find the closest GPS point to the given timestamp"""
        if not self.gpx_data:
            return None
        
        closest_point = min(self.gpx_data, key=lambda x: abs((x[0] - target_time).total_seconds()))
        return closest_point[1], closest_point[2]  # lat, lon
    
    def is_duplicate_detection(self, lat: float, lon: float, timestamp: datetime) -> bool:
        """Check if this is a duplicate detection within the time window"""
        for detection in self.recent_detections:
            time_diff = abs((timestamp - detection['timestamp']).total_seconds())
            if time_diff <= DUPLICATE_TIME_WINDOW.total_seconds():
                # Check if locations are close (within ~10 meters)
                lat_diff = abs(lat - detection['lat'])
                lon_diff = abs(lon - detection['lon'])
                if lat_diff < 0.0001 and lon_diff < 0.0001:  # Roughly 10 meters
                    return True
        return False
    
    def save_detection_image(self, frame: np.ndarray, timestamp: datetime) -> str:
        """Save detection image locally"""
        os.makedirs('detections', exist_ok=True)
        filename = f"detection_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}.jpg"
        filepath = os.path.join('detections', filename)
        cv2.imwrite(filepath, frame)
        logger.info(f"Detection image saved: {filepath}")
        return filepath
    
    def upload_to_firebase_storage(self, local_path: str, timestamp: datetime) -> str:
        """Upload image to Firebase Storage"""
        try:
            filename = f"garbage_images/detection_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}.jpg"
            blob = self.bucket.blob(filename)
            blob.upload_from_filename(local_path)
            blob.make_public()
            url = blob.public_url
            logger.info(f"Image uploaded to Firebase Storage: {url}")
            return url
        except Exception as e:
            logger.error(f"Firebase Storage upload failed: {e}")
            return ""
    
    def create_firestore_task(self, image_url: str, lat: float, lon: float, timestamp: datetime):
        """Create a new task in Firestore"""
        try:
            address = self.get_address_from_coordinates(lat, lon)
            task_data = {
                'imageUrl': image_url,
                'location': firestore.GeoPoint(lat, lon),
                'status': 'pending',
                'timestamp': timestamp,
                'address': address  
            }
            doc_ref = self.db.collection('activeTasks').add(task_data)
            logger.info(f"Task created in Firestore: {doc_ref[1].id}")
            
            # Add to recent detections to prevent duplicates
            self.recent_detections.append({
                'lat': lat,
                'lon': lon,
                'timestamp': timestamp
            })
            
            # Clean old detections
            cutoff_time = timestamp - DUPLICATE_TIME_WINDOW
            self.recent_detections = [d for d in self.recent_detections if d['timestamp'] > cutoff_time]
            
        except Exception as e:
            logger.error(f"Firestore task creation failed: {e}")
    
    def process_video(self):
        """Main video processing function"""
        if not os.path.exists(VIDEO_PATH):
            logger.error(f"Video file not found: {VIDEO_PATH}")
            return
        
        cap = cv2.VideoCapture(VIDEO_PATH)
        if not cap.isOpened():
            logger.error(f"Could not open video: {VIDEO_PATH}")
            return
        
        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps
        
        logger.info(f"Video: {total_frames} frames, {fps} FPS, {duration:.2f} seconds")
        
        # Calculate start time based on GPX data
        if self.gpx_data:
            start_time = self.gpx_data[0][0]
            logger.info(f"Processing video starting from: {start_time}")
        
        frame_count = 0
        detection_count = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1

            # Skip frames to speed up processing
            if frame_count % FRAME_SKIP != 0:
                continue

            # Calculate current video time
            current_video_time = start_time + timedelta(seconds=frame_count / fps)

            # Preprocess the frame before detection
            processed_frame = preprocess_drone_frame(frame)

            # Run YOLO detection
            results = self.model(processed_frame, conf=DETECTION_CONFIDENCE_THRESHOLD)
            
            for result in results:
                if result.boxes is not None and len(result.boxes) > 0:
                    # Garbage detected
                    detection_count += 1
                    logger.info(f"Garbage detected in frame {frame_count}")
                    
                    # Get GPS coordinates
                    gps_coords = self.find_closest_gps_point(current_video_time)
                    if gps_coords:
                        lat, lon = gps_coords
                        
                        # Check for duplicate detection
                        if not self.is_duplicate_detection(lat, lon, current_video_time):
                            # Save detection image
                            local_path = self.save_detection_image(frame, current_video_time)
                            
                            # Upload to Firebase Storage
                            image_url = self.upload_to_firebase_storage(local_path, current_video_time)
                            
                            if image_url:
                                # Create Firestore task
                                self.create_firestore_task(image_url, lat, lon, current_video_time)
                            else:
                                logger.warning("Skipping task creation due to upload failure")
                        else:
                            logger.info("Duplicate detection ignored")
                    else:
                        logger.warning("No GPS coordinates found for current time")
            
            # Progress update every 100 frames
            if frame_count % 100 == 0:
                progress = (frame_count / total_frames) * 100
                logger.info(f"Progress: {progress:.1f}% ({frame_count}/{total_frames} frames)")
        
        cap.release()
        logger.info(f"Video processing complete. Total detections: {detection_count}")
    
    def get_address_from_coordinates(self, lat: float, lon: float) -> str:
        """Get address from coordinates using Google Maps Geocoding API with OpenStreetMap fallback"""
        # Try Google Maps API first
        try:
            url = f"https://maps.googleapis.com/maps/api/geocode/json"
            params = {
                'latlng': f"{lat},{lon}",
                'key': GOOGLE_MAPS_API_KEY
            }
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data['status'] == 'OK' and data['results']:
                address = data['results'][0]['formatted_address']
                logger.info(f"Google Maps address found: {address}")
                return address
            else:
                logger.warning(f"Google Maps geocoding failed: {data.get('status', 'Unknown error')}")
                return self._get_address_from_osm(lat, lon)
        except Exception as e:
            logger.error(f"Google Maps API error: {e}")
            return self._get_address_from_osm(lat, lon)

    def _get_address_from_osm(self, lat: float, lon: float) -> str:
        """Get address from coordinates using OpenStreetMap Nominatim (free service)"""
        try:
            url = f"https://nominatim.openstreetmap.org/reverse"
            params = {
                'lat': lat,
                'lon': lon,
                'format': 'json',
                'addressdetails': 1
            }
            headers = {
                'User-Agent': 'DroneGarbageDetection/1.0 (https://github.com/your-repo; your-email@example.com)'
            }
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            if 'display_name' in data:
                address = data['display_name']
                logger.info(f"OpenStreetMap address found: {address}")
                return address
            else:
                logger.warning("OpenStreetMap geocoding failed")
                return "somewhere"
        except Exception as e:
            logger.error(f"OpenStreetMap API error: {e}")
            return "somewhere"

def main():
    """Main function"""
    global VIDEO_PATH, GPX_PATH, MODEL_PATH  # <-- Move this to the top
    parser = argparse.ArgumentParser(description='Drone Garbage Detection')
    parser.add_argument('--video', default=VIDEO_PATH, help='Path to video file')
    parser.add_argument('--gpx', default=GPX_PATH, help='Path to GPX file')
    parser.add_argument('--model', default=MODEL_PATH, help='Path to YOLO model')
    args = parser.parse_args()
    
    # Update paths if provided
    VIDEO_PATH = args.video
    GPX_PATH = args.gpx
    MODEL_PATH = args.model
    
    logger.info("Starting Drone Garbage Detection System")
    
    # Initialize detector
    detector = DroneGarbageDetector()
    
    # Check required files
    required_files = [MODEL_PATH, FIREBASE_CRED_PATH, GPX_PATH]
    for file_path in required_files:
        if not os.path.exists(file_path):
            logger.error(f"Required file not found: {file_path}")
            return
    
    # Initialize components
    if not detector.initialize_firebase():
        logger.error("Failed to initialize Firebase")
        return
    
    if not detector.load_model():
        logger.error("Failed to load model")
        return
    
    # Parse GPX file
    detector.gpx_data = detector.parse_gpx_file(GPX_PATH)
    if not detector.gpx_data:
        logger.error("Failed to parse GPX file")
        return
    # Process video
    detector.process_video()
    logger.info("Detection system completed")
if __name__ == "__main__":
    main()