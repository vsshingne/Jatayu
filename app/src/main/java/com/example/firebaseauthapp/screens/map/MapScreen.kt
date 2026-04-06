package com.example.firebaseauthapp.screens.map

import android.annotation.SuppressLint
import android.location.Location
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.foundation.layout.fillMaxSize
import com.google.maps.android.compose.GoogleMap
import com.google.maps.android.compose.rememberCameraPositionState
import com.google.maps.android.compose.Marker
import com.google.maps.android.compose.MarkerState
import com.google.maps.android.compose.Polyline
import com.google.android.gms.maps.model.LatLng
import com.google.android.gms.maps.model.BitmapDescriptorFactory
import com.google.android.gms.maps.CameraUpdateFactory
import com.example.firebaseauthapp.FirebaseUtils
import com.example.firebaseauthapp.screens.Task
import com.example.firebaseauthapp.screens.toTask
import kotlinx.coroutines.tasks.await
import com.google.firebase.firestore.GeoPoint
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.ui.Alignment
import androidx.compose.foundation.layout.Box
import androidx.compose.material3.Text
import androidx.compose.ui.graphics.Color
import androidx.compose.material3.Button
import androidx.compose.material3.Surface
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.layout.padding
import androidx.compose.ui.platform.LocalContext
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.FusedLocationProviderClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import androidx.compose.runtime.rememberCoroutineScope
import kotlinx.coroutines.launch
import com.google.accompanist.permissions.ExperimentalPermissionsApi
import com.google.accompanist.permissions.rememberPermissionState
import com.google.accompanist.permissions.isGranted

private const val DIRECTIONS_API_KEY = "<Directions API Key>"

@OptIn(ExperimentalPermissionsApi::class)
@SuppressLint("MissingPermission")
@Composable
fun MapScreen(focusLat: Double? = null, focusLng: Double? = null) {
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()
    val locationPermissionState = rememberPermissionState(android.Manifest.permission.ACCESS_FINE_LOCATION)
    var tasks by remember { mutableStateOf(listOf<Triple<Task, String, LatLng>>()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    val cameraPositionState = rememberCameraPositionState()
    var selectedTask by remember { mutableStateOf<Triple<Task, String, LatLng>?>(null) }
    var currentLocation by remember { mutableStateOf<LatLng?>(null) }
    // Removed: var routePoints, routeLoading, routeError

    // Request location permission if not granted
    LaunchedEffect(Unit) {
        if (!locationPermissionState.status.isGranted) {
            locationPermissionState.launchPermissionRequest()
        }
    }

    // Get current location only if permission is granted 
    
    LaunchedEffect(locationPermissionState.status.isGranted) {
        if (locationPermissionState.status.isGranted) {
            val fusedLocationClient = com.google.android.gms.location.LocationServices.getFusedLocationProviderClient(context)
            try {
                val loc: Location? = fusedLocationClient.lastLocation.await()
                loc?.let {
                    currentLocation = LatLng(it.latitude, it.longitude)
                }
            } catch (e: Exception) {
                error = "Failed to get current location: ${e.localizedMessage}"
            }
        }
    }

    // Fetch tasks
    LaunchedEffect(Unit) {
        loading = true
        error = null
        try {
            val active = FirebaseUtils.activeTasksCollection.get().await().documents.mapNotNull { doc ->
                val task = doc.toTask()
                val geo = task.location
                if (geo.latitude != 0.0 || geo.longitude != 0.0) Triple(task, "active", LatLng(geo.latitude, geo.longitude)) else null
            }
            val ongoing = FirebaseUtils.ongoingTasksCollection.get().await().documents.mapNotNull { doc ->
                val task = doc.toTask()
                val geo = task.location
                if (geo.latitude != 0.0 || geo.longitude != 0.0) Triple(task, "ongoing", LatLng(geo.latitude, geo.longitude)) else null
            }
            val completed = FirebaseUtils.completedTasksCollection.get().await().documents.mapNotNull { doc ->
                val task = doc.toTask()
                val geo = task.location
                if (geo.latitude != 0.0 || geo.longitude != 0.0) Triple(task, "completed", LatLng(geo.latitude, geo.longitude)) else null
            }
            val all = active + ongoing + completed
            tasks = all
            // Center/zoom to fit all markers or focus on a specific location
            if (focusLat != null && focusLng != null) {
                cameraPositionState.move(CameraUpdateFactory.newLatLngZoom(LatLng(focusLat, focusLng), 16f))
            } else if (all.isNotEmpty()) {
                val avgLat = all.map { it.third.latitude }.average()
                val avgLng = all.map { it.third.longitude }.average()
                cameraPositionState.move(CameraUpdateFactory.newLatLngZoom(LatLng(avgLat, avgLng), 10f))
            }
        } catch (e: Exception) {
            error = e.localizedMessage
        }
        loading = false
    }

    // Removed: fetchRoute and decodePolyline functions

    Box(Modifier.fillMaxSize()) {
        if (!locationPermissionState.status.isGranted) {
            Text(
                "Location permission is required to show your current location.",
                color = Color.Red,
                modifier = Modifier.align(Alignment.Center)
            )
            return@Box
        }
        GoogleMap(
            modifier = Modifier.fillMaxSize(),
            cameraPositionState = cameraPositionState
        ) {
            tasks.forEach { (task, type, latLng) ->
                val color = when (type) {
                    "active" -> BitmapDescriptorFactory.HUE_AZURE
                    "ongoing" -> BitmapDescriptorFactory.HUE_ORANGE
                    "completed" -> BitmapDescriptorFactory.HUE_GREEN
                    else -> BitmapDescriptorFactory.HUE_RED
                }
                Marker(
                    state = MarkerState(position = latLng),
                    title = task.address,
                    snippet = "Status: ${task.status}",
                    icon = BitmapDescriptorFactory.defaultMarker(color),
                    onClick = {
                        selectedTask = Triple(task, type, latLng)
                        false // show info window
                    }
                )
            }
            // Removed: Polyline drawing
        }
        when {
            loading -> CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
            error != null -> Text("Error: $error", color = Color.Red, modifier = Modifier.align(Alignment.Center))
            tasks.isEmpty() && !loading -> Text("No tasks found", color = Color.Gray, modifier = Modifier.align(Alignment.Center))
        }
        // Removed: Direction button and route error UI
    }
} 