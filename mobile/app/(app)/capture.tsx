import React, { useRef, useState } from "react";
import {
  View, Text, TouchableOpacity, StyleSheet,
  ActivityIndicator, Alert, Dimensions,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { CameraView, useCameraPermissions } from "expo-camera";
import * as ImagePicker from "expo-image-picker";
import { useRouter } from "expo-router";
import { uploadAudit } from "../../lib/api";
import { useStore } from "../../lib/store";

const { width } = Dimensions.get("window");

export default function CaptureScreen() {
  const router = useRouter();
  const { selectedAccount } = useStore();
  const cameraRef = useRef<CameraView>(null);

  const [permission, requestPermission] = useCameraPermissions();
  const [uploading, setUploading] = useState(false);
  const [status, setStatus] = useState<"ready" | "uploading" | "processing">("ready");
  const [message, setMessage] = useState("");

  if (!permission) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator color="#3b82f6" size="large" />
      </SafeAreaView>
    );
  }

  if (!permission.granted) {
    return (
      <SafeAreaView style={styles.container}>
        <Text style={styles.text}>Camera permission required</Text>
        <TouchableOpacity style={styles.button} onPress={requestPermission}>
          <Text style={styles.buttonText}>Grant Permission</Text>
        </TouchableOpacity>
      </SafeAreaView>
    );
  }

  if (!selectedAccount) {
    return (
      <SafeAreaView style={styles.container}>
        <Text style={styles.text}>Select a store first</Text>
        <TouchableOpacity style={styles.button} onPress={() => router.push("/(app)/accounts")}>
          <Text style={styles.buttonText}>Go to Stores</Text>
        </TouchableOpacity>
      </SafeAreaView>
    );
  }

  const handleUpload = async (imageUri: string) => {
    try {
      setUploading(true);
      setStatus("uploading");
      setMessage("📤 Uploading...");

      const result = await uploadAudit(
        imageUri,
        selectedAccount.id,
        new Date().toISOString()
      );

      setStatus("processing");
      setMessage("🔄 Processing image...\n(checking quality, reading labels)");

      // Poll for result
      await pollAuditStatus(result.audit_id);

      setStatus("ready");
      setMessage("");
      router.push(`/(app)/audit/${result.audit_id}`);
    } catch (err) {
      setStatus("ready");
      setMessage("");
      Alert.alert("Error", err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleCapture = async () => {
    if (!cameraRef.current) return;

    try {
      setStatus("uploading");
      setMessage("📸 Taking photo...");

      const photo = await cameraRef.current.takePictureAsync({
        quality: 0.88,
        base64: false,
      });

      if (!photo) {
        Alert.alert("Failed to capture photo");
        setStatus("ready");
        return;
      }

      await handleUpload(photo.uri);
    } catch (err) {
      setStatus("ready");
      setMessage("");
      Alert.alert("Error", err instanceof Error ? err.message : "Capture failed");
    }
  };

  const handleGallery = async () => {
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: false,
        quality: 0.88,
      });

      if (result.canceled) return;

      if (!result.assets || result.assets.length === 0) {
        Alert.alert("No image selected");
        return;
      }

      const imageUri = result.assets[0].uri;
      await handleUpload(imageUri);
    } catch (err) {
      Alert.alert("Error", err instanceof Error ? err.message : "Gallery access failed");
    }
  };

  async function pollAuditStatus(auditId: string) {
    for (let i = 0; i < 60; i++) {
      const res = await fetch(`https://valid-subgroup-sturdy.ngrok-free.dev/audits/${auditId}`, {
        headers: {
          Authorization: `Bearer ${await getToken()}`,
        },
      });
      const audit = await res.json();

      if (audit.status === "final" || audit.status === "retake_required" || audit.status === "guardrail_rejected") {
        return audit;
      }

      await new Promise(r => setTimeout(r, 1000));
    }
    throw new Error("Processing timeout");
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.cameraContainer}>
        <CameraView ref={cameraRef} style={StyleSheet.absoluteFillObject} />
        <View style={styles.overlay}>
          <View style={styles.frameGuide} />
        </View>
      </View>

      <View style={styles.controls}>
        {status === "ready" && (
          <>
            <Text style={styles.storeLabel}>{selectedAccount.name}</Text>
            <View style={styles.buttonRow}>
              <TouchableOpacity
                style={[styles.button, styles.galleryBtn, uploading && styles.disabled]}
                onPress={handleGallery}
                disabled={uploading}
              >
                <Text style={styles.buttonLabel}>📱 Gallery</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.shutterButton, uploading && styles.disabled]}
                onPress={handleCapture}
                disabled={uploading}
              >
                {uploading ? (
                  <ActivityIndicator color="#fff" size="large" />
                ) : (
                  <View style={styles.shutterInner} />
                )}
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.button, styles.exitBtn, uploading && styles.disabled]}
                onPress={() => router.push("/(app)/audits")}
                disabled={uploading}
              >
                <Text style={styles.buttonLabel}>← Back</Text>
              </TouchableOpacity>
            </View>
          </>
        )}

        {status === "uploading" && (
          <View style={styles.statusBox}>
            <ActivityIndicator color="#3b82f6" size="large" />
            <Text style={styles.statusText}>{message}</Text>
          </View>
        )}

        {status === "processing" && (
          <View style={styles.statusBox}>
            <ActivityIndicator color="#3b82f6" size="large" />
            <Text style={styles.statusText}>{message}</Text>
          </View>
        )}
      </View>
    </SafeAreaView>
  );
}

async function getToken(): Promise<string | null> {
  const { getItem } = await import("../../lib/storage");
  return getItem("kosha_access_token");
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#000" },
  cameraContainer: { flex: 1, position: "relative" },
  overlay: { flex: 1, justifyContent: "center", alignItems: "center" },
  frameGuide: {
    width: width * 0.9,
    aspectRatio: 1,
    borderWidth: 2,
    borderColor: "#3b82f6",
    borderRadius: 12,
    opacity: 0.6,
  },
  controls: {
    padding: 20,
    alignItems: "center",
    backgroundColor: "#1a1a1a",
    borderTopWidth: 1,
    borderTopColor: "#333",
  },
  storeLabel: { color: "#fff", fontSize: 14, marginBottom: 16, fontWeight: "600" },
  shutterButton: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: "#3b82f6",
    justifyContent: "center",
    alignItems: "center",
  },
  shutterInner: {
    width: 70,
    height: 70,
    borderRadius: 35,
    backgroundColor: "#fff",
  },
  disabled: { opacity: 0.5 },
  statusBox: { alignItems: "center", gap: 12 },
  statusText: { color: "#fff", fontSize: 14, textAlign: "center" },
  text: { color: "#fff", fontSize: 16, marginBottom: 20, textAlign: "center" },
  button: { backgroundColor: "#3b82f6", padding: 12, borderRadius: 8, paddingHorizontal: 16 },
  buttonLabel: { color: "#fff", fontWeight: "600", textAlign: "center", fontSize: 12 },
  buttonText: { color: "#fff", fontWeight: "600", textAlign: "center" },
  buttonRow: { flexDirection: "row", alignItems: "center", gap: 12, justifyContent: "center" },
  galleryBtn: { backgroundColor: "#059669" },
  exitBtn: { backgroundColor: "#7c3aed" },
});
