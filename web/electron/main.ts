import { app, BrowserWindow, screen, ipcMain, globalShortcut } from 'electron';
import path from 'path';
import fs from 'fs';
import { spawn, ChildProcess } from 'child_process';
import http from 'http';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

process.env['ELECTRON_DISABLE_SECURITY_WARNINGS'] = 'true';

// Ensure crisp rendering on HiDPI / Retina displays
app.commandLine.appendSwitch('high-dpi-support', '1');
app.commandLine.appendSwitch('force-device-scale-factor', '0'); // Let OS handle it natively

// Suppress internal Chromium sandbox/macOS CoreServices noise (SetApplicationIsDaemon paramErr -50)
app.commandLine.appendSwitch('log-level', '3'); // Log fatal errors only
app.commandLine.appendSwitch('disable-logging');

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
  const primaryDisplay = screen.getPrimaryDisplay();
  const workArea = primaryDisplay.workArea;
  
  const winW = 440;
  const winH = 540;
  // Position with comfortable margin from bottom-right, safely above Dock
  const posX = Math.max(0, Math.round(workArea.x + workArea.width - winW - 16));
  const posY = Math.max(0, Math.round(workArea.y + workArea.height - winH - 16));
  
  mainWindow = new BrowserWindow({
    width: winW,
    height: winH,
    x: posX,
    y: posY,
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

  // Ensure window is visible on all macOS workspaces / spaces
  if (process.platform === 'darwin') {
    mainWindow.setVisibleOnAllWorkspaces(true, { visibleOnAllWorkspaces: true });
    mainWindow.setAlwaysOnTop(true, 'floating');
  }

  // Load the Vite dev server URL or the built index.html
  if (process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }

  // Show window reliably
  mainWindow.once('ready-to-show', () => {
    mainWindow?.show();
    mainWindow?.focus();
  });

  // Forward renderer console logs to terminal
  mainWindow.webContents.on('console-message', (event: any) => {
    const msg = event?.message ?? event;
    if (msg) console.log(`[UI]: ${msg}`);
  });
}

function startPythonBackend(): Promise<void> {
  return new Promise((resolve, reject) => {
    // Check if backend is already running first
    const probe = http.get('http://localhost:8000/api/health', (res) => {
      if (res.statusCode === 200) {
        console.log("Python backend is already running on port 8000.");
        return resolve();
      }
      doSpawn();
    });
    probe.on('error', () => {
      doSpawn();
    });

    function doSpawn() {
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
        const rootDir = path.resolve(__dirname, '../../');
        const venvMac = path.join(rootDir, '.venv', 'bin', 'python');
        const venvWin = path.join(rootDir, '.venv', 'Scripts', 'python.exe');
        let pyExe = 'python3';
        if (process.platform === 'win32') {
          pyExe = fs.existsSync(venvWin) ? venvWin : 'python';
        } else {
          pyExe = fs.existsSync(venvMac) ? venvMac : 'python3';
        }
        console.log(`[Electron] Spawning python using: ${pyExe}`);
        pythonProcess = spawn(pyExe, ['main.py'], {
          cwd: rootDir,
          env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
        });
      }

      pythonProcess.stdout?.on('data', (data) => {
        console.log(`[Python]: ${data.toString()}`);
      });

      pythonProcess.stderr?.on('data', (data) => {
        console.error(`[Python ERROR]: ${data.toString()}`);
      });

      let isReady = false;
      const checkHealth = setInterval(() => {
        if (isReady) return;
        const req = http.get('http://localhost:8000/api/health', (res) => {
          if (!isReady && res.statusCode === 200) {
            isReady = true;
            clearInterval(checkHealth);
            clearTimeout(timeoutId);
            console.log("Python backend is ready!");
            resolve();
          }
        });
        req.on('error', () => {
          // Backend not ready yet
        });
      }, 500);

      // Timeout after 30 seconds
      const timeoutId = setTimeout(() => {
        if (!isReady) {
          clearInterval(checkHealth);
          reject(new Error("Python backend took too long to start"));
        }
      }, 30000);
    }
  });
}

app.whenReady().then(async () => {
  try {
    await startPythonBackend();
  } catch (err) {
    console.error("Failed to start Python, continuing anyway...", err);
  }
  createWindow();

  // Register global hands-free hotkeys (Ctrl+Space or Option+Space to talk / interrupt)
  const triggerListen = () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('hotkey-listen');
    }
  };
  globalShortcut.register('CommandOrControl+Space', triggerListen);
  globalShortcut.register('Alt+Space', triggerListen);

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

// Kill the python process cleanly when the app exits
function killPythonProcess() {
  if (pythonProcess && pythonProcess.pid) {
    console.log("Killing Python background process...");
    try {
      if (process.platform === 'win32') {
        const killer = spawn('taskkill', ['/pid', pythonProcess.pid.toString(), '/f', '/t']);
        killer.on('error', (err) => {
          console.error("Failed to execute taskkill on Windows:", err.message);
        });
      } else {
        pythonProcess.kill('SIGKILL');
      }
    } catch (err) {
      console.error("Failed to kill Python process:", err);
    }
    pythonProcess = null;
  }
}

app.on('will-quit', () => {
  globalShortcut.unregisterAll();
  killPythonProcess();
});

process.on('exit', () => {
  killPythonProcess();
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

