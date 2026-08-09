import urllib.request
import os

print("Downloading Kokoro ONNX model and voices...")

model_url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
voices_url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"

if not os.path.exists("kokoro-v1.0.onnx"):
    print("Downloading kokoro-v1.0.onnx (this may take a minute)...")
    urllib.request.urlretrieve(model_url, "kokoro-v1.0.onnx")

if not os.path.exists("voices-v1.0.bin"):
    print("Downloading voices-v1.0.bin...")
    urllib.request.urlretrieve(voices_url, "voices-v1.0.bin")

print("Download complete!")
