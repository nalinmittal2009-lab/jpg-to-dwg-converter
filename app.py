import os
import shutil
import tempfile
import subprocess
import sqlite3
import datetime
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask
import cv2
import numpy as np
import ezdxf
from ezdxf.math import Matrix44
from ezdxf.addons import odafc, Importer
import pytesseract

odafc.unix_exec_path = "/usr/bin/ODAFileConverter"

# Database Setup for Reviews
DB_FILE = "reviews.db"
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS reviews 
                 (id INTEGER PRIMARY KEY, name TEXT, review TEXT, image_path TEXT, timestamp TEXT)''')
    conn.commit()
    conn.close()

init_db()

app = FastAPI(title="Pro CAD Converter")
os.makedirs("static_reviews", exist_ok=True)
app.mount("/static", StaticFiles(directory="static_reviews"), name="static")

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en" class="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pro JPG to CAD Converter</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
      tailwind.config = { darkMode: 'class' }
    </script>
    <style>
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-thumb { background: #4B5563; border-radius: 4px; }
    </style>
</head>
<body class="bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 min-h-screen p-6 font-sans transition-colors duration-300">
    <div class="max-w-6xl mx-auto">
        
        <header class="mb-10 flex justify-between items-center">
            <div>
                <h1 class="text-4xl font-extrabold tracking-tight text-blue-600 dark:text-blue-500 mb-2">Image to CAD Pro</h1>
                <p class="text-gray-500 dark:text-gray-400">Auto-Scaling • OCR Text • Multi-Layer</p>
            </div>
            <button onclick="toggleTheme()" class="p-3 rounded-full bg-gray-200 dark:bg-gray-800 hover:bg-gray-300 dark:hover:bg-gray-700 transition">
                <span id="theme-icon">🌙</span>
            </button>
        </header>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-8 mb-12">
            <div class="bg-white dark:bg-gray-800 rounded-xl shadow-xl p-6 border border-gray-200 dark:border-gray-700">
                <div id="dropzone" onclick="document.getElementById('file-input').click()" class="border-2 border-dashed border-gray-400 dark:border-gray-600 rounded-lg p-12 text-center cursor-pointer hover:border-blue-500 transition-all mb-6">
                    <p class="text-gray-500 dark:text-gray-300 font-medium" id="drop-text">Drag & Drop JPG here or <span class="text-blue-500">Browse</span></p>
                    <input type="file" id="file-input" accept="image/jpeg, image/jpg, image/png" class="hidden" onchange="handleFile(this.files[0])">
                </div>

                <div class="space-y-4">
                    <div>
                        <label class="block text-sm font-semibold mb-1">Output Filename</label>
                        <input type="text" id="filename" placeholder="my_drawing" class="w-full p-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-white">
                    </div>
                    
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <label class="block text-sm font-semibold mb-1">Page Size</label>
                            <select id="pagesize" class="w-full p-2 bg-gray-50 dark:bg-gray-700 border rounded-lg text-gray-900 dark:text-white">
                                <option value="A4">A4 (297x210)</option>
                                <option value="A3">A3 (420x297)</option>
                                <option value="ORIGINAL">Original Image Size</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-sm font-semibold mb-1">Drawing Units</label>
                            <select id="units" class="w-full p-2 bg-gray-50 dark:bg-gray-700 border rounded-lg text-gray-900 dark:text-white">
                                <option value="mm">Millimeters (mm)</option>
                                <option value="cm">Centimeters (cm)</option>
                                <option value="in">Inches (in)</option>
                            </select>
                        </div>
                    </div>

                    <div>
                        <label class="block text-sm font-semibold mb-1">AutoCAD Version</label>
                        <select id="version" class="w-full p-2 bg-gray-50 dark:bg-gray-700 border rounded-lg text-gray-900 dark:text-white">
                            <option value="R2018">AutoCAD 2027</option>
                            <option value="R2018">AutoCAD 2026</option>
                            <option value="R2018">AutoCAD 2025</option>
                            <option value="R2018">AutoCAD 2024</option>
                            <option value="R2018">AutoCAD 2023</option>
                            <option value="R2018">AutoCAD 2018 - 2022</option>
                            <option value="R2013">AutoCAD 2013</option>
                        </select>
                    </div>
                </div>

                <div class="mt-6 grid grid-cols-2 gap-4">
                    <button onclick="downloadCAD('DXF')" class="w-full py-3 bg-gray-700 hover:bg-gray-600 text-white font-bold rounded-lg transition-colors">Generate .DXF</button>
                    <button onclick="downloadCAD('DWG')" class="w-full py-3 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-lg transition-colors shadow-lg">Generate .DWG</button>
                </div>
                <div id="status-bar" class="mt-4 text-center text-sm font-semibold text-blue-500 hidden"></div>
            </div>

            <div class="bg-white dark:bg-gray-800 rounded-xl shadow-xl p-6 border border-gray-200 dark:border-gray-700">
                <h3 class="text-xl font-bold mb-4">Leave a Review</h3>
                <div class="space-y-4">
                    <div class="flex items-center justify-between">
                        <input type="text" id="rev-name" placeholder="Your Name" class="w-2/3 p-2 bg-gray-50 dark:bg-gray-700 border rounded-lg text-gray-900 dark:text-white">
                        <label class="flex items-center gap-2 text-sm">
                            <input type="checkbox" id="rev-anon" onchange="toggleAnon()"> Anonymous
                        </label>
                    </div>
                    <textarea id="rev-text" placeholder="Write your feedback..." rows="3" class="w-full p-2 bg-gray-50 dark:bg-gray-700 border rounded-lg text-gray-900 dark:text-white"></textarea>
                    <div>
                        <label class="block text-sm font-semibold mb-1">Attach Screenshot (Max 2MB)</label>
                        <input type="file" id="rev-file" accept="image/*" class="w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100">
                    </div>
                    <button onclick="submitReview()" class="w-full py-2 bg-green-600 hover:bg-green-500 text-white font-bold rounded-lg transition-colors">Post Review</button>
                </div>
            </div>
        </div>

        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-xl p-6 border border-gray-200 dark:border-gray-700">
            <div class="flex justify-between items-center mb-6">
                <h3 class="text-xl font-bold">Community Reviews</h3>
                <select id="sort-reviews" class="p-2 bg-gray-50 dark:bg-gray-700 border rounded-lg text-sm" onchange="loadReviews()">
                    <option value="newest">Newest First</option>
                    <option value="oldest">Oldest First</option>
                </select>
            </div>
            <div id="reviews-container" class="space-y-4"></div>
        </div>
    </div>

    <script>
        function toggleTheme() {
            const html = document.documentElement;
            html.classList.toggle('dark');
            html.classList.toggle('light');
            document.getElementById('theme-icon').innerText = html.classList.contains('dark') ? '☀️' : '🌙';
        }

        let currentFile = null;
        function handleFile(file) {
            currentFile = file;
            document.getElementById('drop-text').innerText = "Ready: " + file.name;
            if(!document.getElementById('filename').value) {
                document.getElementById('filename').value = file.name.split('.')[0];
            }
        }

        async function downloadCAD(formatType) {
            if(!currentFile) return alert("Upload an image first.");
            const statusBox = document.getElementById("status-bar");
            statusBox.classList.remove("hidden", "text-red-400", "text-green-400");
            statusBox.classList.add("text-blue-500", "animate-pulse");
            statusBox.innerText = `Auto-optimizing and building ${formatType}...`;

            const formData = new FormData();
            formData.append("file", currentFile);
            formData.append("filename", document.getElementById("filename").value || "drawing");
            formData.append("pagesize", document.getElementById("pagesize").value);
            formData.append("units", document.getElementById("units").value);
            formData.append("format", formatType);
            formData.append("version", document.getElementById("version").value);

            try {
                const response = await fetch("/convert", { method: "POST", body: formData });
                if(!response.ok) throw new Error((await response.json()).error);
                
                const blob = await response.blob();
                const a = document.createElement('a');
                a.href = window.URL.createObjectURL(blob);
                a.download = `${formData.get("filename")}.${formatType.toLowerCase()}`;
                a.click();
                
                statusBox.className = "mt-4 text-center text-sm font-semibold text-green-400";
                statusBox.innerText = "✅ Download Complete!";
            } catch(err) {
                statusBox.className = "mt-4 text-center text-sm font-semibold text-red-400";
                statusBox.innerText = "❌ Error: " + err.message;
            }
        }

        function toggleAnon() {
            const nameInput = document.getElementById('rev-name');
            if(document.getElementById('rev-anon').checked) {
                nameInput.value = "Anonymous";
                nameInput.disabled = true;
            } else {
                nameInput.value = "";
                nameInput.disabled = false;
            }
        }

        async function submitReview() {
            const name = document.getElementById('rev-name').value || "Anonymous";
            const text = document.getElementById('rev-text').value;
            const fileInput = document.getElementById('rev-file');
            
            if(!text) return alert("Please enter a review.");
            
            const formData = new FormData();
            formData.append("name", name);
            formData.append("review", text);
            
            if(fileInput.files.length > 0) {
                const file = fileInput.files[0];
                if(file.size > 2 * 1024 * 1024) return alert("Image must be smaller than 2MB.");
                formData.append("image", file);
            }

            try {
                await fetch("/reviews", { method: "POST", body: formData });
                document.getElementById('rev-text').value = "";
                fileInput.value = "";
                loadReviews();
            } catch(e) {
                alert("Failed to submit review.");
            }
        }

        async function loadReviews() {
            const sort = document.getElementById('sort-reviews').value;
            const res = await fetch(`/reviews?sort=${sort}`);
            const reviews = await res.json();
            
            const container = document.getElementById('reviews-container');
            container.innerHTML = "";
            
            reviews.forEach(r => {
                const date = new Date(r.timestamp).toLocaleString();
                let imgHtml = r.image_path ? `<img src="${r.image_path}" class="mt-3 max-h-48 rounded-lg border border-gray-600">` : '';
                container.innerHTML += `
                    <div class="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg border border-gray-200 dark:border-gray-600">
                        <div class="flex justify-between items-start mb-2">
                            <span class="font-bold text-blue-600 dark:text-blue-400">${r.name}</span>
                            <span class="text-xs text-gray-500 dark:text-gray-400">${date}</span>
                        </div>
                        <p class="text-gray-800 dark:text-gray-200">${r.review}</p>
                        ${imgHtml}
                    </div>
                `;
            });
        }
        window.onload = loadReviews;
    </script>
</body>
</html>
"""

@app.get("/")
def get_ui():
    return HTMLResponse(content=HTML_CONTENT)

@app.post("/reviews")
async def add_review(name: str = Form(...), review: str = Form(...), image: UploadFile = File(None)):
    img_path = None
    if image:
        ext = image.filename.split('.')[-1]
        filename = f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
        filepath = os.path.join("static_reviews", filename)
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
        img_path = f"/static/{filename}"
        
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO reviews (name, review, image_path, timestamp) VALUES (?, ?, ?, ?)",
              (name, review, img_path, datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.get("/reviews")
def get_reviews(sort: str = "newest"):
    order = "DESC" if sort == "newest" else "ASC"
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(f"SELECT * FROM reviews ORDER BY timestamp {order}")
    rows = [{"id": r[0], "name": r[1], "review": r[2], "image_path": r[3], "timestamp": r[4]} for r in c.fetchall()]
    conn.close()
    return JSONResponse(content=rows)

def run_potrace(input_bmp, output_dxf):
    res = subprocess.run(["potrace", input_bmp, "-b", "dxf", "-o", output_dxf], capture_output=True, text=True)
    if res.returncode != 0:
        raise Exception(f"Vectorizer failed: {res.stderr}")

@app.post("/convert")
async def convert(
    file: UploadFile = File(...),
    filename: str = Form("drawing"),
    pagesize: str = Form("A4"),
    units: str = Form("mm"),
    format: str = Form("DWG"),
    version: str = Form("R2018")
):
    temp_dir = tempfile.mkdtemp()
    
    try:
        image_bytes = await file.read()
        np_img = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_img, cv2.IMREAD_GRAYSCALE)
        img_h, img_w = img.shape[:2]
        
        ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        text_entities = []
        for i in range(len(ocr_data['text'])):
            word = ocr_data['text'][i].strip()
            if len(word) > 1:
                x, y, w, h = (ocr_data['left'][i], ocr_data['top'][i], ocr_data['width'][i], ocr_data['height'][i])
                
                # Correct Y-axis coordinate inversion mapping OpenCV top-left origin to AutoCAD bottom-left origin
                cad_y = img_h - (y + h)
                text_entities.append({"text": word, "x": x, "y": cad_y, "h": h})
                
                cv2.rectangle(img, (x-2, y-2), (x+w+2, y+h+2), (255, 255, 255), -1)

        _, bin_img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        kernel = np.ones((3,3), np.uint8)
        thick_lines_img = cv2.erode(bin_img, kernel, iterations=1)
        thin_lines_img = cv2.subtract(bin_img, thick_lines_img)
        
        thick_bmp = os.path.join(temp_dir, "thick.bmp")
        thin_bmp = os.path.join(temp_dir, "thin.bmp")
        cv2.imwrite(thick_bmp, cv2.bitwise_not(thick_lines_img))
        cv2.imwrite(thin_bmp, cv2.bitwise_not(thin_lines_img))
        
        thick_dxf = os.path.join(temp_dir, "thick.dxf")
        thin_dxf = os.path.join(temp_dir, "thin.dxf")
        run_potrace(thick_bmp, thick_dxf)
        run_potrace(thin_bmp, thin_dxf)
        
        # Build Master CAD Document with neutral default colors (7)
        master_doc = ezdxf.new(dxfversion='R2010')
        master_doc.layers.add("THICK_LINES", color=7)
        master_doc.layers.add("THIN_LINES", color=7)
        master_doc.layers.add("OCR_TEXT", color=7)
        
        # Safely import entities to prevent NoneType object errors
        for d_path, layer_name in [(thick_dxf, "THICK_LINES"), (thin_dxf, "THIN_LINES")]:
            if not os.path.exists(d_path): continue
            temp_doc = ezdxf.readfile(d_path)
            for entity in temp_doc.modelspace():
                entity.dxf.layer = layer_name
            importer = Importer(temp_doc, master_doc)
            importer.import_modelspace()
            importer.finalize()

        msp = master_doc.modelspace()
        
        for t in text_entities:
            msp.add_text(t["text"], dxfattribs={'layer': 'OCR_TEXT', 'height': t["h"]}).set_placement((t["x"], t["y"]))

        if pagesize != "ORIGINAL":
            target_w = 297 if pagesize == "A4" else 420
            if units == "cm": target_w /= 10
            elif units == "in": target_w /= 25.4
            
            scale_factor = target_w / img_w
            
            # Corrected Matrix Scaling: Z must be 1.0, not 0
            transform_matrix = Matrix44.scale(scale_factor, scale_factor, 1.0)
            for entity in msp:
                if hasattr(entity, 'transform'):
                    entity.transform(transform_matrix)
                
        master_dxf_path = os.path.join(temp_dir, "final.dxf")
        master_doc.saveas(master_dxf_path)
        
        if format.upper() == "DXF":
            return FileResponse(master_dxf_path, filename=f"{filename}.dxf", background=BackgroundTask(shutil.rmtree, temp_dir))
        else:
            dwg_path = os.path.join(temp_dir, "compiled.dwg")
            try:
                odafc.export_dwg(master_doc, dwg_path, version=version)
            except Exception as e:
                if not os.path.exists(dwg_path): raise Exception(f"ODA Engine Failed: {str(e)}")
            
            if os.path.exists(dwg_path):
                return FileResponse(dwg_path, filename=f"{filename}.dwg", background=BackgroundTask(shutil.rmtree, temp_dir))
            else:
                raise Exception("DWG not generated.")

    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return JSONResponse(status_code=500, content={"error": str(e)})
