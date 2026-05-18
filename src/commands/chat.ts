import { Command } from 'commander';
import inquirer from 'inquirer';
import chalk from 'chalk';
import * as readline from 'readline/promises';
import { marked } from 'marked';
// @ts-ignore — marked-terminal no tiene tipos oficiales
import TerminalRenderer from 'marked-terminal';
import { loadConfig } from '../config.js';
import { OpenCodeClient } from '../opencode.js';
import { ensureOpencodeRunning } from '../opencode-ensure.js';
import { toolRead, toolWrite, toolExec } from '../tools.js';
import {
  findRelevantSkills,
  buildSkillsContext,
  listSkills,
  installSkillFromUrl,
  findSkillUrls,
  installBestSkillForQuery,
  parseSkillIntent,
  searchRemoteSkills,
} from '../skills.js';
import {
  shouldSearchWeb,
  searchWeb,
  formatSearchContext,
  extractSearchQuery,
} from '../websearch.js';
import {
  addMemory,
  searchMemories,
  listMemories,
  deleteMemory,
  archiveOldMemories,
} from '../memory.js';
import {
  downloadFile,
  searchFilesOnline,
  executeFile,
  parseFileIntent,
  installApp,
} from '../fileops.js';
import {
  createSession,
  saveSession,
  loadSession,
  addMessage,
  listSessions,
  needsSummarization,
  buildSummarizationPrompt,
  compactSession,
} from '../utils.js';
import { exportChat, getSupportedFormats, ExportFormat } from '../export.js';
import { searchSessions, formatSearchResults } from '../session-search.js';
import { Session, Config } from '../types.js';

