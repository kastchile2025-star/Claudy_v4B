import { spawn, execSync } from 'child_process';
import chalk from 'chalk';
import { OpenCodeClient } from './opencode.js';
import { Config } from './types.js';

/**
 * Verifica si el servidor OpenCode está respondiendo.
 * Si no, intenta iniciarlo automáticamente.
 */
export async function ensureOpencodeRunning(config: Config['opencode']): Promise<boolean> {
  const client = new OpenCodeClient(config);

  // 1. Verificar si ya está corriendo
  if (await client.testConnection()) {
    return true;
  }

  console.log(chalk.yellow('⚠ OpenCode no está respondiendo. Intentando iniciar automáticamente...'));

  // 2. Intentar iniciar opencode serve
  try {
    const port = new URL(config.baseUrl).port || '4096';
    const hostname = new URL(config.baseUrl).hostname || '127.0.0.1';

    const child = spawn('opencode', ['serve', '--port', port, '--hostname', hostname], {
      stdio: 'ignore',
      detached: true,
    });

    child.unref(); // Dejar que el proceso viva independientemente

    console.log(chalk.cyan('🔄 Iniciando opencode serve en segundo plano...'));

    // 3. Esperar hasta 15 segundos a que responda
    const maxWait = 15_000;
    const pollInterval = 500;
    const start = Date.now();

    while (Date.now() - start < maxWait) {
      await new Promise((r) => setTimeout(r, pollInterval));
      if (await client.testConnection()) {
        console.log(chalk.green('✓ OpenCode iniciado correctamente.'));
        return true;
      }
    }

    console.log(chalk.red('✗ No se pudo iniciar OpenCode automáticamente.'));
    console.log(chalk.gray('  Inicia manualmente: opencode serve --port 4096 --hostname 127.0.0.1'));
    return false;
  } catch (error) {
    console.log(chalk.red('✗ Error al iniciar OpenCode:'));
    console.log(chalk.gray(`  ${error instanceof Error ? error.message : String(error)}`));
    console.log(chalk.gray('  Inicia manualmente: opencode serve --port 4096 --hostname 127.0.0.1'));
    return false;
  }
}
