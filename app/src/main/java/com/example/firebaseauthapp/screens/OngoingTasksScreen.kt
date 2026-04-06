package com.example.firebaseauthapp.screens

import android.net.Uri
import android.util.Log
import android.location.Location    
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment

import androidx.compose.ui.Modifier

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController
import coil.compose.rememberAsyncImagePainter
import com.example.firebaseauthapp.FirebaseUtils

import com.example.firebaseauthapp.navigation.Screen
import com.google.android.gms.location.LocationServices
import com.google.firebase.Timestamp
import com.google.firebase.firestore.GeoPoint
import com.google.firebase.storage.FirebaseStorage
import kotlinx.coroutines.launch
import kotlinx.coroutines.tasks.await

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OngoingTasksScreen(navController: NavController) {
    var tasks by remember { mutableStateOf(listOf<Task>()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    var expandedTaskId by remember { mutableStateOf<String?>(null) }
    var markDoneDialogTask by remember { mutableStateOf<Task?>(null) }
    var markDoneLoading by remember { mutableStateOf(false) }
    var showSuccessMessage by remember { mutableStateOf(false) }
    var showErrorMessage by remember { mutableStateOf<String?>(null) }
    var validatingTaskId by remember { mutableStateOf<String?>(null) }
    val coroutineScope = rememberCoroutineScope()
    val snackbarHostState = remember { SnackbarHostState() }

    fun refreshTasks() {
        coroutineScope.launch {
            loading = true
            error = null
            try {
                val result = FirebaseUtils.ongoingTasksCollection.get().await()
                tasks = result.documents.map { it.toTask() }
            } catch (e: Exception) {
                error = e.localizedMessage
            }
            loading = false
        }
    }

    LaunchedEffect(Unit) { refreshTasks() }

    LaunchedEffect(showSuccessMessage) {
        if (showSuccessMessage) {
            snackbarHostState.showSnackbar("Task marked as done successfully!")
            showSuccessMessage = false
        }
    }

    LaunchedEffect(showErrorMessage) {
        showErrorMessage?.let { error ->
            snackbarHostState.showSnackbar("Error: $error")
            showErrorMessage = null
        }
    }

    Scaffold(
        containerColor = Color(0xFFFFF3E0),
        snackbarHost = { SnackbarHost(snackbarHostState) }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                shape = RoundedCornerShape(24.dp),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                elevation = CardDefaults.cardElevation(8.dp)
            ) {
                Text(
                    text = "Ongoing Tasks",
                    style = MaterialTheme.typography.headlineMedium.copy(
                        fontWeight = FontWeight.Bold,
                        color = Color.Black
                    ),
                    modifier = Modifier.padding(24.dp)
                )
            }

            Box(modifier = Modifier.fillMaxSize()) {
                when {
                    loading -> CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
                    error != null -> Text("Error: $error", color = MaterialTheme.colorScheme.error)
                    tasks.isEmpty() -> Text("No tasks found", modifier = Modifier.align(Alignment.Center), color = Color.Gray)
                    else -> LazyColumn {
                        items(tasks) { task ->
                            TaskListItem(
                                task = task,
                                isExpanded = expandedTaskId == task.id,
                                onClick = {
                                    expandedTaskId = if (expandedTaskId == task.id) null else task.id
                                },
                                actionButtons = if (expandedTaskId == task.id) {
                                    {
                                        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                            Button(onClick = { markDoneDialogTask = task }, enabled = !markDoneLoading) {
                                                Text("Mark as done")
                                            }
                                            Button(onClick = {
                                                val lat = task.location.latitude
                                                val lng = task.location.longitude
                                                navController.navigate(Screen.MapWithLocation.createRoute(lat, lng))
                                            }) {
                                                Text("Map")
                                            }
                                            Button(onClick = { validatingTaskId = task.id }) {
                                                Text("Complete Task")
                                            }
                                        }
                                    }
                                } else null
                            )
                        }
                    }
                }
            }
        }

        if (markDoneDialogTask != null) {
            AlertDialog(
                onDismissRequest = { if (!markDoneLoading) markDoneDialogTask = null },
                title = { Text("Mark as Done") },
                text = { Text("Do you want to mark this task as done? It will be moved to Completed Tasks.") },
                confirmButton = {
                    Button(onClick = {
                        markDoneLoading = true
                        coroutineScope.launch {
                            try {
                                val result = markTaskDone(markDoneDialogTask!!) // <-- from TaskUtils.kt
                                if (result.isSuccess) {
                                    showSuccessMessage = true
                                    refreshTasks()
                                } else {
                                    val errorMsg = result.exceptionOrNull()?.localizedMessage ?: "Failed to mark task as done"
                                    showErrorMessage = errorMsg
                                }
                            } catch (e: Exception) {
                                showErrorMessage = e.localizedMessage ?: "Unknown error occurred"
                            } finally {
                                markDoneLoading = false
                                markDoneDialogTask = null
                            }
                        }
                    }, enabled = !markDoneLoading) {
                        if (markDoneLoading) CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp)
                        else Text("Yes")
                    }
                },
                dismissButton = {
                    Button(onClick = { markDoneDialogTask = null }, enabled = !markDoneLoading) { Text("No") }
                }
            )
        }

        if (validatingTaskId != null) {
            AlertDialog(
                onDismissRequest = { validatingTaskId = null },
                title = { Text("Upload Completion Photo") },
                text = {
                    OngoingTaskValidationScreen(
                        taskId = validatingTaskId!!,
                        onUploadComplete = {
                            validatingTaskId = null
                            refreshTasks()
                        }
                    )
                },
                confirmButton = {},
                dismissButton = {
                    Button(onClick = { validatingTaskId = null }) { Text("Cancel") }
                }
            )
        }
    }
}

