# 🚁 Drone Garbage Detection System

An AI-powered system that uses drones to automatically detect and report garbage dumps in cities. The system processes drone video feeds with GPS location data to detect garbage using YOLOv8 and creates tasks for municipal workers via Firebase.

## 🏗️ Architecture

- **Drone**: Records video + GPS location logs (GPX format)
- **Edge PC**: Python script processes video with YOLOv8 model
- **Firebase**: Stores detections and manages tasks
- **Android App**: Municipal workers manage cleanup tasks

## 🚀 Quick Start

### 1. Setup Python Environment
```bash
pip install -r requirements.txt
```

### 2. Configure Firebase
- Download `serviceAccountKey.json` from Firebase Console
- Place in project root directory
- Ensure Firebase Storage and Firestore are enabled

### 3. Test Firebase Connection
```bash
python test_firebase.py
```

### 4. Run Demo (with existing GPX file)
```bash
python demo_edge_device.py
```

### 5. Run Full Detection (with video file)
```bash
python edge_device.py
```

## 📁 Project Structure

```
├── edge_device.py              # Main detection script
├── demo_edge_device.py         # Demo script (works without video)
├── test_firebase.py           # Firebase connection test
├── requirements.txt            # Python dependencies
├── models/                     # YOLO models directory
│   └── best.pt                # Your trained model
├── serviceAccountKey.json      # Firebase credentials
├── 2025-07-14 14-56-38.bin.gpx # Sample GPX file
└── app/                        # Android application
    └── src/main/java/com/example/firebaseauthapp/
        ├── screens/            # App screens
        ├── viewmodel/          # ViewModels
        └── FirebaseUtils.kt    # Firebase utilities
```

## 🔧 Configuration

Edit the configuration section in `edge_device.py` to customize:
- Model path: `MODEL_PATH = "models/best.pt"`
- Video file: `VIDEO_PATH = "footage.mp4"`
- GPX file: `GPX_PATH = "2025-07-14 14-56-38.bin.gpx"`
- Firebase credentials: `FIREBASE_CRED_PATH = "serviceAccountKey.json"`
- Detection settings: `DUPLICATE_TIME_WINDOW = timedelta(seconds=10)`

## 📱 Android App

The Android app provides:
- User authentication
- Task management (Active/Ongoing/Completed)
- Map view with task locations
- Profile management

## 🎯 Features

- **Garbage Detection**: YOLOv8 model detects garbage in video frames
- **Smart Location Sync**: Automatically synchronizes video frames with GPS log data
- **Time-Based Interpolation**: Calculates exact GPS position for each frame using time progression
- **Duplicate Prevention**: Location filtering prevents redundant detections
- **Firebase Integration**: Automatic task creation and image storage
- **Mobile Management**: Android app for task management
- **GPX Support**: Native support for GPX format GPS logs

## 📊 Output

- **Firebase Firestore**: Task documents with location, images, metadata
- **Firebase Storage**: Detection images
- **Local Storage**: Detection images saved to `detections/` folder
- **Android App**: Real-time task updates for workers

## 🔄 How Video-GPS Synchronization Works

Since drone videos don't contain embedded timestamps, the system uses **time-based synchronization**:

1. **Video Analysis**: Calculates video duration from frame count and FPS
2. **GPS Log Analysis**: Determines GPS log duration from start/end timestamps
3. **Time Mapping**: Maps each video frame to corresponding GPS time position
4. **Location Interpolation**: Calculates exact GPS coordinates for each frame using linear interpolation
5. **Detection**: When garbage is detected, the system knows the exact GPS location

**Example:**
- Video: 300 seconds (5 minutes)
- GPS Log: 300 seconds (5 minutes)
- Frame 1500 (at 50 seconds): Maps to GPS time position 50 seconds
- System interpolates GPS coordinates between the two closest GPS log points

## 🧪 Testing

### Test Firebase Connection
```bash
python test_firebase.py
```

### Run Demo (No Video Required)
```bash
python demo_edge_device.py
```
This creates demo detections using the existing GPX file and tests the full Firebase integration.

### Run Full Detection
```bash
python edge_device.py
```
Requires:
- `models/best.pt` (YOLO model)
- `footage.mp4` (video file)
- `2025-07-14 14-56-38.bin.gpx` (GPX file)
- `serviceAccountKey.json` (Firebase credentials)

## 🔒 Security

- Firebase Authentication for app users
- Service account for Python backend
- Configurable security rules

## 📞 Support

For issues or questions:
1. Check that all dependencies are installed: `pip install -r requirements.txt`
2. Test Firebase connection: `python test_firebase.py`
3. Run demo to test full integration: `python demo_edge_device.py`
4. Check configuration settings in the script files
