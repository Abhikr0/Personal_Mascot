import { app, BrowserWindow, screen, ipcMain, globalShortcut } from 'electron';
import path from 'path';
import { spawn, ChildProcess } from 'child_process';
import http from 'http';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

let mainWindow: BrowserWindow | null = null;
let pythonProcess: ChildProcess | null = null;

// Allow the renderer to ask for its position and set its position natively to bypass Chromium monitor clamping
ipcMain.on('get-window-pos', (event) => {
  if (mainWindow) {
    event.returnValue = mainWindow.getPosition();
  } else {
    event.returnValue = [0, 0];
  }
});

ipcMain.on('set-window-pos', (event, x, y) => {
  if (mainWindow) {
    mainWindow.setPosition(x, y);
  }
});

function createWindow() {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;
  
  mainWindow = new BrowserWindow({
    width: 350,
    height: 500,
    x: width - 350, // Put her in the bottom right corner by default
    y: height - 500,
    transparent: true,
    frame: false,
    hasShadow: false,
    alwaysOnTop: true,
    resizable: false, // Locked to prevent accidental scaling and resize events during drag
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
    },
  });

  // Load the Vite dev server URL or the built index.html
  if (process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }

  // Prevent white flashes on load
  mainWindow.on('ready-to-show', () => {
    mainWindow?.show();
  });
}

function startPythonBackend(): Promise<void> {
  return new Promise((resolve, reject) => {
    console.log("Starting Python backend...");
    
    // Spawn python from the parent directory with UTF-8 encoding
    pythonProcess = spawn('python', ['main.py'], {
      cwd: path.join(__dirname, '../../'), // We are inside web/dist-electron (or web/), so go up one level to Friday2.0
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
    });

    pythonProcess.stdout?.on('data', (data) => {
      console.log(`[Python]: ${data.toString()}`);
    });

    pythonProcess.stderr?.on('data', (data) => {
      console.error(`[Python ERROR]: ${data.toString()}`);
    });

    // Ping the health endpoint to wait for it to boot up
    const checkHealth = setInterval(() => {
      http.get('http://localhost:8000/api/health', (res) => {
        if (res.statusCode === 200) {
          clearInterval(checkHealth);
          console.log("Python backend is ready!");
          resolve();
        }
      }).on('error', () => {
        // Backend not ready yet
      });
    }, 500);

    // Timeout after 15 seconds
    setTimeout(() => {
      clearInterval(checkHealth);
      reject(new Error("Python backend took too long to start"));
    }, 15000);
  });
}

app.whenReady().then(async () => {
  try {
    await startPythonBackend();
  } catch (err) {
    console.error("Failed to start Python, continuing anyway...", err);
  }
  createWindow();

  // Register global hands-free hotkey
  globalShortcut.register('CommandOrControl+Space', () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('hotkey-listen');
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// Kill the python process violently when the app exits
app.on('will-quit', () => {
  globalShortcut.unregisterAll();
  if (pythonProcess) {
    console.log("Killing Python background process...");
    // Force kill on Windows
    spawn('taskkill', ['/pid', pythonProcess.pid!.toString(), '/f', '/t']);
  }
});

// Keep exactly one instance of activate handler
app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

// Broadcast global cursor position to the renderer for smooth 30FPS outside-window tracking
setInterval(() => {
  if (mainWindow && !mainWindow.isDestroyed()) {
    const point = screen.getCursorScreenPoint();
    mainWindow.webContents.send('cursor-pos', point.x, point.y);
  }
}, 1000 / 30);
