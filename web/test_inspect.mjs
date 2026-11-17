
import electron from "electron";
const { app, BrowserWindow } = electron;
app.whenReady().then(async () => {
  const win = new BrowserWindow({ show: false, webPreferences: { nodeIntegration: true, contextIsolation: false } });
  win.webContents.on("console-message", (event) => {
    console.log("[CONSOLE]:", event.message);
  });
  await win.loadURL("http://localhost:5173");
  setTimeout(async () => {
    const res = await win.webContents.executeJavaScript(`
      JSON.stringify({
        root: !!document.getElementById("root"),
        canvas: !!document.querySelector("canvas"),
        errorContainer: !!document.querySelector(".error-container"),
        errorText: document.querySelector(".error-message")?.textContent || null,
        loadingHidden: document.querySelector(".loading-container")?.classList.contains("hidden"),
        bodyHTML: document.body.innerHTML.substring(0, 500)
      })
    `);
    console.log("[INSPECTION RESULT]:", res);
    app.exit(0);
  }, 4000);
});
