import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { rememberProfile, getMemoryStats } from "../backend/src/memory";

const targetDir = "G:\\Mi unidad\\QCORE-ECOSYSTEM";

function walk(dir: string, fileList: string[] = []) {
  try {
    const files = readdirSync(dir);
    for (const file of files) {
      const filePath = join(dir, file);
      try {
        if (statSync(filePath).isDirectory()) {
          // Excluir carpetas ocultas pesadas
          if (!file.startsWith(".") && file !== "node_modules" && file !== ".venv") {
            walk(filePath, fileList);
          }
        } else {
          if (file.endsWith(".md") || file.endsWith(".txt")) {
            fileList.push(filePath);
          }
        }
      } catch (e) {
        // Ignorar
      }
    }
  } catch (e) {
    // Ignorar
  }
  return fileList;
}

console.log(`Buscando archivos en ${targetDir}...`);
const files = walk(targetDir);
console.log(`Se encontraron ${files.length} archivos .md/.txt. Ingestando...`);

let count = 0;

for (const file of files) {
  try {
    const content = readFileSync(file, "utf8");
    const fileName = file.split("\\").pop() || file.split("/").pop();
    
    if (content.length > 50) {
      const paragraphs = content.split(/\n\n+/).filter(c => c.trim().length > 30);
      
      let currentChunk = "";
      for (const p of paragraphs) {
        if (currentChunk.length + p.length > 800) {
          try {
            rememberProfile(`[Fuente: ${fileName}] ${currentChunk.trim()}`.slice(0, 1000));
            count++;
          } catch(e) {}
          currentChunk = p;
        } else {
          currentChunk += "\n\n" + p;
        }
      }
      if (currentChunk.trim().length > 0) {
         try {
           rememberProfile(`[Fuente: ${fileName}] ${currentChunk.trim()}`.slice(0, 1000));
           count++;
         } catch(e) {}
      }
    }
  } catch (e) {
    console.error(`Error leyendo ${file}`);
  }
}

console.log(`\n¡Ingestión completada con éxito!`);
console.log(`Fragmentos absorbidos en la memoria: ${count}`);
console.log("Estado actual de la memoria vectorial:", getMemoryStats());
