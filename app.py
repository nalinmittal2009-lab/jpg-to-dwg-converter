import os
import shutil
import tempfile
import subprocess
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from starlette.background import BackgroundTask
import cv2
import numpy as np
import ezdxf
from ezdxf.addons import odafc

odafc.unix_exec_path = "/usr/bin/ODAFileConverter"

app = FastAPI(title="JPG to CAD Converter API")

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JPG to DWG/DXF Converter</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
      tailwind.config = { darkMode: 'class' }
    </script>
    <style>
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-thumb { background: #4B5563; border-radius: 4px; }
        .preview-svg svg { width: 100%; height: 100%; object-fit: contain; }
    </style>
</head>
<body class="bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 min-h-screen p-6 font-sans transition-colors">
    <div class="max-w-6xl mx-auto">
        <header class="mb-10 text-center">
            <h1 class="text-4xl font-extrabold tracking-tight text-blue-500 mb-2">Image to CAD Converter</h1>
            <p class="text-gray-400">100% Free Unlimited Local Processing Engine</p>
        </header>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div class="bg-white dark:bg-gray-800 rounded-xl shadow-xl p-6 border border-gray-200 dark:border-gray-700">
                <div id="dropzone" onclick="document.getElementById('file-input').click()" class="border-2 border-dashed border-gray-400 dark:border-gray-600 rounded-lg p-12 text-center cursor-pointer hover:border-blue-500 hover:bg-gray-50 dark:hover:bg-gray-700 transition-all mb-6">
                    <p class="text-gray-500 dark:text-gray-300 font-medium" id="drop-text">Drag & Drop JPG here or <span class="text-blue-500">Browse</span></p>
                    <input type="file" id="file-input" accept="image/jpeg, image/jpg, image/png" class="hidden" onchange="handleFile(this.files[0])">
                </div>

                <div class="space-y-5">
                    <div>
                        <label class="block text-sm font-semibold mb-1">Contrast Sensitivity</label>
                        <input type="range" id="threshold" min="0" max="255" value="127" class="w-full accent-blue-500" oninput="handleSliderChange()">
                    </div>
                    
                    <div class="flex items-center gap-3">
                        <input type="checkbox" id="invert" class="w-5 h-5 accent-blue-500" onchange="handleSliderChange()">
                        <label class="text-sm font-semibold">Invert Colors (White on Black)</label>
                    </div>

                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <label class="block text-sm font-semibold mb-1">Smoothing Level</label>
                            <select id="smoothing" class="w-full p-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg" onchange="handleSliderChange()">
                                <option value="Low">Low</option>
                                <option value="Medium">Medium</option>
                                <option value="High">High</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-sm font-semibold mb-1">Output Version</label>
                            <select id="version" class="w-full p-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg">
                                <option value="R2018">AutoCAD 2018</option>
                                <option value="R2013">AutoCAD 2013</option>
                            </select>
                        </div>
                    </div>
                </div>

                <div class="mt-8 grid grid-cols-2 gap-4">
                    <button onclick="downloadCAD('DXF')" class="w-full py-3 bg-gray-700 hover:bg-gray-600 text-white font-bold rounded-lg transition-colors">Download .DXF</button>
                    <button onclick="downloadCAD('DWG')" class="w-full py-3 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-lg transition-colors shadow-lg shadow-blue-500/30">Download .DWG</button>
                </div>
                
                <div id="status-bar" class="mt-4 text-center text-sm font-semibold text-red-400 hidden"></div>
            </div>

            <div class="bg-white dark:bg-gray-800 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 flex flex-col">
                <div class="bg-gray-100 dark:bg-gray-700 px-4 py-3 flex justify-between">
                    <h3 class="font-bold text-sm">Live Preview</h3>
                    <span id="stats" class="text-xs text-gray-400">Waiting for image...</span>
                </div>
                <div id="preview-container" class="preview-svg flex-grow p-4 flex items-center justify-center bg-gray-50 dark:bg-gray-900">
                    <p class="text-gray-400 text-sm">Upload an image to see vector paths.</p>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentFile = null;
        let debounceTimer;

        function handleFile(file) {
            currentFile = file;
            document.getElementById('drop-text').innerText = "Loaded: " + file.name;
            updatePreview();
        }

        function handleSliderChange() {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(updatePreview, 400);
        }

        async function updatePreview() {
            if(!currentFile) return;
            document.getElementById('stats').innerText = "Processing...";
            
            const formData = new FormData();
            formData.append("file", currentFile);
            formData.append("threshold", document.getElementById("threshold").value);
            formData.append("invert", document.getElementById("invert").checked);
            formData.append("smoothing", document.getElementById("smoothing").value);

            try {
                const response = await fetch("/preview", { method: "POST", body: formData });
                const data = await response.json();
                if(data.svg) {
                    document.getElementById("preview-container").innerHTML = data.svg;
                    document.getElementById('stats').innerText = "Vectors Ready";
                }
            } catch(err) {
                document.getElementById('stats').innerText = "Preview failed.";
            }
        }

        async function downloadCAD(formatType) {
            if(!currentFile) return alert("Upload an image first.");
            const statusBox = document.getElementById("status-bar");
            statusBox.classList.remove("hidden", "text-red-400");
            statusBox.classList.add("text-blue-400", "animate-pulse");
            statusBox.innerText = `Compiling ${formatType}...`;

            const formData = new FormData();
            formData.append("file", currentFile);
            formData.append("threshold", document.getElementById("threshold").value);
            formData.append("invert", document.getElementById("invert").checked);
            formData.append("smoothing", document.getElementById("smoothing").value);
            formData.append("format", formatType);
            formData.append("version", document.getElementById("version").value);

            try {
                const response = await fetch("/convert", { method: "POST", body: formData });
                if(!response.ok) {
                    const errData = await response.json();
                    throw new Error(errData.error || "Unknown server error");
                }
                
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = currentFile.name.split('.')[0] + "_" + formatType + "." + formatType.toLowerCase();
                a.click();
                
                statusBox.classList.remove("animate-pulse", "text-blue-400");
                statusBox.classList.add("text-green-400");
                statusBox.innerText = "✅ Download Complete!";
            } catch(err) {
                statusBox.classList.remove("animate-pulse", "text-blue-400", "text-green-400");
                statusBox.classList.add("text-red-400");
                statusBox.innerText = "❌ Error: " + err.message;
            }
        }
    </script>
</body>
</html>
"""

@app.get("/")
def get_ui():
    return HTMLResponse(content=HTML_CONTENT)

def process_image(image_bytes, threshold: int, invert: bool, smoothing: str, temp_dir: str):
    np_img = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(np_img, cv2.IMREAD_GRAYSCALE)
    _, th3 = cv2.threshold(img, threshold, 255, cv2.THRESH_BINARY)
    if invert:
        th3 = cv2.bitwise_not(th3)
    if smoothing == "Medium":
        th3 = cv2.medianBlur(th3, 3)
    elif smoothing == "High":
        th3 = cv2.medianBlur(th3, 5)
        kernel = np.ones((3,3), np.uint8)
        th3 = cv2.morphologyEx(th3, cv2.MORPH_CLOSE, kernel)
        
    bmp_path = os.path.join(temp_dir, "temp.bmp")
    cv2.imwrite(bmp_path, th3)
    return bmp_path

@app.post("/preview")
async def preview(file: UploadFile = File(...), threshold: int = Form(127), invert: bool = Form(False), smoothing: str = Form("Low")):
    image_bytes = await file.read()
    with tempfile.TemporaryDirectory() as temp_dir:
        bmp_path = process_image(image_bytes, threshold, invert, smoothing, temp_dir)
        svg_path = os.path.join(temp_dir, "out.svg")
        subprocess.run(["potrace", bmp_path, "-s", "-o", svg_path])
        with open(svg_path, "r") as f:
            svg_content = f.read()
    return JSONResponse(content={"svg": svg_content})

@app.post("/convert")
async def convert(file: UploadFile = File(...), threshold: int = Form(127), invert: bool = Form(False), smoothing: str = Form("Low"), format: str = Form("DWG"), version: str = Form("R2018")):
    image_bytes = await file.read()
    temp_dir = tempfile.mkdtemp()
    
    try:
        bmp_path = process_image(image_bytes, threshold, invert, smoothing, temp_dir)
        dxf_path = os.path.join(temp_dir, "temp.dxf")
        
        trace_result = subprocess.run(["potrace", bmp_path, "-b", "dxf", "-o", dxf_path], capture_output=True, text=True)
        if trace_result.returncode != 0:
            raise Exception("Potrace engine failed: " + trace_result.stderr)
        
        doc = ezdxf.readfile(dxf_path)
        doc.layers.add("OUTLINES", color=7)
        for entity in doc.modelspace():
            entity.dxf.layer = "OUTLINES"
            
        if format.upper() == "DXF":
            doc.saveas(dxf_path)
            return FileResponse(dxf_path, filename=f"{file.filename.split('.')[0]}.dxf", background=BackgroundTask(shutil.rmtree, temp_dir))
            
        else:
            dwg_path = os.path.join(temp_dir, "compiled.dwg")
            try:
                odafc.export_dwg(doc, dwg_path, version=version)
            except Exception as e:
                # If ODA completed with return code 0 but threw a warning via stderr, verify if the file exists anyway
                if not os.path.exists(dwg_path):
                    raise Exception("DWG Compilation Engine failed: " + str(e))
                
            if os.path.exists(dwg_path):
                return FileResponse(dwg_path, filename=f"{file.filename.split('.')[0]}.dwg", background=BackgroundTask(shutil.rmtree, temp_dir))
            else:
                raise Exception("Native DWG file was not created by the engine.")
                
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return JSONResponse(status_code=500, content={"error": str(e)})