@Composable
fun OngoingTaskValidationScreen(
    taskId: String,
    onUploadComplete: () -> Unit
) {
    val context = LocalContext.current
    var selectedImageUri by remember { mutableStateOf<Uri?>(null) }
    var uploading by remember { mutableStateOf(false) }
    var uploadError by remember { mutableStateOf<String?>(null) }
    var uploadSuccess by remember { mutableStateOf(false) }

    val launcher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetContent()
    ) { uri: Uri? -> selectedImageUri = uri }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(16.dp)
    ) {
        Text("Upload completion photo for validation", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(16.dp))

        selectedImageUri?.let { uri ->
            Image(
                painter = rememberAsyncImagePainter(uri),
                contentDescription = "Selected Image",
                modifier = Modifier
                    .height(200.dp)
                    .fillMaxWidth()
            )
            Spacer(Modifier.height(8.dp))
        }

        Button(onClick = { launcher.launch("image/*") }) { Text("Select Photo") }
        Spacer(Modifier.height(16.dp))

        Button(
            onClick = {
                if (selectedImageUri != null) {
                    uploading = true
                    uploadError = null
                    uploadCompletionImage(
                        context = context,
                        taskId = taskId,
                        imageUri = selectedImageUri!!,
                        onSuccess = {
                            uploading = false
                            uploadSuccess = true
                            onUploadComplete()
                        },
                        onError = { error ->
                            uploading = false
                            uploadError = error.localizedMessage ?: "Upload failed"
                        }
                    )
                }
            },
            enabled = selectedImageUri != null && !uploading
        ) {
            if (uploading) CircularProgressIndicator(modifier = Modifier.size(24.dp))
            else Text("Upload & Validate")
        }

        Spacer(Modifier.height(16.dp))
        if (uploadSuccess) Text("Upload successful!", color = Color.Green)
        uploadError?.let { Text("Error: $it", color = MaterialTheme.colorScheme.error) }
    }
}

fun uploadCompletionImage(
    context: android.content.Context,
    taskId: String,
    imageUri: Uri,
    onSuccess: () -> Unit,
    onError: (Exception) -> Unit
) {
    val storageRef = FirebaseStorage.getInstance().reference
    val timestamp = System.currentTimeMillis()
    val fileName = "validation_images/${taskId}_$timestamp.jpg"
    val imageRef = storageRef.child(fileName)
    val fusedLocationClient = LocationServices.getFusedLocationProviderClient(context)

    try {
        fusedLocationClient.lastLocation.addOnSuccessListener { location: Location? ->
            imageRef.putFile(imageUri)
                .addOnSuccessListener {
                    imageRef.downloadUrl.addOnSuccessListener { uri ->
                        val finalImgUrl = uri.toString()
                        val finalTime = Timestamp.now()
                        val finalLoco = location?.let { GeoPoint(it.latitude, it.longitude) }
                        val updateMap = mutableMapOf<String, Any>(
                            "finalImg" to finalImgUrl,
                            "finalTime" to finalTime
                        )

                        if (finalLoco != null) updateMap["finalLoco"] = finalLoco
                        FirebaseUtils.ongoingTasksCollection.document(taskId)
                            .update(updateMap)
                            .addOnSuccessListener {
                                FirebaseUtils.ongoingTasksCollection.document(taskId)
                                    .update("status", "processing")
                                    .addOnSuccessListener { onSuccess() }
                                    .addOnFailureListener { e -> onError(e) }
                            }
                    }.addOnFailureListener { e -> onError(e) }
                }
                .addOnFailureListener { e -> onError(e) }
        }.addOnFailureListener { e -> onError(e) }
    } catch (e: Exception) {
        onError(e)
    }
}
