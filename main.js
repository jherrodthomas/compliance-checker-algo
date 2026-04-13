/**
 * Lion of Functional Safety Engine™ — Electron Main Process
 *
 * Spawns the bundled PyInstaller binary (iso26262_checker) as a child process,
 * pipes stdout for real-time progress, and loads the generated HTML report
 * into a BrowserWindow when complete.
 */

const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');

let mainWindow = null;
let analysisProcess = null;

// Resolve the path to the bundled engine executable
function getEnginePath() {
  const isDev = !app.isPackaged;
  if (isDev) {
    // Development: look for the PyInstaller output in ./engine/
    const ext = process.platform === 'win32' ? '.exe' : '';
    return path.join(__dirname, 'engine', `iso26262_checker${ext}`);
  } else {
    // Production: extraResources places it alongside the app
    const ext = process.platform === 'win32' ? '.exe' : '';
    return path.join(process.resourcesPath, 'engine', `iso26262_checker${ext}`);
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    title: 'Lion of Functional Safety Engine™',
    backgroundColor: '#0a1628',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      webviewTag: true   // for inline report viewing
    },
    // Frameless with custom titlebar for a polished look
    // titleBarStyle: 'hiddenInset',  // uncomment on macOS for sleek look
    show: false
  });

  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
    if (analysisProcess) {
      analysisProcess.kill();
      analysisProcess = null;
    }
  });
}

// --- IPC Handlers ---

// Open native folder picker
ipcMain.handle('select-folder', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: 'Select Work Products Folder',
    properties: ['openDirectory'],
    buttonLabel: 'Analyze This Folder'
  });
  if (result.canceled) return null;
  return result.filePaths[0];
});

// List files in a directory (for preview)
ipcMain.handle('list-folder', async (event, folderPath) => {
  try {
    const entries = fs.readdirSync(folderPath, { withFileTypes: true });
    const files = entries
      .filter(e => e.isFile())
      .map(e => ({
        name: e.name,
        ext: path.extname(e.name).toLowerCase(),
        size: fs.statSync(path.join(folderPath, e.name)).size
      }))
      .filter(f => ['.docx', '.xlsx', '.pdf', '.odt', '.md', '.txt', '.json'].includes(f.ext));
    return { ok: true, files };
  } catch (err) {
    return { ok: false, error: err.message };
  }
});

// Run the ISO 26262 analysis
ipcMain.handle('run-analysis', async (event, folderPath, reportFormat) => {
  return new Promise((resolve) => {
    const enginePath = getEnginePath();
    const format = reportFormat || 'html';  // default to html

    // Check engine exists
    if (!fs.existsSync(enginePath)) {
      resolve({
        ok: false,
        error: `Engine binary not found at: ${enginePath}\n\nPlease run the PyInstaller build first:\n  pyinstaller --onefile --name iso26262_checker --distpath ./engine ./ISO26262_Checker.py`
      });
      return;
    }

    // Create reports output dir inside the target folder
    const reportsDir = path.join(folderPath, 'reports');
    if (!fs.existsSync(reportsDir)) {
      fs.mkdirSync(reportsDir, { recursive: true });
    }

    // Build engine arguments — pass format flag
    const engineArgs = [folderPath];
    if (format === 'docx') {
      engineArgs.push('--format', 'docx');
    } else if (format === 'both') {
      engineArgs.push('--format', 'both');
    } else {
      engineArgs.push('--format', 'html');
    }

    // Spawn the engine
    analysisProcess = spawn(enginePath, engineArgs, {
      cwd: folderPath,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUTF8: '1' }
    });

    let stdout = '';
    let stderr = '';

    analysisProcess.stdout.on('data', (data) => {
      const text = data.toString();
      stdout += text;
      // Forward progress lines to renderer
      mainWindow?.webContents.send('analysis-progress', text);
    });

    analysisProcess.stderr.on('data', (data) => {
      stderr += data.toString();
      mainWindow?.webContents.send('analysis-progress', data.toString());
    });

    analysisProcess.on('close', (code) => {
      analysisProcess = null;

      // Helper: find newest file by extension in a directory
      function findNewest(dir, ext, nameFilter) {
        if (!fs.existsSync(dir)) return null;
        try {
          const files = fs.readdirSync(dir)
            .filter(f => f.endsWith(ext) && (!nameFilter || f.includes(nameFilter)))
            .sort((a, b) => {
              return fs.statSync(path.join(dir, b)).mtimeMs -
                     fs.statSync(path.join(dir, a)).mtimeMs;
            });
          return files.length > 0 ? path.join(dir, files[0]) : null;
        } catch (e) { return null; }
      }

      // Parse stdout for report filenames the engine printed
      function parseReportFromStdout(ext) {
        const regex = new RegExp(`(ISO26262_compliance_[\\w-]+\\.${ext})`, 'i');
        const match = stdout.match(regex);
        if (match) {
          // Check in reports/ subfolder first, then root
          const inReports = path.join(reportsDir, match[1]);
          if (fs.existsSync(inReports)) return inReports;
          const inRoot = path.join(folderPath, match[1]);
          if (fs.existsSync(inRoot)) return inRoot;
        }
        return null;
      }

      // Find HTML report — check reports/, root folder, and parse stdout
      let htmlReport = findNewest(reportsDir, '.html') ||
                       findNewest(folderPath, '.html', 'compliance') ||
                       parseReportFromStdout('html');

      // Find DOCX report
      let docxReport = findNewest(reportsDir, '.docx') ||
                       findNewest(folderPath, '.docx', 'compliance') ||
                       parseReportFromStdout('docx');

      resolve({
        ok: code === 0,
        code,
        htmlReport,
        docxReport,
        reportFormat: format,
        stdout,
        stderr,
        reportsDir
      });
    });

    analysisProcess.on('error', (err) => {
      analysisProcess = null;
      resolve({ ok: false, error: err.message });
    });
  });
});

// Cancel a running analysis
ipcMain.handle('cancel-analysis', async () => {
  if (analysisProcess) {
    analysisProcess.kill();
    analysisProcess = null;
    return true;
  }
  return false;
});

// Open a file in the default system app
ipcMain.handle('open-external', async (event, filePath) => {
  shell.openPath(filePath);
});

// Open folder in system file explorer
ipcMain.handle('open-folder', async (event, folderPath) => {
  shell.showItemInFolder(folderPath);
});

// Read an HTML file (for inline report viewing)
ipcMain.handle('read-html-file', async (event, filePath) => {
  try {
    return { ok: true, content: fs.readFileSync(filePath, 'utf8') };
  } catch (err) {
    return { ok: false, error: err.message };
  }
});

// Check engine availability
ipcMain.handle('check-engine', async () => {
  const enginePath = getEnginePath();
  return {
    exists: fs.existsSync(enginePath),
    path: enginePath
  };
});

// --- App Lifecycle ---

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
