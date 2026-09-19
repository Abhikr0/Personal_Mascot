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

// Forward mouse events or make transparent window click-through
ipcMain.on('set-ignore-mouse-events', (event, ignore: boolean, options?: any) => {
  const win = BrowserWindow.fromWebContents(event.sender) || mainWindow;
  if (win && !win.isDestroyed()) {
    try {
      if (ignore) {
        win.setIgnoreMouseEvents(true, options || { forward: true });
      } else {
        win.setIgnoreMouseEvents(false);
      }
    } catch {}
  }
});


function createWindow() {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;
  
  mainWindow = new BrowserWindow({
    width: 440,
    height: 540,
    x: width - 440, // Put her in the bottom right corner by default
    y: height - 540,
    transparent: true,
    frame: false,
    hasShadow: false,
    alwaysOnTop: true,
    resizable: false, // Locked to prevent accidental scaling and resize events during drag
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      webSecurity: false,
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
    
    if (app.isPackaged) {
      const backendPath = path.join(process.resourcesPath, 'backend.exe');
      const exeDir = path.dirname(process.execPath); // This is where Friday.exe is located
      console.log("Spawning compiled backend from: ", backendPath, "with cwd:", exeDir);
      pythonProcess = spawn(backendPath, [], {
        cwd: exeDir,
        env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
      });
    } else {
      // Spawn python from the parent directory with UTF-8 encoding
      pythonProcess = spawn('python', ['main.py'], {
        cwd: path.join(__dirname, '../../'), // We are inside web/dist-electron (or web/), so go up one level to Friday2.0
        env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
      });
    }

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

  // Register global hands-free hotkey (Ctrl+Space to talk / interrupt)
  globalShortcut.register('CommandOrControl+Space', () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('hotkey-listen');
    }
  });

  // Register global hotkey to toggle Always-On / Wake Word mode (Ctrl+Shift+A)
  globalShortcut.register('CommandOrControl+Shift+A', () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('hotkey-toggle-always-on');
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

// Broadcast window-relative cursor position at 60FPS for flawless desktop-wide tracking
let lastCursorX = -99999;
let lastCursorY = -99999;

setInterval(() => {
  if (mainWindow && !mainWindow.isDestroyed()) {
    try {
      const point = screen.getCursorScreenPoint();
      const [winX, winY] = mainWindow.getPosition();
      const relX = Math.round(point.x - winX);
      const relY = Math.round(point.y - winY);
      if (relX !== lastCursorX || relY !== lastCursorY) {
        lastCursorX = relX;
        lastCursorY = relY;
        mainWindow.webContents.send('cursor-pos', relX, relY);
      }
    } catch {}
  }
}, 1000 / 60);

