package com.example.firebaseauthapp

import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.storage.FirebaseStorage

object FirebaseUtils {
    val firestore: FirebaseFirestore by lazy { FirebaseFirestore.getInstance("swachhdrone") }
    val storage: FirebaseStorage by lazy { FirebaseStorage.getInstance() }

    // Task Collections
    val activeTasksCollection
        get() = firestore.collection("activeTasks")
    val ongoingTasksCollection
        get() = firestore.collection("ongoingTasks")
    val completedTasksCollection
        get() = firestore.collection("completedTasks")
    
    // Drone Detection Collections
    val detectedGarbageCollection
        get() = firestore.collection("detected_garbage")
    val droneSessionsCollection
        get() = firestore.collection("drone_sessions")
    
    // User Collections
    val usersCollection
        get() = firestore.collection("users")
    
    // Storage References
    val garbageImagesStorage
        get() = storage.reference.child("garbage_images")
    val profileImagesStorage
        get() = storage.reference.child("profile_images")
} 