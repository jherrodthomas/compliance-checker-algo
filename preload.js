/**
 * Lion of Functional Safety Engine™ — Preload Bridge
 *
 * Exposes a safe, scoped API to the renderer process via contextBridge.
 * No raw Node.js or Electron APIs leak into the browser context.
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('lion', {
  // Folder operations
  selectFolder: () => ipcRenderer.invoke('select-folder'),
  listFolder: (path) => ipcRenderer.invoke('list-folder', path),

  // Analysis
  runAnalysis: (folderPath, format) => ipcRenderer.invoke('run-analysis', folderPath, format),
  cancelAnalysis: () => ipcRenderer.invoke('cancel-analysis'),
  onProgress: (callback) => {
    const handler = (_event, data) => callback(data);
    ipcRenderer.on('analysis-progress', handler);
    // Return cleanup function
    return () => ipcRenderer.removeListener('analysis-progress', handler);
  },

  // Report viewing
  readHtmlFile: (path) => ipcRenderer.invoke('read-html-file', path),

  // System
  openExternal: (path) => ipcRenderer.invoke('open-external', path),
  openFolder: (path) => ipcRenderer.invoke('open-folder', path),
  checkEngine: () => ipcRenderer.invoke('check-engine'),

  // Platform info
  platform: process.platform
});