export const chatCommand = new Command('chat')
  .description('Iniciar sesión de chat interactivo')
  .option('-s, --session <id>', 'Continuar una sesión existente')
  .option('-m, --model <model>', 'Modelo a utilizar')
  .option('-n, --new', 'Crear nueva sesión sin preguntar')
  .action(async (options) => {
    const config = loadConfig();

    // Auto-start opencode if not running
    const opencodeReady = await ensureOpencodeRunning(config.opencode);
    if (!opencodeReady) {
      console.log(chalk.red('✗ No se pudo conectar a OpenCode. Saliendo.'));
      process.exit(1);
    }

    let session: Session;

    if (options.session) {
      const loaded = loadSession(options.session);
      if (!loaded) {
        console.log(chalk.red(`✗ Sesión "${options.session}" no encontrada.`));
        process.exit(1);
      }
      session = loaded;
      console.log(chalk.cyan(`\n📂 Continuando sesión: ${session.name}`));
    } else if (!options.new) {
      const existing = listSessions();
      if (existing.length > 0) {
        const { action } = await inquirer.prompt([
          {
            type: 'list',
            name: 'action',
            message: '¿Qué deseas hacer?',
            choices: [
              { name: 'Nueva sesión', value: 'new' },
              ...existing.slice(0, 10).map((s) => ({
                name: `Continuar: ${s.name} (${s.messages.length} mensajes)`,
                value: s.id,
              })),
            ],
          },
        ]);

        if (action === 'new') {
          session = await createNewSession(options.model || config.opencode.defaultModel);
        } else {
          session = loadSession(action)!;
          console.log(chalk.cyan(`\n📂 Continuando sesión: ${session.name}`));
        }
      } else {
        session = await createNewSession(options.model || config.opencode.defaultModel);
      }
    } else {
      session = await createNewSession(options.model || config.opencode.defaultModel);
    }

    const client = new OpenCodeClient(config.opencode);

    console.log(chalk.gray('\n─────────────────────────────────────────'));
    console.log(chalk.gray(`Modelo: ${session.model}`));
    console.log(chalk.gray(`Sesión: ${session.id.substring(0, 8)}...`));
    console.log(chalk.gray(`OpenCode: ${config.opencode.baseUrl}`));
    console.log(
      chalk.gray(
        `Tools: read=${config.tools.allowRead ? '✓' : '✗'} write=${
          config.tools.allowWrite ? '✓' : '✗'
        } exec=${config.tools.allowExec ? '✓' : '✗'}`
      )
    );
    const installedSkills = listSkills();
    if (installedSkills.length > 0) {
      console.log(
        chalk.gray(
          `Skills: ${installedSkills.map((s) => s.name).join(', ')}`
        )
      );
    }
    console.log(
      chalk.gray(
        'Comandos: /exit /clear /save /model /read /write /exec /skills /find-skill /install-skill /search /export /help'
      )
    );
    console.log(chalk.gray('─────────────────────────────────────────\n'));

    if (session.messages.length > 0) {
      session.messages.forEach((msg) => {
        if (msg.role === 'user') {
          console.log(chalk.green('You: ') + msg.content);
        } else {
          console.log(chalk.blue('Claudy: ') + msg.content + '\n');
        }
      });
    }

    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
    });

    // Track streaming state for Ctrl+C cancellation
    let isStreaming = false;
    let streamController: AbortController | null = null;

    // Ctrl+C: cancel stream if active, exit if not
    rl.on('SIGINT', () => {
      if (isStreaming && streamController) {
        // Cancel the ongoing stream
        streamController.abort();
        isStreaming = false;
        process.stdout.write('\n');
        console.log(chalk.yellow('⚠ Respuesta interrumpida por el usuario'));
      } else {
        saveSession(session);
        console.log(chalk.gray('\n👋 Sesión guardada. ¡Hasta luego!\n'));
        rl.close();
        process.exit(0);
      }
    });

    while (true) {
      let userInput: string;
      try {
        userInput = (await rl.question(chalk.green('You: '))).trim();
      } catch {
        // readline cerrado externamente
        break;
      }

      if (!userInput) continue;

      if (userInput.startsWith('/')) {
        if (userInput.startsWith('/find-skill ')) {
          const query = userInput.slice('/find-skill '.length).trim();
          await handleFindSkill(query, session);
          continue;
        }

        if (userInput.startsWith('/install-skill ')) {
          const query = userInput.slice('/install-skill '.length).trim();
          await handleInstallSkill(query, session);
          continue;
        }

        const result = await handleCommand(userInput, session, config);
        if (result === 'exit') break;
        continue;
      }

      const skillIntent = parseSkillIntent(userInput);
      if (skillIntent) {
        addMessage(session, 'user', userInput);
        if (skillIntent.action === 'install') {
          await handleInstallSkill(skillIntent.query, session);
        } else {
          await handleFindSkill(skillIntent.query, session);
        }
        continue;
      }

      // ── File intent routing: download, search-download, execute ──
      const fileIntent = parseFileIntent(userInput);
      if (fileIntent) {
        addMessage(session, 'user', userInput);
        if (fileIntent.action === 'download') {
          console.log(chalk.cyan(`⬇ Descargando: ${fileIntent.target}`));
          const dlResult = await downloadFile(fileIntent.target);
          if (dlResult.ok) {
            console.log(chalk.green(`\n${dlResult.message}`));
            if (dlResult.path) {
              console.log(chalk.gray(`\nPara ejecutar: /ejecutar ${dlResult.path}`));
            }
            console.log('');
          } else {
            console.log(chalk.red(`\n✗ ${dlResult.message}\n`));
          }
        } else if (fileIntent.action === 'search-download') {
          console.log(chalk.cyan(`🔍 Buscando: "${fileIntent.target}"`));
          const sr = await searchFilesOnline(fileIntent.target);
          if (sr.ok && sr.results) {
            console.log(chalk.cyan(`\n${sr.message}`));
            sr.results.forEach((r, i) => {
              console.log(chalk.white(`  ${i + 1}. ${r.title}`));
              console.log(chalk.gray(`     ${r.url}`));
              if (r.snippet) console.log(chalk.gray(`     ${r.snippet.substring(0, 120)}`));
            });
            console.log(chalk.gray('\nPara descargar: /download <url>\n'));
          } else {
            console.log(chalk.yellow(`\n${sr.message}\n`));
          }
        } else if (fileIntent.action === 'execute') {
          const execResult = await executeFile(fileIntent.target);
          if (execResult.ok) {
            console.log(chalk.green(`\n${execResult.message}\n`));
          } else {
            console.log(chalk.red(`\n✗ ${execResult.message}\n`));
          }
        } else if (fileIntent.action === 'auto-install') {
          console.log(chalk.cyan(`🚀 Pipeline: buscar → descargar → ejecutar "${fileIntent.target}"\n`));
          const installResult = await installApp(fileIntent.target);
          if (installResult.ok) {
            console.log(chalk.green(installResult.message));
            console.log('');
          } else {
            console.log(chalk.red(installResult.message));
            console.log('');
          }
        }
        saveSession(session);
        continue;
      }

      addMessage(session, 'user', userInput);

      // ── Auto web search: detectar si necesita datos en vivo ──
      let webContext = '';
      if (shouldSearchWeb(userInput)) {
        const query = extractSearchQuery(userInput);
        if (query.length >= 3) {
          process.stdout.write(chalk.yellow('🔍 Buscando en internet...'));
          try {
            const backendUrl = (config as any).claudyBackendUrl || 'http://127.0.0.1:3001';
            const results = await searchWeb(query, backendUrl);
            if (results.length > 0) {
              webContext = formatSearchContext(query, results);
              process.stdout.write(
                `\r${chalk.green('✓')} ${chalk.dim(`${results.length} resultados encontrados`)}` +
                ' '.repeat(20) + '\n'
              );
            } else {
              process.stdout.write(
                `\r${chalk.yellow('⚠')} ${chalk.dim('Sin resultados web')}` +
                ' '.repeat(20) + '\n'
              );
            }
          } catch {
            process.stdout.write(
              `\r${chalk.yellow('⚠')} ${chalk.dim('Búsqueda web no disponible')}` +
              ' '.repeat(20) + '\n'
            );
          }
        }
      }

      // Spinner mientras se recibe la respuesta (tokens se bufferean, no se imprimen)
      let receivedTokens = false;
      let charCount = 0;
      const spinnerChars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];
      let spinnerIdx = 0;
      let startTime = Date.now();
      const spinnerInterval = setInterval(() => {
        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        const label = receivedTokens
          ? `Generando respuesta... (${charCount} chars)`
          : `Pensando... (${elapsed}s)`;
        process.stdout.write(`\r${chalk.cyan(spinnerChars[spinnerIdx++ % spinnerChars.length])} ${label}  `);
      }, 80);

      try {
        // Skip skills when web search is active — no need for coding skills on a football question
        const skillsCtx = webContext ? '' : buildSkillsContext(findRelevantSkills(userInput, 2));
        // Add location context for weather, laws, timezone awareness
        const locationCtx = await (async () => {
          try {
            const { buildLocationContext } = await import('../location.js');
            return await buildLocationContext();
          } catch {
            return '';
          }
        })();
        const sessionSummaryCtx = session.summary
          ? `Resumen de mensajes anteriores de esta sesión (los mensajes originales fueron compactados):\n${session.summary}`
          : '';
        const systemPrompt = [
          config.agent.systemPrompt,
          locationCtx,
          sessionSummaryCtx,
          skillsCtx,
          webContext,
        ].filter(Boolean).join('\n\n');

        let reply = '';

        // Reset spinner timer — now we're ONLY waiting for the LLM
        startTime = Date.now();

        // Hard 120-second timeout for the LLM call only (starts AFTER web search finishes)
        streamController = new AbortController();
        const hardTimeout = setTimeout(() => streamController!.abort(), 120_000);

        // Mark as streaming so Ctrl+C can cancel
        isStreaming = true;

        try {
          let firstToken = true;
          await client.sendMessageStreaming(
            session,
            userInput,
            session.model,
            systemPrompt,
            (token: string) => {
              if (!receivedTokens) {
                receivedTokens = true;
                // Al recibir el primer token: limpiar spinner e iniciar salida en vivo
                clearInterval(spinnerInterval);
                process.stdout.write('\r' + ' '.repeat(60) + '\r');
                process.stdout.write(chalk.blue('Claudy: '));
              }
              reply += token;
              charCount = reply.length;
              // Imprimir token en vivo (streaming visual)
              process.stdout.write(token);
            },
            streamController.signal
          );
          // Nueva línea tras finalizar el stream
          if (receivedTokens) {
            process.stdout.write('\n');
          }
        } finally {
          clearTimeout(hardTimeout);
          isStreaming = false;
          streamController = null;
        }

        // Si no llegó ningún token, limpiar spinner
        if (!receivedTokens) {
          clearInterval(spinnerInterval);
          process.stdout.write('\r' + ' '.repeat(60) + '\r');
        }

        // Guardar respuesta en sesión
        addMessage(session, 'assistant', reply);
        saveSession(session);

        // Auto-resumen si la sesión es muy larga
        if (needsSummarization(session)) {
          console.log(chalk.dim('\n📝 Sesión larga detectada — generando resumen compacto...'));
          try {
            const summaryPrompt = buildSummarizationPrompt(session);
            let summaryText = '';
            const summaryCtrl = new AbortController();
            const summaryTimeout = setTimeout(() => summaryCtrl.abort(), 60_000);

            await client.sendMessageStreaming(
              session,
              summaryPrompt,
              session.model,
              'Responde solo con el resumen solicitado. No añadas comentarios.',
              (token: string) => {
                summaryText += token;
              },
              summaryCtrl.signal
            );

            clearTimeout(summaryTimeout);

            if (summaryText.trim().length > 0) {
              compactSession(session, summaryText.trim());
              saveSession(session);
              console.log(chalk.dim(`✓ Sesión compactada: ${session.messages.length} mensajes activos + resumen guardado`));
            }
          } catch (err: any) {
            console.log(chalk.dim(`⚠ No se pudo generar resumen: ${err.message}`));
          }
        }

        // Auto-detectar URLs SKILL.md en la respuesta y ofrecer instalarlas
        const urls = findSkillUrls(reply);
        for (const url of urls) {
          const { confirm } = await inquirer.prompt([
            {
              type: 'confirm',
              name: 'confirm',
              message: `🔌 Detecté un skill: ${url}\n  ¿Instalar?`,
              default: true,
            },
          ]);
          if (confirm) {
            try {
              const installed = await installSkillFromUrl(url);
              console.log(
                chalk.green(`✓ Skill "${installed.name}" instalado en ${installed.path}\n`)
              );
            } catch (err: any) {
              console.log(chalk.red(`✗ Error instalando: ${err.message}\n`));
            }
          }
        }
      } catch (error: any) {
        clearInterval(spinnerInterval);
        process.stdout.write('\r' + ' '.repeat(60) + '\r');
        isStreaming = false;
        streamController = null;

        // User cancelled with Ctrl+C — not an error, just skip saving partial reply
        if (error.name === 'AbortError' && !receivedTokens) {
          console.log(chalk.yellow('⚠ Respuesta cancelada') + '\n');
          continue;
        }

        const msg = error.name === 'AbortError'
          ? 'Timeout: el modelo tardó más de 120s. Prueba un mensaje más corto o cambia de modelo con /model.'
          : error.message;
        console.log(chalk.red('✗ ' + msg) + '\n');
      }
    }

    saveSession(session);
    rl.close();
    console.log(chalk.gray('\n👋 Sesión guardada. ¡Hasta luego!\n'));
  });

