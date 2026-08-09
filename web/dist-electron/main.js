import { BrowserWindow, app, globalShortcut, ipcMain, screen } from "electron";
import path from "path";
import { spawn } from "child_process";
import http from "http";
import { fileURLToPath } from "url";
//#region electron/main.ts
var __filename = fileURLToPath(import.meta.url);
var __dirname = path.dirname(__filename);
var mainWindow = null;
var pythonProcess = null;
ipcMain.on("get-window-pos", (event) => {
	if (mainWindow) event.returnValue = mainWindow.getPosition();
	else event.returnValue = [0, 0];
});
ipcMain.on("set-window-pos", (event, x, y) => {
	if (mainWindow) mainWindow.setPosition(x, y);
});
function createWindow() {
	const { width, height } = screen.getPrimaryDisplay().workAreaSize;
	mainWindow = new BrowserWindow({
		width: 350,
		height: 500,
		x: width - 350,
		y: height - 500,
		transparent: true,
		frame: false,
		hasShadow: false,
		alwaysOnTop: true,
		resizable: false,
		webPreferences: {
			nodeIntegration: true,
			contextIsolation: false
		}
	});
	if (process.env.VITE_DEV_SERVER_URL) mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
	else mainWindow.loadFile(path.join(__dirname, "../dist/index.html"));
	mainWindow.on("ready-to-show", () => {
		mainWindow?.show();
	});
}
function startPythonBackend() {
	return new Promise((resolve, reject) => {
		console.log("Starting Python backend...");
		pythonProcess = spawn("python", ["main.py"], {
			cwd: path.join(__dirname, "../../"),
			env: {
				...process.env,
				PYTHONIOENCODING: "utf-8"
			}
		});
		pythonProcess.stdout?.on("data", (data) => {
			console.log(`[Python]: ${data.toString()}`);
		});
		pythonProcess.stderr?.on("data", (data) => {
			console.error(`[Python ERROR]: ${data.toString()}`);
		});
		const checkHealth = setInterval(() => {
			http.get("http://localhost:8000/api/health", (res) => {
				if (res.statusCode === 200) {
					clearInterval(checkHealth);
					console.log("Python backend is ready!");
					resolve();
				}
			}).on("error", () => {});
		}, 500);
		setTimeout(() => {
			clearInterval(checkHealth);
			reject(/* @__PURE__ */ new Error("Python backend took too long to start"));
		}, 15e3);
	});
}
app.whenReady().then(async () => {
	try {
		await startPythonBackend();
	} catch (err) {
		console.error("Failed to start Python, continuing anyway...", err);
	}
	createWindow();
	globalShortcut.register("CommandOrControl+Space", () => {
		if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send("hotkey-listen");
	});
});
app.on("window-all-closed", () => {
	if (process.platform !== "darwin") app.quit();
});
app.on("will-quit", () => {
	globalShortcut.unregisterAll();
	if (pythonProcess) {
		console.log("Killing Python background process...");
		spawn("taskkill", [
			"/pid",
			pythonProcess.pid.toString(),
			"/f",
			"/t"
		]);
	}
});
app.on("activate", () => {
	if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
setInterval(() => {
	if (mainWindow && !mainWindow.isDestroyed()) {
		const point = screen.getCursorScreenPoint();
		mainWindow.webContents.send("cursor-pos", point.x, point.y);
	}
}, 1e3 / 30);
//#endregion
export {};