async function createNewSession(model: string): Promise<Session> {
  const { name } = await inquirer.prompt([
    {
      type: 'input',
      name: 'name',
      message: 'Nombre de la sesión (Enter para auto):',
      default: `Chat ${new Date().toLocaleString()}`,
    },
  ]);
  return createSession(name, model);
}

async function handleCommand(
  command: string,
  session: Session,
  config: Config
): Promise<'exit' | 'handled'> {
  const [cmd, ...args] = command.split(' ');
  const rest = args.join(' ');

  switch (cmd) {
    case '/exit':
    case '/quit':
      return 'exit';

    case '/clear':
      console.clear();
      return 'handled';

    case '/save':
      saveSession(session);
      console.log(chalk.green('✓ Sesión guardada'));
      return 'handled';

    case '/model':
      if (args.length > 0) {
        session.model = args.join(' ');
        session.opencodeSessionId = undefined;
        saveSession(session);
        console.log(chalk.green(`✓ Modelo cambiado a: ${session.model}`));
      } else {
        console.log(chalk.gray(`Modelo actual: ${session.model}`));
      }
      return 'handled';

    case '/read': {
      if (!rest) {
        console.log(chalk.yellow('Uso: /read <ruta>'));
        return 'handled';
      }
      const result = await toolRead(rest, config.tools);
      if (result.ok) {
        console.log(chalk.cyan(`\n📄 ${rest}:`));
        console.log(chalk.gray(result.output));
        console.log('');
        // Inyectar como mensaje "user" para que Claudy lo vea en el siguiente turno
        addMessage(
          session,
          'user',
          `[Tool /read ${rest}]\n\`\`\`\n${result.output}\n\`\`\``
        );
        saveSession(session);
      } else {
        console.log(chalk.red(`✗ ${result.error}`));
      }
      return 'handled';
    }

    case '/write': {
      // Sintaxis: /write <ruta>\n<contenido>
      const newlineIdx = rest.indexOf('\n');
      const filePath = newlineIdx >= 0 ? rest.slice(0, newlineIdx).trim() : rest.trim();
      const content = newlineIdx >= 0 ? rest.slice(newlineIdx + 1) : '';

      if (!filePath) {
        console.log(chalk.yellow('Uso: /write <ruta>\\n<contenido>'));
        return 'handled';
      }
      if (!content) {
        console.log(chalk.yellow('Sin contenido. Pasa el contenido tras un salto de línea.'));
        return 'handled';
      }
      const result = await toolWrite(filePath, content, config.tools);
      if (result.ok) {
        console.log(chalk.green(`✓ ${result.output}`));
        addMessage(session, 'user', `[Tool /write ${filePath}] ${result.output}`);
        saveSession(session);
      } else {
        console.log(chalk.red(`✗ ${result.error}`));
      }
      return 'handled';
    }

    case '/exec': {
      if (!rest) {
        console.log(chalk.yellow('Uso: /exec <comando>'));
        return 'handled';
      }
      const result = await toolExec(rest, config.tools);
      if (result.ok) {
        console.log(chalk.cyan(`\n▶ ${rest}`));
        console.log(chalk.gray(result.output));
        console.log('');
        addMessage(
          session,
          'user',
          `[Tool /exec ${rest}]\n\`\`\`\n${result.output}\n\`\`\``
        );
        saveSession(session);
      } else {
        console.log(chalk.red(`✗ ${result.error}`));
        if (result.output) console.log(chalk.gray(result.output));
      }
      return 'handled';
    }

    case '/skills': {
      const skills = listSkills();
      if (skills.length === 0) {
        console.log(chalk.gray('\nNo hay skills instalados.'));
        console.log(chalk.gray('Instala con: claudy skills install <url>\n'));
      } else {
        console.log(chalk.cyan(`\n📚 Skills (${skills.length}):`));
        skills.forEach((s) => console.log(chalk.gray(`  • ${s.name} — ${s.description}`)));
        console.log('');
      }
      return 'handled';
    }

    case '/tools':
      console.log(chalk.cyan('\nEstado de tools:'));
      console.log(`  enabled:    ${tick(config.tools.enabled)}`);
      console.log(`  read:       ${tick(config.tools.allowRead)}`);
      console.log(`  write:      ${tick(config.tools.allowWrite)}`);
      console.log(`  exec:       ${tick(config.tools.allowExec)}`);
      console.log(`  root:       ${chalk.gray(config.tools.allowedRoot)}`);
      console.log(`  timeout:    ${chalk.gray(config.tools.commandTimeoutMs + 'ms')}`);
      console.log(chalk.gray('\nCambia con: claudy config set tools.allowWrite true\n'));
      return 'handled';

    case '/history':
      console.log(chalk.gray(`\nMensajes: ${session.messages.length}`));
      console.log(chalk.gray(`OpenCode session: ${session.opencodeSessionId || '(no creada)'}\n`));
      return 'handled';

    case '/download':
    case '/descargar': {
      if (!rest) {
        console.log(chalk.yellow('Uso: /download <url>  o  /descargar <url>'));
        return 'handled';
      }
      console.log(chalk.cyan(`⬇ Descargando: ${rest}`));
      const dlResult = await downloadFile(rest);
      if (dlResult.ok) {
        console.log(chalk.green(`\n${dlResult.message}`));
        if (dlResult.path) {
          console.log(chalk.gray(`\nPara ejecutar: /ejecutar ${dlResult.path}`));
        }
        console.log('');
      } else {
        console.log(chalk.red(`\n✗ ${dlResult.message}\n`));
      }
      return 'handled';
    }

    case '/buscar': {
      if (!rest) {
        console.log(chalk.yellow('Uso: /buscar <qué archivo buscas>'));
        return 'handled';
      }
      console.log(chalk.cyan(`🔍 Buscando archivos: "${rest}"`));
      const sr = await searchFilesOnline(rest);
      if (sr.ok && sr.results) {
        console.log(chalk.cyan(`\n${sr.message}`));
        sr.results.forEach((r, i) => {
          console.log(chalk.white(`  ${i + 1}. ${r.title}`));
          console.log(chalk.gray(`     ${r.url}`));
          if (r.snippet) console.log(chalk.gray(`     ${r.snippet.substring(0, 120)}`));
        });
        console.log(chalk.gray('\nPara descargar: /download <url>\n'));
      } else {
        console.log(chalk.yellow(`\n${sr.message}\n`));
      }
      return 'handled';
    }

    case '/ejecutar': {
      if (!rest) {
        console.log(chalk.yellow('Uso: /ejecutar <ruta del archivo>'));
        return 'handled';
      }
      const execResult = await executeFile(rest);
      if (execResult.ok) {
        console.log(chalk.green(`\n${execResult.message}\n`));
      } else {
        console.log(chalk.red(`\n✗ ${execResult.message}\n`));
      }
      return 'handled';
    }

    case '/instalar':
    case '/install': {
      if (!rest) {
        console.log(chalk.yellow('Uso: /instalar <nombre de la app>\nEj: /instalar winrar'));
        return 'handled';
      }
      console.log(chalk.cyan(`🚀 Pipeline automático: buscar → descargar → ejecutar\n`));
      const installResult = await installApp(rest);
      if (installResult.ok) {
        console.log(chalk.green(installResult.message));
        console.log('');
      } else {
        console.log(chalk.red(installResult.message));
        console.log('');
      }
      return 'handled';
    }

    case '/search':
    case '/buscar-sesion': {
      if (!rest) {
        console.log(chalk.yellow('Uso: /search <texto>  o  /buscar-sesion <texto>'));
        console.log(chalk.gray('Busca en todas las sesiones por nombre y contenido de mensajes.'));
        return 'handled';
      }
      const results = searchSessions(rest);
      console.log(formatSearchResults(results, rest));
      return 'handled';
    }

    case '/export': {
      if (!rest) {
        console.log(chalk.yellow(`Uso: /export <formato> [ruta]`));
        console.log(chalk.gray(getSupportedFormats()));
        console.log(chalk.gray('Ej: /export md, /export html, /export txt, /export pdf'));
        return 'handled';
      }
      const [format, ...pathParts] = rest.split(' ');
      const validFormats: ExportFormat[] = ['md', 'html', 'txt', 'pdf'];
      if (!validFormats.includes(format as ExportFormat)) {
        console.log(chalk.red(`✗ Formato "${format}" no válido.`));
        console.log(chalk.gray(getSupportedFormats()));
        return 'handled';
      }
      const outputDir = pathParts.join(' ') || undefined;
      try {
        const filename = exportChat(session.messages, session.name, format as ExportFormat, outputDir);
        console.log(chalk.green(`✓ Chat exportado a: ${filename}`));
        addMessage(session, 'user', `[Tool /export ${format}] Exportado a ${filename}`);
        saveSession(session);
      } catch (err: any) {
        console.log(chalk.red(`✗ Error exportando: ${err.message}`));
      }
      return 'handled';
    }

    case '/memory': {
      const subCmd = args[0];
      const restArgs = args.slice(1).join(' ');

      if (!subCmd || subCmd === 'help') {
        console.log(chalk.cyan('\nComandos de memoria:'));
        console.log(chalk.gray('  /memory save <texto>        - Guardar nota en memoria'));
        console.log(chalk.gray('  /memory search <query>      - Buscar en memoria'));
        console.log(chalk.gray('  /memory list [n]            - Listar últimas n memorias (default 20)'));
        console.log(chalk.gray('  /memory delete <id>         - Eliminar memoria por ID'));
        console.log(chalk.gray('  /memory archive [dias]      - Archivar memorias antiguas (default 7 días)'));
        console.log(chalk.gray('  /memory help                - Esta ayuda\n'));
        return 'handled';
      }

      if (subCmd === 'save') {
        if (!restArgs) {
          console.log(chalk.yellow('Uso: /memory save <texto a recordar>'));
          return 'handled';
        }
        const entry = addMemory(restArgs, [], session.id);
        console.log(chalk.green(`✓ Memoria guardada (ID: ${entry.id.substring(0, 12)}...)`));
        addMessage(session, 'user', `[Memory saved] ${restArgs}`);
        saveSession(session);
        return 'handled';
      }

      if (subCmd === 'search') {
        if (!restArgs) {
          console.log(chalk.yellow('Uso: /memory search <query>'));
          return 'handled';
        }
        const results = searchMemories(restArgs, 10);
        if (results.length === 0) {
          console.log(chalk.gray('\nNo se encontraron memorias.'));
        } else {
          console.log(chalk.cyan(`\n🧠 Memorias (${results.length}):`));
          results.forEach((m) => {
            console.log(chalk.gray(`  [${m.id.substring(0, 12)}] ${m.content.substring(0, 100)}${m.content.length > 100 ? '...' : ''}`));
            console.log(chalk.gray(`    ${new Date(m.timestamp).toLocaleString()}`));
          });
          console.log('');
        }
        return 'handled';
      }

      if (subCmd === 'list') {
        const limit = parseInt(restArgs) || 20;
        const results = listMemories(limit);
        if (results.length === 0) {
          console.log(chalk.gray('\nNo hay memorias guardadas.'));
        } else {
          console.log(chalk.cyan(`\n📚 Memorias recientes (${results.length}):`));
          results.forEach((m) => {
            console.log(chalk.gray(`  [${m.id.substring(0, 12)}] ${m.content.substring(0, 100)}${m.content.length > 100 ? '...' : ''}`));
            console.log(chalk.gray(`    ${new Date(m.timestamp).toLocaleString()}`));
          });
          console.log('');
        }
        return 'handled';
      }

      if (subCmd === 'delete') {
        if (!restArgs) {
          console.log(chalk.yellow('Uso: /memory delete <id>'));
          return 'handled';
        }
        const deleted = deleteMemory(restArgs);
        if (deleted) {
          console.log(chalk.green('✓ Memoria eliminada.'));
        } else {
          console.log(chalk.yellow('⚠ No se encontró esa memoria.'));
        }
        return 'handled';
      }

      if (subCmd === 'archive') {
        const days = parseInt(restArgs) || 7;
        const archived = archiveOldMemories(days);
        console.log(chalk.green(`✓ ${archived} memorias archivadas (> ${days} días).`));
        return 'handled';
      }

      console.log(chalk.yellow(`Subcomando desconocido: ${subCmd}. Usa /memory help`));
      return 'handled';
    }

    case '/help':
      console.log(chalk.cyan('\nComandos disponibles:'));
      console.log(chalk.gray('  /exit                       - Salir'));
      console.log(chalk.gray('  /clear                      - Limpiar pantalla'));
      console.log(chalk.gray('  /save                       - Guardar sesión'));
      console.log(chalk.gray('  /model <m>                  - Cambiar modelo'));
      console.log(chalk.gray('  /read <ruta>                - Leer archivo (lo añade al contexto)'));
      console.log(chalk.gray('  /write <ruta>\\n<contenido>  - Escribir archivo'));
      console.log(chalk.gray('  /exec <comando>             - Ejecutar shell command'));
      console.log(chalk.gray('  /download <url>             - Descargar archivo de internet'));
      console.log(chalk.gray('  /buscar <tema>              - Buscar archivos para descargar'));
      console.log(chalk.gray('  /ejecutar <ruta>            - Abrir/ejecutar un archivo'));
      console.log(chalk.gray('  /instalar <app>             - Pipeline: buscar→descargar→ejecutar'));
      console.log(chalk.gray('  /find-skill <tema>          - Buscar skills en internet'));
      console.log(chalk.gray('  /install-skill <tema>       - Instalar el mejor skill encontrado'));
      console.log(chalk.gray('  /tools                      - Ver estado de tools'));
      console.log(chalk.gray('  /history                    - Info de sesión'));
      console.log(chalk.gray('  /search <texto>             - Buscar en sesiones pasadas'));
      console.log(chalk.gray('  /export <formato>           - Exportar chat (md, html, txt, pdf)'));
      console.log(chalk.gray('  /memory                     - Gestionar memoria vectorial'));
      console.log(chalk.gray('  /help                       - Esta ayuda\n'));
      return 'handled';

    default:
      console.log(chalk.yellow(`Comando desconocido: ${cmd}. Usa /help`));
      return 'handled';
  }
}

function tick(value: boolean): string {
  return value ? chalk.green('✓') : chalk.red('✗');
}

/**
 * Renderiza Markdown con colores de terminal usando marked-terminal.
 * Si falla (e.g. texto muy corto o sin Markdown), devuelve el texto original.
 */
function renderMarkdown(text: string): string {
  try {
    marked.setOptions({ renderer: new TerminalRenderer() } as Parameters<typeof marked.setOptions>[0]);
    const rendered = marked(text) as string;
    // Quitar salto de línea final extra que añade marked
    return rendered.replace(/\n$/, '');
  } catch {
    return text;
  }
}

async function handleFindSkill(query: string, session: Session): Promise<void> {
  if (!query.trim()) {
    return;
  }

  process.stdout.write(chalk.cyan('Buscando skills...'));

  try {
    const skills = await searchRemoteSkills(query, 5);
    process.stdout.write('\r' + ' '.repeat(24) + '\r');

    if (skills.length === 0) {
      const message = `No encontre skills en internet para "${query}".`;
      console.log(chalk.blue('Claudy: ') + message + '\n');
      addMessage(session, 'assistant', message);
      saveSession(session);
      return;
    }

    const message = [
      `Encontre estos skills en internet para "${query}":`,
      ...skills.map(
        (skill, index) =>
          `${index + 1}. ${skill.name} (${skill.source}/${skill.skillId}) - ${
            skill.installs || 0
          } installs`
      ),
      '',
      `Para instalar el mejor resultado: /install-skill ${query}`,
    ].join('\n');

    console.log(chalk.blue('Claudy: ') + message + '\n');
    addMessage(session, 'assistant', message);
    saveSession(session);
  } catch (error: any) {
    process.stdout.write('\r' + ' '.repeat(24) + '\r');
    const message = `No pude buscar skills: ${error.message || String(error)}`;
    console.log(chalk.red('Error: ') + message + '\n');
    addMessage(session, 'assistant', message);
    saveSession(session);
  }
}

async function handleInstallSkill(query: string, session: Session): Promise<void> {
  if (!query.trim()) {
    return;
  }

  process.stdout.write(chalk.cyan('Buscando e instalando skill...'));

  try {
    const result = await installBestSkillForQuery(query);
    process.stdout.write('\r' + ' '.repeat(36) + '\r');

    const alternatives = result.candidates
      .filter((candidate) => candidate.id !== result.remote.id)
      .slice(0, 3)
      .map(
        (candidate) =>
          `- ${candidate.name} (${candidate.source}/${candidate.skillId}, ${
            candidate.installs || 0
          } installs)`
      );

    const message = [
      `Skill instalado: ${result.installed.name}`,
      `Fuente: ${result.remote.source}/${result.remote.skillId}`,
      `Installs reportados: ${result.remote.installs || 0}`,
      `Archivo: ${result.installed.path}`,
      `README actualizado: ${result.installed.readmePath}`,
      '',
      'Ya queda disponible para futuras respuestas de Claudy cuando el mensaje sea relevante.',
      alternatives.length ? '\nOtros candidatos considerados:\n' + alternatives.join('\n') : '',
    ]
      .filter(Boolean)
      .join('\n');

    console.log(chalk.blue('Claudy: ') + message + '\n');
    addMessage(session, 'assistant', message);
    saveSession(session);
  } catch (error: any) {
    process.stdout.write('\r' + ' '.repeat(36) + '\r');
    const message = `No pude instalar la skill: ${error.message || String(error)}`;
    console.log(chalk.red('Error: ') + message + '\n');
    addMessage(session, 'assistant', message);
    saveSession(session);
  }
}
